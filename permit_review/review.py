"""Review one PDF and summarize the outcome. Shared by the command line and the web page.

This is the glue between scanner (local PDF facts), claude_client (the API call),
and models (pass/fail). Callers get a JSON-ready dict they can print or send to
the browser, plus the typed overview when the review actually ran.
"""

import anthropic

from permit_review import claude_client
from permit_review.models import DocumentOverview
from permit_review.scanner import PdfFile


def review_pdf(client, pdf: PdfFile, name: str) -> tuple[dict, DocumentOverview | None]:
    """Return a JSON-ready result for one PDF, plus Claude's overview when the review ran.

    Problems with a single PDF are recorded in result["error"]. A rejected API key is raised
    as anthropic.AuthenticationError, because every other PDF would fail the same way.
    """
    entry = {"file": name, "page_count": pdf.page_count}
    if pdf.error:
        entry["error"] = pdf.error
        return entry, None

    try:
        overview = claude_client.describe_pdf(client, pdf)
    except claude_client.ReviewError as e:
        entry["error"] = str(e)
        return entry, None
    except anthropic.AuthenticationError:
        raise  # caller should stop the whole batch, not just this file
    except anthropic.RateLimitError:
        entry["error"] = "Rate limited by the Claude API; try again in a minute."
        return entry, None
    except anthropic.APIStatusError as e:
        entry["error"] = f"Claude API error {e.status_code}: {e.message}"
        return entry, None
    except anthropic.APIConnectionError:
        entry["error"] = "Could not reach the Claude API. Check your internet connection."
        return entry, None

    # Flatten the bits the UI and JSON report care about most, then keep the full overview.
    entry["overview"] = overview.model_dump()
    entry["incomplete_fields"] = [f.label for f in overview.incomplete_fields()]
    entry["missing_attachments"] = [a.name for a in overview.missing_attachments()]
    entry["result"] = "PASS" if overview.passed() else "FAIL"
    return entry, overview
