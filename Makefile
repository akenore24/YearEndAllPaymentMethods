# JAN 17, 2026||10:30PM

.PHONY: docs

docs:
	@echo "📄 Generating CLI help documentation..."
	@./make_docs.sh


.PHONY: help
help:
	@echo "Available targets:"
	@echo "  make docs   - regenerate CLI help docs in docs/reference/help/"


