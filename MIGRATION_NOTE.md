# Migration Note: poly17 Replacement

This repository replaces the legacy poly17 workflow with a fully auditable open implementation.

Why replace instead of patch:
1. Legacy executable behavior is opaque and difficult to audit.
2. Reproducible scientific workflows require deterministic reports and checksums.
3. Modern automation needs explicit merge policies, validation, and test coverage.
4. External UCI evaluation is better stored outside BIN records to preserve Polyglot compliance.

This tool does not patch or reverse-engineer old binaries and treats them only as historical artifacts.
