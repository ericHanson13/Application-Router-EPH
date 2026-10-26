import sys

if sys.version_info < (3, 10):
    sys.exit(
        f"Permit Review needs Python 3.10 or newer, but this is Python {sys.version.split()[0]}.\n"
        "See 'Setup' in the README."
    )

from permit_review.cli import main  # noqa: E402

raise SystemExit(main())
