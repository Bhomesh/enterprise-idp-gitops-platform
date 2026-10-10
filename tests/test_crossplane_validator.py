import unittest
from pathlib import Path

from src.crossplane_validator import CrossplaneValidator


class TestCrossplaneValidator(unittest.TestCase):
    def test_valid_xrd(self):
        doc = {
            "apiVersion": "apiextensions.crossplane.io/v1",
            "kind": "CompositeResourceDefinition",
            "metadata": {"name": "xmyservices.platform.corp"},
            "spec": {
                "group": "platform.corp",
                "names": {"kind": "XMyService", "plural": "xmyservices"},
                "versions": [
                    {
                        "name": "v1alpha1",
                        "served": True,
                        "referenceable": True,
                        "schema": {"openAPIV3Schema": {"type": "object"}},
                    }
                ],
            },
        }
        errors = CrossplaneValidator.validate_document(doc)
        self.assertEqual(errors, [])

    def test_invalid_xrd_missing_schema(self):
        doc = {
            "apiVersion": "apiextensions.crossplane.io/v1",
            "kind": "CompositeResourceDefinition",
            "metadata": {"name": "broken-xrd"},
            "spec": {
                "group": "platform.corp",
                "names": {"kind": "XMyService"},
                "versions": [{"name": "v1alpha1"}],
            },
        }
        errors = CrossplaneValidator.validate_document(doc)
        self.assertTrue(any("missing openAPIV3Schema" in e for e in errors))

    def test_valid_composition(self):
        doc = {
            "apiVersion": "apiextensions.crossplane.io/v1",
            "kind": "Composition",
            "metadata": {"name": "sample-comp"},
            "spec": {
                "compositeTypeRef": {
                    "apiVersion": "platform.corp/v1alpha1",
                    "kind": "XMyService",
                },
                "resources": [
                    {
                        "base": {
                            "apiVersion": "s3.aws.upbound.io/v1beta1",
                            "kind": "Bucket",
                        }
                    }
                ],
            },
        }
        errors = CrossplaneValidator.validate_document(doc)
        self.assertEqual(errors, [])

    def test_validate_repo_crossplane_files(self):
        repo_root = Path(__file__).parent.parent
        files = list((repo_root / "crossplane" / "apis").glob("*.yaml")) + \
                list((repo_root / "crossplane" / "compositions").glob("*.yaml"))
        self.assertGreater(len(files), 0)
        for f in files:
            errs = CrossplaneValidator.validate_file(f)
            self.assertEqual(errs, [], f"Validation failed for {f}: {errs}")


if __name__ == "__main__":
    unittest.main()
