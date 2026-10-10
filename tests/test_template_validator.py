import unittest
from pathlib import Path

from src.template_validator import BackstageValidator


class TestTemplateValidator(unittest.TestCase):
    def test_valid_component(self):
        doc = {
            "apiVersion": "backstage.io/v1alpha1",
            "kind": "Component",
            "metadata": {"name": "test-service"},
            "spec": {
                "type": "service",
                "lifecycle": "production",
                "owner": "team-core",
            },
        }
        errors = BackstageValidator.validate_document(doc)
        self.assertEqual(errors, [])

    def test_missing_fields_component(self):
        doc = {
            "apiVersion": "backstage.io/v1alpha1",
            "kind": "Component",
            "metadata": {},
            "spec": {},
        }
        errors = BackstageValidator.validate_document(doc)
        self.assertTrue(any("metadata.name" in e for e in errors))
        self.assertTrue(any("type" in e for e in errors))

    def test_valid_template(self):
        doc = {
            "apiVersion": "scaffolder.backstage.io/v1beta3",
            "kind": "Template",
            "metadata": {"name": "sample-template"},
            "spec": {
                "type": "service",
                "steps": [
                    {"id": "step1", "action": "fetch:template"},
                    {"id": "step2", "action": "publish:github"},
                ],
            },
        }
        errors = BackstageValidator.validate_document(doc)
        self.assertEqual(errors, [])

    def test_duplicate_step_id_template(self):
        doc = {
            "apiVersion": "scaffolder.backstage.io/v1beta3",
            "kind": "Template",
            "metadata": {"name": "broken-template"},
            "spec": {
                "type": "service",
                "steps": [
                    {"id": "step1", "action": "fetch:template"},
                    {"id": "step1", "action": "publish:github"},
                ],
            },
        }
        errors = BackstageValidator.validate_document(doc)
        self.assertTrue(any("Duplicate step id" in e for e in errors))

    def test_validate_repo_templates(self):
        repo_root = Path(__file__).parent.parent
        templates = [p for p in repo_root.glob("backstage/**/*.yaml") if "skeleton" not in p.parts]
        self.assertGreater(len(templates), 0)
        for t in templates:
            errs = BackstageValidator.validate_file(t)
            self.assertEqual(errs, [], f"Validation failed for {t}: {errs}")


if __name__ == "__main__":
    unittest.main()
