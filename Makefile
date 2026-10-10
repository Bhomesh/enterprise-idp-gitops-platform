.PHONY: help test validate-templates validate-crossplane reap-stale fmt

help:
	@echo "Enterprise Internal Developer Platform (IDP) Commands:"
	@echo "  make test                - Run all unit and integration tests"
	@echo "  make validate-templates  - Validate Backstage catalog entities and templates"
	@echo "  make validate-crossplane - Validate Crossplane XRDs and Compositions"
	@echo "  make reap-stale          - Run the ephemeral environment reaper"

test:
	PYTHONPATH=. python3 -m unittest discover -s tests -p "test_*.py"

validate-templates:
	python3 src/template_validator.py backstage/

validate-crossplane:
	python3 src/crossplane_validator.py crossplane/

reap-stale:
	python3 src/ephemeral_manager.py reap
