"""Find PDFs in a folder and read basic facts about them locally (no API calls).

Used before Claude runs: the CLI lists files from a folder, and the web server
inspects each uploaded file. Form-field values from fillable PDFs are extracted
here so Claude can see typed answers that may not show up on page images.
"""

from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader


@dataclass
class PdfFile:
    """Local facts about one PDF, enough to decide whether to send it to Claude."""

    path: Path
    page_count: int | None  # None when the file could not be opened
    size_bytes: int
    error: str | None = None
    # Values typed into a fillable PDF form, by field name. Empty for scanned or flat PDFs.
    form_values: dict[str, str] = field(default_factory=dict)


def find_pdfs(folder: Path, recursive: bool = False) -> list[PdfFile]:
    """Return every .pdf in `folder`, sorted by path. Does not look at file contents yet
    except through inspect_pdf.
    """
    pattern = "**/*" if recursive else "*"
    paths = sorted(
        p for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() == ".pdf"
    )
    return [inspect_pdf(p) for p in paths]


def inspect_pdf(path: Path) -> PdfFile:
    """Open one PDF: page count, size, and fillable-form values. On failure, still
    return a PdfFile with `error` set so the caller can report it and skip Claude.
    """
    size = path.stat().st_size
    try:
        reader = PdfReader(path)
        return PdfFile(
            path=path, page_count=len(reader.pages), size_bytes=size, form_values=_form_values(reader)
        )
    except Exception as e:
        return PdfFile(path=path, page_count=None, size_bytes=size, error=f"Could not open PDF: {e}")


def _form_values(reader: PdfReader) -> dict[str, str]:
    """Pull stored values from AcroForm fields (text, checkboxes, dropdowns).

    Unchecked boxes often store `/Off`; those become empty strings. Other field
    types (signatures, etc.) are skipped. A broken form dictionary yields {}.
    """
    try:
        fields = reader.get_fields() or {}
    except Exception:
        return {}
    values = {}
    for name, f in fields.items():
        if f.get("/FT") not in ("/Tx", "/Btn", "/Ch"):  # text, checkbox/radio, dropdown
            continue
        value = f.get("/V")
        values[name] = "" if value is None or value == "/Off" else str(value).lstrip("/")
    return values
