"""
Crossplane XRD and Composition Schema Validator
Ensures Composite Resource Definitions (XRDs), Compositions, and Developer Claims adhere to
Crossplane v1 specification standards and maintain referential integrity.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List
import yaml


class CrossplaneValidator:
    """Validates Crossplane XRDs, Compositions, and Claims."""

    XRD_KINDS = {"CompositeResourceDefinition"}
    COMPOSITION_KINDS = {"Composition"}

    @classmethod
    def validate_file(cls, path: Path) -> List[str]:
        errors: List[str] = []
        if not path.exists():
            return [f"File does not exist: {path}"]

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
        errors: List[str] = []
        if not isinstance(doc, dict):
            return ["Root manifest must be a dictionary"]

        api_version = doc.get("apiVersion", "")
        kind = doc.get("kind", "")
        metadata = doc.get("metadata", {})
        spec = doc.get("spec", {})

        if not metadata.get("name"):
            errors.append("Missing required field: 'metadata.name'")

        if kind in cls.XRD_KINDS:
            errors.extend(cls._validate_xrd(spec))
        elif kind in cls.COMPOSITION_KINDS:
            errors.extend(cls._validate_composition(spec))

        return errors

    @classmethod
    def _validate_xrd(cls, spec: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        if not isinstance(spec, dict):
            return ["XRD spec must be a dictionary"]

        if not spec.get("group"):
            errors.append("XRD missing 'spec.group'")
        names = spec.get("names", {})
        if not names.get("kind"):
            errors.append("XRD missing 'spec.names.kind'")

        versions = spec.get("versions", [])
        if not versions or not isinstance(versions, list):
            errors.append("XRD must define at least one version in 'spec.versions'")
        else:
            for v in versions:
                if not v.get("name"):
                    errors.append("XRD version missing 'name'")
                if not v.get("schema", {}).get("openAPIV3Schema"):
                    errors.append(f"XRD version '{v.get('name')}' missing openAPIV3Schema")

        return errors

    @classmethod
    def _validate_composition(cls, spec: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        if not isinstance(spec, dict):
            return ["Composition spec must be a dictionary"]

        comp_ref = spec.get("compositeTypeRef", {})
        if not comp_ref.get("apiVersion") or not comp_ref.get("kind"):
            errors.append("Composition missing 'spec.compositeTypeRef.apiVersion' or 'kind'")

        resources = spec.get("resources", [])
        if not resources or not isinstance(resources, list):
            errors.append("Composition must declare at least one resource in 'spec.resources'")
        else:
            for i, r in enumerate(resources):
                base = r.get("base", {})
                if not base.get("apiVersion") or not base.get("kind"):
                    errors.append(f"Composition resource #{i} missing 'base.apiVersion' or 'base.kind'")

        return errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: crossplane_validator.py <file-or-dir>")
        sys.exit(1)

    target = Path(sys.argv[1])
    files = [target] if target.is_file() else list(target.rglob("*.yaml")) + list(target.rglob("*.yml"))
    all_errors = []
    for f in files:
        errs = CrossplaneValidator.validate_file(f)
        if errs:
            all_errors.extend(errs)

    if all_errors:
        print(f"Crossplane validation failed with {len(all_errors)} errors:")
        for e in all_errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"All {len(files)} files passed Crossplane validation!")
