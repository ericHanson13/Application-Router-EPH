"""`python -m permit_review` lands here: check Python version, then run the CLI."""

import sys

# Fail fast with a readable message; the rest of the package uses 3.10+ syntax
# (int | None, match-like typing) that older interpreters would choke on.
if sys.version_info < (3, 10):
    sys.exit(
        f"Permit Review needs Python 3.10 or newer, but this is Python {sys.version.split()[0]}.\n"
        "See 'Setup' in the README."
    )

from permit_review.cli import main  # noqa: E402  # imported after the version check on purpose

raise SystemExit(main())
