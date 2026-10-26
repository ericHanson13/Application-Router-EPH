"""Find PDFs in a folder and read basic facts about them locally (no API calls)."""

from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader


@dataclass
class PdfFile:
    path: Path
    page_count: int | None
    size_bytes: int
    error: str | None = None
    # Values typed into a fillable PDF form, by field name. Empty for scanned or flat PDFs.
    form_values: dict[str, str] = field(default_factory=dict)


def find_pdfs(folder: Path, recursive: bool = False) -> list[PdfFile]:
    pattern = "**/*" if recursive else "*"
    paths = sorted(
        p for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() == ".pdf"
    )
    return [inspect_pdf(p) for p in paths]


def inspect_pdf(path: Path) -> PdfFile:
    size = path.stat().st_size
    try:
        reader = PdfReader(path)
        return PdfFile(
            path=path, page_count=len(reader.pages), size_bytes=size, form_values=_form_values(reader)
        )
    except Exception as e:
        return PdfFile(path=path, page_count=None, size_bytes=size, error=f"Could not open PDF: {e}")


def _form_values(reader: PdfReader) -> dict[str, str]:
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
