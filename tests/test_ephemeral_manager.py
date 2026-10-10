import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.ephemeral_manager import EphemeralEnvironmentManager, sanitize_kubernetes_name


class TestEphemeralManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "test_state.json"
        self.manager = EphemeralEnvironmentManager(
            base_domain="preview.platform.corp",
            default_ttl_hours=24,
            max_ttl_hours=72,
            max_active_environments=3,
            state_file=self.state_file,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sanitize_kubernetes_name(self):
        self.assertEqual(sanitize_kubernetes_name("feature/JIRA-123_checkout-flow!"), "feature-jira-123-checkout-flow")
        self.assertEqual(sanitize_kubernetes_name("---dirty---name---"), "dirty-name")
        long_str = "a" * 100
        sanitized = sanitize_kubernetes_name(long_str)
        self.assertEqual(len(sanitized), 63)
        self.assertEqual(sanitize_kubernetes_name(""), "env-default")

    def test_provision_preview_environment(self):
        env = self.manager.provision_preview_environment(
            repo="acme/payments-service",
            pr_number=101,
            branch="feature/v2-stripe",
            commit_sha="abcdef123456",
            author="engineer-bob",
            ttl_hours=12,
        )

        self.assertEqual(env["id"], "acme-payments-service-pr-101")
        self.assertEqual(env["pr_number"], 101)
        self.assertEqual(env["status"], "active")
        self.assertEqual(env["ttl_hours"], 12)
        self.assertEqual(env["hostname"], "pr-101.acme-payments-service.preview.platform.corp")

        expires_at = datetime.fromisoformat(env["expires_at"])
        created_at = datetime.fromisoformat(env["created_at"])
        self.assertAlmostEqual((expires_at - created_at).total_seconds(), 12 * 3600, delta=5)

    def test_max_ttl_clamping(self):
        env = self.manager.provision_preview_environment(
            repo="acme/service",
            pr_number=5,
            branch="fix/bug",
            commit_sha="112233",
            author="alice",
            ttl_hours=200,  # exceeds max 72
        )
        self.assertEqual(env["ttl_hours"], 72)

    def test_concurrency_quota_enforcement(self):
        # Provision up to limit (3)
        self.manager.provision_preview_environment("repo-a", 1, "b1", "sha1", "dev1")
        self.manager.provision_preview_environment("repo-b", 2, "b2", "sha2", "dev2")
        self.manager.provision_preview_environment("repo-c", 3, "b3", "sha3", "dev3")

        # 4th should raise ValueError
        with self.assertRaises(ValueError) as ctx:
            self.manager.provision_preview_environment("repo-d", 4, "b4", "sha4", "dev4")
        self.assertIn("Quota exceeded", str(ctx.exception))

    def test_destroy_environment(self):
        self.manager.provision_preview_environment("repo-a", 1, "b1", "sha1", "dev1")
        destroyed = self.manager.destroy_preview_environment("repo-a", 1)
        self.assertIsNotNone(destroyed)
        self.assertEqual(destroyed["status"], "terminated")
        self.assertIn("terminated_at", destroyed)

    def test_reap_expired_environments(self):
        # Provision an environment and manually expire it
        env = self.manager.provision_preview_environment("repo-old", 99, "branch", "sha", "dev")
        past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        self.manager.environments[env["id"]]["expires_at"] = past_time
        self.manager._save_state()

        reaped = self.manager.reap_expired_environments()
        self.assertEqual(len(reaped), 1)
        self.assertEqual(reaped[0]["id"], env["id"])
        self.assertEqual(reaped[0]["status"], "expired")

    def test_manifest_generators(self):
        env = self.manager.provision_preview_environment("acme/auth", 42, "patch-1", "sha0", "alice")
        vcluster_vals = self.manager.generate_vcluster_values(env)
        self.assertTrue(vcluster_vals["isolation"]["enabled"])
        self.assertEqual(vcluster_vals["telemetry"]["labels"]["platform.corp/pr"], "42")

        argo_app = self.manager.generate_argocd_application(env)
        self.assertEqual(argo_app["kind"], "Application")
        self.assertEqual(argo_app["metadata"]["name"], f"preview-{env['id']}")
        self.assertEqual(argo_app["spec"]["destination"]["namespace"], env["namespace"])


if __name__ == "__main__":
    unittest.main()
