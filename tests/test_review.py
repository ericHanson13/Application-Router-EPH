"""Tests for steps 1 to 4. These never call the real Claude API. Run:  python -m pytest"""

import json
from types import SimpleNamespace

from pypdf import PdfWriter

from permit_review import claude_client, cli
from permit_review.models import DocumentOverview, FormField, RequiredAttachment, Section
from permit_review.scanner import PdfFile, find_pdfs


def write_pdf(path, pages=2):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=612, height=792)
    with open(path, "wb") as f:
        w.write(f)


class FakeClient:
    """Stands in for anthropic.Anthropic and records what was sent."""

    def __init__(self, overview):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))
        self._overview = overview

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", parsed_output=self._overview)


OVERVIEW = DocumentOverview(
    summary="A residential permit application followed by a site plan.",
    is_permit_application=True,
    sections=[
        Section(title="Building permit application", kind="application_form", start_page=1, end_page=2),
        Section(title="Site plan", kind="attachment", start_page=3, end_page=3),
    ],
    required_attachments=[
        RequiredAttachment(
            name="Site plan", requirement_text="Site plan showing property lines", listed_on_page=2,
            condition="", applies="yes", applies_reason="",
            satisfied=True, found_on_pages=[3], evidence="Page 3 is titled 'Site plan'.",
        ),
        RequiredAttachment(
            name="Engineering letter", requirement_text="Engineer's letter if span exceeds 20 ft", listed_on_page=2,
            condition="if the span exceeds 20 ft", applies="no", applies_reason="The patio span is 12 ft.",
            satisfied=False, found_on_pages=[], evidence="Not included.",
        ),
        RequiredAttachment(
            name="Construction drawings", requirement_text="Construction drawings", listed_on_page=2,
            condition="", applies="yes", applies_reason="",
            satisfied=False, found_on_pages=[], evidence="No page is labeled as drawings.",
        ),
    ],
    form_fields=[
        FormField(label="Owner name", page=1, value="Jordan Alvarez", status="filled", required=True, note=""),
        FormField(label="Contractor phone", page=2, value="", status="blank", required=True, note=""),
        FormField(label="Fax", page=2, value="", status="blank", required=False, note="Marked optional"),
        FormField(label="Date", page=2, value="1O/1?", status="unclear", required=True, note="Date is illegible"),
    ],
)


def test_find_pdfs_counts_pages_and_skips_other_files(tmp_path):
    write_pdf(tmp_path / "b.pdf", pages=3)
    write_pdf(tmp_path / "a.PDF", pages=1)
    (tmp_path / "notes.txt").write_text("not a pdf")
    (tmp_path / "broken.pdf").write_bytes(b"not really a pdf")

    pdfs = find_pdfs(tmp_path)
    assert [p.path.name for p in pdfs] == ["a.PDF", "b.pdf", "broken.pdf"]
    assert [p.page_count for p in pdfs] == [1, 3, None]
    assert pdfs[2].error


def test_describe_pdf_sends_the_pdf_to_claude(tmp_path):
    write_pdf(tmp_path / "permit.pdf", pages=3)
    client = FakeClient(OVERVIEW)

    result = claude_client.describe_pdf(client, find_pdfs(tmp_path)[0])

    assert result == OVERVIEW
    content = client.calls[0]["messages"][0]["content"]
    assert content[0]["type"] == "document"
    assert content[0]["source"]["media_type"] == "application/pdf"


def test_cli_saves_results(tmp_path, capsys):
    folder = tmp_path / "permits"
    folder.mkdir()
    write_pdf(folder / "permit.pdf", pages=3)
    out = tmp_path / "reports"

    code = cli.main([str(folder), "--out", str(out)], client=FakeClient(OVERVIEW))

    assert code == 0
    saved = json.loads(next(out.glob("review-*.json")).read_text())
    overview = saved["files"][0]["overview"]
    assert overview["sections"][1]["title"] == "Site plan"
    assert [a["name"] for a in overview["required_attachments"]] == [
        "Site plan", "Engineering letter", "Construction drawings",
    ]
    printed = capsys.readouterr().out
    assert "ok  Site plan (p3): Page 3 is titled 'Site plan'." in printed
    assert "-  Engineering letter: Not included." in printed
    assert "applies here: no. The patio span is 12 ft." in printed
    assert "MISSING  Construction drawings: No page is labeled as drawings." in printed
    assert saved["files"][0]["missing_attachments"] == ["Construction drawings"]
    assert saved["files"][0]["result"] == "FAIL"
    assert "RESULT: FAIL (field 'Contractor phone' blank; field 'Date' unclear; missing Construction drawings)" in printed
    assert saved["files"][0]["incomplete_fields"] == ["Contractor phone", "Date"]
    assert "Form fields: 4 checked, INCOMPLETE (2 missing)" in printed
    assert "! Contractor phone (p2) is blank" in printed
    assert "! Date (p2) is unclear: Date is illegible" in printed
    assert "Fax" not in printed


def test_dry_run_needs_no_api_key(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    write_pdf(tmp_path / "permit.pdf")

    assert cli.main([str(tmp_path), "--dry-run"]) == 0
    assert "permit.pdf  (2 pages)" in capsys.readouterr().out


def test_fillable_form_values_are_given_to_claude(tmp_path):
    write_pdf(tmp_path / "permit.pdf")
    pdf = PdfFile(path=tmp_path / "permit.pdf", page_count=2, size_bytes=100,
                  form_values={"OwnerName": "Jordan Alvarez", "ContractorPhone": ""})
    client = FakeClient(OVERVIEW)

    claude_client.describe_pdf(client, pdf)

    prompt = client.calls[0]["messages"][0]["content"][1]["text"]
    assert "- OwnerName: Jordan Alvarez" in prompt
    assert "- ContractorPhone: (empty)" in prompt


def test_flat_pdf_prompt_has_no_form_values(tmp_path):
    write_pdf(tmp_path / "permit.pdf")
    client = FakeClient(OVERVIEW)

    claude_client.describe_pdf(client, find_pdfs(tmp_path)[0])

    assert "fillable form" not in client.calls[0]["messages"][0]["content"][1]["text"]


def test_packet_passes_when_form_complete_and_attachments_present():
    complete = OVERVIEW.model_copy(update={
        "form_fields": [f for f in OVERVIEW.form_fields if f.status == "filled"],
        "required_attachments": [a for a in OVERVIEW.required_attachments if a.name != "Construction drawings"],
    })
    assert complete.passed()
    assert not complete.model_copy(update={"is_permit_application": False}).passed()


def test_attachment_with_unclear_condition_counts_as_missing():
    unclear = OVERVIEW.required_attachments[1].model_copy(update={"applies": "unclear"})
    overview = OVERVIEW.model_copy(update={"required_attachments": [unclear]})
    assert overview.missing_attachments() == [unclear]
