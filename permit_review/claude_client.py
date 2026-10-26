"""Calls to Claude. Each PDF is sent whole; Claude reads both its text and its page images.

The API is asked to return a DocumentOverview (see models.py). Size/page limits
are checked here so we fail locally instead of with a vague API error.
"""

import base64

import anthropic

from permit_review.models import DocumentOverview
from permit_review.scanner import PdfFile

MODEL = "claude-opus-5-5"

# The API accepts requests up to 32 MB; base64 makes a PDF about a third larger.
MAX_PDF_BYTES = 24 * 1024 * 1024
MAX_PDF_PAGES = 600

# Role and ground rules: stay on the pages, don't invent missing documents.
SYSTEM_PROMPT = """You review permit application packets (building, sign, and similar permits) for a
permitting office.
A packet is one PDF. It usually starts with an application form a few pages long, and the
pages after it are attachments the applicant included, such as site plans, construction
drawings, contractor licenses, or proof of ownership. Some pages may be scans.
Describe what is in the packet accurately and only from what is on the pages."""

# The four review steps Claude must fill into DocumentOverview.
REVIEW_PROMPT = """Review this PDF:
1. Give a short summary, say whether it contains a permit application form, and list
   each distinct section in page order with its page range.
2. List every document the application form requires the applicant to attach to this packet.
   Look at the whole form, including instructions, checklists and footnotes. Only include
   documents to attach: leave out statements about the project (for example "Sign meets the
   wind load code"), code-compliance requirements, fees, and anything else that isn't a
   document to include. For a document that is only needed in some cases, decide from the
   applicant's answers whether it applies here. List what the form requires, not what
   happens to be attached.
3. Go through the application form field by field, including signatures, dates and checkboxes,
   and record what was entered. A field is required unless the form marks it optional or for
   office use, or it is conditional ("if applicable") and does not apply to this application.
   Mark a field 'unclear' rather than 'filled' if the entry is illegible or doesn't answer it.
4. For each document from step 2, check whether it is attached. It is attached when a page
   after the form is titled or clearly labeled as that document. Placeholder or sample text on
   the rest of the page is fine: judge only that the document is there, not the quality of its
   contents. A box on the form saying it is attached does not count by itself, and one page
   can't stand in for two different documents unless it is labeled as both."""

# Extra hint for fillable PDFs: typed values may not appear in the rendered pages.
FORM_VALUES_NOTE = """This PDF is a fillable form. These are the values stored in its form fields,
which may not all be visible on the page images. Use them together with what you see:
{values}"""


class ReviewError(Exception):
    """A problem with this PDF or Claude's answer — not a bad API key (that is raised as AuthenticationError)."""

    pass


def make_client() -> anthropic.Anthropic:
    # Reads ANTHROPIC_API_KEY from the environment (loaded from .env by the CLI).
    return anthropic.Anthropic()


def describe_pdf(client: anthropic.Anthropic, pdf: PdfFile) -> DocumentOverview:
    """Send the whole PDF to Claude and parse the reply into DocumentOverview.

    Raises ReviewError for size, page-count, refusal, or an unreadable answer.
    Other Anthropic exceptions (auth, rate limit, network) are left for review.py.
    """
    if pdf.size_bytes > MAX_PDF_BYTES:
        raise ReviewError(f"PDF is {pdf.size_bytes / 1e6:.0f} MB; the limit is about 24 MB.")
    if pdf.page_count and pdf.page_count > MAX_PDF_PAGES:
        raise ReviewError(f"PDF has {pdf.page_count} pages; the limit is {MAX_PDF_PAGES}.")

    data = base64.standard_b64encode(pdf.path.read_bytes()).decode("ascii")
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "medium"},
        # If Claude's safety filters decline a request, retry it on a fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
                {"type": "text", "text": _prompt(pdf)},
            ],
        }],
        output_format=DocumentOverview,
    )

    if response.stop_reason == "refusal":
        raise ReviewError("Claude declined to review this PDF.")
    if response.stop_reason == "max_tokens":
        raise ReviewError("Claude's answer was cut off (max_tokens).")
    if response.parsed_output is None:
        raise ReviewError("Claude's answer could not be read.")
    return response.parsed_output


def _prompt(pdf: PdfFile) -> str:
    """Review instructions, plus stored form-field values when the PDF is fillable."""
    if not pdf.form_values:
        return REVIEW_PROMPT
    values = "\n".join(f"- {name}: {value or '(empty)'}" for name, value in pdf.form_values.items())
    return REVIEW_PROMPT + "\n\n" + FORM_VALUES_NOTE.format(values=values)
