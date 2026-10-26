"""Shapes of what Claude returns. Claude's answers are validated against these."""

from typing import Literal

from pydantic import BaseModel, Field


class Section(BaseModel):
    title: str = Field(description="What this part of the PDF is, e.g. 'Building permit application' or 'Site plan'")
    kind: Literal["application_form", "attachment", "other"]
    start_page: int
    end_page: int


class RequiredAttachment(BaseModel):
    name: str = Field(description="Short name of the document, e.g. 'Site plan'")
    requirement_text: str = Field(description="The form's wording for this requirement, quoted as closely as possible")
    listed_on_page: int = Field(description="Page of the PDF where the form lists this requirement")
    condition: str = Field(
        description="When the form says this is only needed in some cases (e.g. 'if work exceeds $5,000'), "
        "that condition; otherwise an empty string"
    )
    applies: Literal["yes", "no", "unclear"] = Field(
        description="Whether this requirement applies to this application, judged from the answers on the form. "
        "'yes' for unconditional requirements"
    )
    applies_reason: str = Field(description="One sentence on why it applies or not; empty for unconditional requirements")
    satisfied: bool = Field(description="True if a page after the form is titled or clearly labeled as this document")
    found_on_pages: list[int] = Field(description="Pages holding this document; empty if missing")
    evidence: str = Field(description="One sentence: the page title that matched, or what is missing")


class FormField(BaseModel):
    label: str = Field(description="The field's label as printed on the form")
    page: int
    value: str = Field(description="What the applicant entered, or an empty string if nothing")
    status: Literal["filled", "blank", "unclear"] = Field(
        description="'unclear' when something is entered but can't be read or doesn't answer the question"
    )
    required: bool = Field(
        description="False for fields marked optional, for office use only, or conditional ('if applicable') "
        "where the condition doesn't apply to this application"
    )
    note: str = Field(description="Why a blank field is not required, or what is unclear; otherwise empty")


class DocumentOverview(BaseModel):
    summary: str = Field(description="Two or three sentences on what this PDF contains")
    is_permit_application: bool = Field(description="True if the PDF contains a permit application form")
    sections: list[Section] = Field(description="Every distinct part of the PDF, in page order")
    required_attachments: list[RequiredAttachment] = Field(
        description="Every document the application form says must be attached to the packet, including ones "
        "mentioned only in instructions or footnotes. Only documents to attach: not statements, code-compliance "
        "requirements, fees or other conditions. Empty if there is no application form."
    )
    form_fields: list[FormField] = Field(
        description="Every field on the application form the applicant is expected to fill in, including "
        "signatures, dates and checkboxes, in page order. Empty if there is no application form."
    )

    def incomplete_fields(self) -> list[FormField]:
        """Required fields that are blank or unreadable: the form fails if there are any."""
        return [f for f in self.form_fields if f.required and f.status != "filled"]

    def missing_attachments(self) -> list[RequiredAttachment]:
        """Required items that apply (or might) and aren't in the packet: the packet fails if there are any."""
        return [a for a in self.required_attachments if a.applies != "no" and not a.satisfied]

    def passed(self) -> bool:
        return self.is_permit_application and not self.incomplete_fields() and not self.missing_attachments()
