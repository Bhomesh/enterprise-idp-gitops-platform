"""
Ephemeral Environment Lifecycle Manager for Internal Developer Platform (IDP)
Orchestrates on-demand vcluster instances mapped to Git pull requests,
enforces TTL policies, concurrency quotas, and automated cleanup.
"""

import json
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ephemeral-manager")


def sanitize_kubernetes_name(name: str) -> str:
    """
    Sanitize branch or PR string to RFC 1123 compliant Kubernetes resource name.
    - Lowercase alphanumeric characters or '-'
    - Must start and end with an alphanumeric character
    - Max 63 characters
    """
    # Replace non-alphanumeric characters with hyphen
    sanitized = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    # Truncate to 63 chars
    sanitized = sanitized[:63].rstrip("-")
    if not sanitized:
        sanitized = "env-default"
    return sanitized


class EphemeralEnvironmentManager:
    """Manages virtual clusters (vclusters) and ArgoCD applications for ephemeral PR previews."""

    def __init__(
        self,
        base_domain: str = "preview.platform.corp",
        default_ttl_hours: int = 24,
        max_ttl_hours: int = 72,
        max_active_environments: int = 15,
        state_file: Optional[Path] = None,
    ):
        self.base_domain = base_domain
        self.default_ttl_hours = default_ttl_hours
        self.max_ttl_hours = max_ttl_hours
        self.max_active_environments = max_active_environments
        self.state_file = state_file or Path("ephemeral_state.json")
        self.environments: Dict[str, Dict[str, Any]] = self._load_state()

    def _load_state(self) -> Dict[str, Dict[str, Any]]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Could not read state file %s: %s. Starting with empty state.", self.state_file, e)
        return {}

    def _save_state(self) -> None:
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.environments, f, indent=2)
        except Exception as e:
            logger.error("Failed to persist state file %s: %s", self.state_file, e)

    def provision_preview_environment(
        self,
        repo: str,
        pr_number: int,
        branch: str,
        commit_sha: str,
        author: str,
        ttl_hours: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Provisions or updates an ephemeral environment for a Pull Request."""
        env_id = f"{sanitize_kubernetes_name(repo)}-pr-{pr_number}"

        # Check concurrency quota: activating this environment increases active count if not already active
        is_already_active = self.environments.get(env_id, {}).get("status") == "active"
        if not is_already_active:
            active_count = sum(1 for e in self.environments.values() if e.get("status") == "active")
            if active_count >= self.max_active_environments:
                raise ValueError(
                    f"Quota exceeded: Active preview environments limit ({self.max_active_environments}) reached. "
                    "Teardown unused environments before spinning up new ones."
                )

        ttl = min(ttl_hours or self.default_ttl_hours, self.max_ttl_hours)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=ttl)

        sanitized_branch = sanitize_kubernetes_name(branch)
        namespace = sanitize_kubernetes_name(f"vcluster-pr-{pr_number}")
        hostname = f"pr-{pr_number}.{sanitize_kubernetes_name(repo)[:40]}.{self.base_domain}"

        env_record = {
            "id": env_id,
            "repo": repo,
            "pr_number": pr_number,
            "branch": branch,
            "sanitized_branch": sanitized_branch,
            "commit_sha": commit_sha,
            "author": author,
            "namespace": namespace,
            "hostname": hostname,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "ttl_hours": ttl,
            "status": "active",
        }

        self.environments[env_id] = env_record
        self._save_state()

        logger.info(
            "Provisioned preview environment %s for %s#%s (Expires: %s)",
            env_id, repo, pr_number, expires_at.isoformat()
        )
        return env_record

    def generate_vcluster_values(self, env_record: Dict[str, Any]) -> Dict[str, Any]:
        """Generates Helm values for the vcluster ephemeral instance."""
        return {
            "vcluster": {
                "image": "rancher/k3s:v1.30.2-k3s1",
                "resources": {
                    "limits": {"cpu": "2000m", "memory": "2Gi"},
                    "requests": {"cpu": "200m", "memory": "512Mi"},
                },
            },
            "sync": {
                "nodes": {"enabled": False},
                "persistentvolumes": {"enabled": False},
                "ingresses": {"enabled": True},
                "services": {"enabled": True},
                "configmaps": {"enabled": True},
                "secrets": {"enabled": True},
            },
            "isolation": {
                "enabled": True,
                "networkPolicy": {"enabled": True},
                "resourceQuota": {
                    "enabled": True,
                    "quota": {
                        "requests.cpu": "4",
                        "requests.memory": "8Gi",
                        "limits.cpu": "8",
                        "limits.memory": "16Gi",
                        "services.loadbalancers": "0",
                        "services.nodeports": "0",
                    },
                },
            },
            "telemetry": {
                "labels": {
                    "platform.corp/owner": env_record["author"],
                    "platform.corp/repo": env_record["repo"],
                    "platform.corp/pr": str(env_record["pr_number"]),
                    "platform.corp/expires-at": env_record["expires_at"],
                }
            },
        }

    def generate_argocd_application(self, env_record: Dict[str, Any]) -> Dict[str, Any]:
        """Generates ArgoCD Application manifest for the preview environment."""
        app_name = sanitize_kubernetes_name(f"preview-{env_record['id']}")
        return {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": app_name,
                "namespace": "argocd",
                "labels": {
                    "app.kubernetes.io/managed-by": "idp-ephemeral-manager",
                    "preview-env": "true",
                    "pr": str(env_record["pr_number"]),
                },
                "annotations": {
                    "platform.corp/ttl-hours": str(env_record["ttl_hours"]),
                    "platform.corp/expires-at": env_record["expires_at"],
                    "platform.corp/author": env_record["author"],
                },
            },
            "spec": {
                "project": "preview-environments",
                "source": {
                    "repoURL": f"https://github.com/{env_record['repo']}.git",
                    "targetRevision": env_record["commit_sha"],
                    "path": "charts/app",
                    "helm": {
                        "valuesObject": {
                            "ingress": {
                                "enabled": True,
                                "host": env_record["hostname"],
                            },
                            "environment": "ephemeral-preview",
                        }
                    },
                },
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": env_record["namespace"],
                },
                "syncPolicy": {
                    "automated": {
                        "prune": True,
                        "selfHeal": True,
                    },
                    "syncOptions": [
                        "CreateNamespace=true",
                    ],
                },
            },
        }

    def destroy_preview_environment(self, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """Tears down an ephemeral environment on PR merge or close."""
        env_id = f"{sanitize_kubernetes_name(repo)}-pr-{pr_number}"
        if env_id in self.environments:
            record = self.environments[env_id]
            record["status"] = "terminated"
            record["terminated_at"] = datetime.now(timezone.utc).isoformat()
            self._save_state()
            logger.info("Decommissioned ephemeral environment %s", env_id)
            return record
        logger.warning("No active environment found for %s#%s", repo, pr_number)
        return None

    def reap_expired_environments(self) -> List[Dict[str, Any]]:
        """Reaps all active environments past their expiration timestamp."""
        now = datetime.now(timezone.utc)
        reaped = []

        for env_id, record in self.environments.items():
            if record.get("status") != "active":
                continue
            expires_at_str = record.get("expires_at")
            if not expires_at_str:
                continue
            expires_at = datetime.fromisoformat(expires_at_str)
            if now >= expires_at:
                logger.info(
                    "Reaping expired environment %s (Expired at %s, Current: %s)",
                    env_id, expires_at_str, now.isoformat()
                )
                record["status"] = "expired"
                record["terminated_at"] = now.isoformat()
                reaped.append(record)

        if reaped:
            self._save_state()
        return reaped


if __name__ == "__main__":
    manager = EphemeralEnvironmentManager()
    if len(sys.argv) < 2:
        print("Usage: ephemeral_manager.py [provision|destroy|reap|list]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "provision":
        env = manager.provision_preview_environment(
            repo="acme/payments-api",
            pr_number=42,
            branch="feature/checkout-flow",
            commit_sha="a1b2c3d4",
            author="dev-alice",
            ttl_hours=12,
        )
        print(json.dumps(env, indent=2))
    elif cmd == "reap":
        reaped = manager.reap_expired_environments()
        print(f"Reaped {len(reaped)} expired environments.")
    elif cmd == "list":
        print(json.dumps(manager.environments, indent=2))
    else:
        print(f"Unknown command: {cmd}")
