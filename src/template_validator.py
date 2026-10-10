"""
Backstage Catalog & Template Validator for Internal Developer Platform (IDP)
Validates software templates and catalog-info definitions against Backstage v1beta3 schemas.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
import yaml


class BackstageValidator:
    """Validates Backstage Scaffolder Templates and Catalog Entities."""

    REQUIRED_TEMPLATE_API_VERSIONS = {"scaffolder.backstage.io/v1beta3", "backstage.io/v1alpha1"}
    ALLOWED_CATALOG_KINDS = {"Component", "System", "Domain", "Resource", "API", "Template", "Location"}

    @classmethod
    def validate_file(cls, path: Path) -> List[str]:
        """Validates all YAML documents in a given file."""
        errors: List[str] = []
        if not path.exists():
            return [f"File does not exist: {path}"]

        # Skip skeleton files that are meant to be rendered templates (e.g., Helm values)
        if "skeleton" in path.parts:
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                docs = list(yaml.safe_load_all(f))
        except Exception as e:
            return [f"YAML parsing error in {path}: {str(e)}"]

        for idx, doc in enumerate(docs):
            if not doc:
                continue
            doc_errors = cls.validate_document(doc)
            for err in doc_errors:
                errors.append(f"Doc #{idx} in {path.name}: {err}")

        return errors

    @classmethod
    def validate_document(cls, doc: Dict[str, Any]) -> List[str]:
        """Validates a single parsed Backstage document."""
        errors: List[str] = []

        if not isinstance(doc, dict):
            return ["Root entity must be a dictionary"]

        api_version = doc.get("apiVersion")
        kind = doc.get("kind")
        metadata = doc.get("metadata", {})
        spec = doc.get("spec", {})

        if not api_version:
            errors.append("Missing required field: 'apiVersion'")
        if not kind:
            errors.append("Missing required field: 'kind'")
        elif kind not in cls.ALLOWED_CATALOG_KINDS:
            errors.append(f"Unknown kind '{kind}'. Must be one of: {sorted(cls.ALLOWED_CATALOG_KINDS)}")

        if not isinstance(metadata, dict) or not metadata.get("name"):
            errors.append("Missing required field: 'metadata.name'")

        if kind == "Template":
            errors.extend(cls._validate_template_spec(spec))
        elif kind == "Component":
            errors.extend(cls._validate_component_spec(spec))

        return errors

    @classmethod
    def _validate_template_spec(cls, spec: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        if not isinstance(spec, dict):
            return ["Template 'spec' must be a dictionary"]

        if not spec.get("type"):
            errors.append("Template missing required field: 'spec.type'")

        steps = spec.get("steps")
        if not steps or not isinstance(steps, list):
            errors.append("Template missing or invalid 'spec.steps' (must be a non-empty list)")
        else:
            step_ids = set()
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    errors.append(f"Step #{i} must be a dictionary")
                    continue
                step_id = step.get("id")
                action = step.get("action")
                if not step_id:
                    errors.append(f"Step #{i} missing 'id'")
                elif step_id in step_ids:
                    errors.append(f"Duplicate step id '{step_id}'")
                else:
                    step_ids.add(step_id)

                if not action:
                    errors.append(f"Step '{step_id or i}' missing 'action'")

        return errors

    @classmethod
    def _validate_component_spec(cls, spec: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        if not isinstance(spec, dict):
            return ["Component 'spec' must be a dictionary"]

        for req in ["type", "lifecycle", "owner"]:
            if not spec.get(req):
                errors.append(f"Component spec missing required field: '{req}'")

        return errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: template_validator.py <file-or-dir>")
        sys.exit(1)

    target = Path(sys.argv[1])
    files = [target] if target.is_file() else list(target.rglob("*.yaml")) + list(target.rglob("*.yml"))
    all_errors = []
    for f in files:
        errs = BackstageValidator.validate_file(f)
        if errs:
            all_errors.extend(errs)

    if all_errors:
        print(f"Validation failed with {len(all_errors)} errors:")
        for e in all_errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"All {len(files)} files passed Backstage validation!")
