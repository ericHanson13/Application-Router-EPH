"""Builds sample_permit_packet.pdf, a made-up packet for testing.

It has a 2-page application with one blank field, and is missing one of the
three required attachments (construction drawings), so later steps should fail it.
Needs reportlab:  pip install reportlab
"""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = Path(__file__).with_name("sample_permit_packet.pdf")
W, H = letter


def field(c, y, label, value):
    c.setFont("Helvetica", 10)
    c.drawString(72, y, label)
    c.line(250, y - 2, 540, y - 2)
    if value:
        c.setFont("Helvetica-Oblique", 11)
        c.drawString(255, y, value)


def main():
    c = canvas.Canvas(str(OUT), pagesize=letter)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, H - 72, "CITY OF SAMPLEVILLE - BUILDING PERMIT APPLICATION")
    c.setFont("Helvetica", 9)
    c.drawString(72, H - 88, "Department of Building Safety  ·  Form BP-100  ·  Page 1 of 2")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, H - 120, "Section A - Property")
    y = H - 145
    for label, value in [
        ("Site address", "1427 Maple Ridge Dr, Sampleville, TX 75001"),
        ("Parcel number", "SV-0042-118"),
        ("Zoning district", "R-1 Single Family"),
        ("Owner name", "Jordan Alvarez"),
        ("Owner phone", "(555) 201-4477"),
    ]:
        field(c, y, label, value)
        y -= 24
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y - 10, "Section B - Project")
    y -= 35
    for label, value in [
        ("Type of work", "Addition - covered rear patio"),
        ("Description of work", "12 ft x 20 ft attached patio cover with slab"),
        ("Estimated valuation ($)", "18,500"),
        ("Square footage", "240"),
    ]:
        field(c, y, label, value)
        y -= 24
    c.showPage()

    c.setFont("Helvetica", 9)
    c.drawString(72, H - 60, "Form BP-100  ·  Page 2 of 2")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, H - 90, "Section C - Contractor")
    y = H - 115
    for label, value in [
        ("Contractor company", "Lone Star Patio Builders LLC"),
        ("Contractor license number", "TX-RC-58213"),
        ("Contractor phone", ""),  # left blank on purpose
    ]:
        field(c, y, label, value)
        y -= 24
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y - 10, "Section D - Required attachments")
    c.setFont("Helvetica", 10)
    y -= 32
    c.drawString(72, y, "Attach the following documents after this form. Incomplete applications will be returned.")
    y -= 20
    for item in [
        "1. Site plan showing property lines, setbacks and the proposed work",
        "2. Construction drawings (framing plan and elevations)",
        "3. Copy of the contractor's current license",
    ]:
        c.drawString(90, y, item)
        y -= 18
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y - 20, "Section E - Signature")
    y -= 45
    field(c, y, "Applicant signature", "Jordan Alvarez")
    field(c, y - 24, "Date", "10/14/2026")
    c.showPage()

    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, H - 72, "SITE PLAN - 1427 Maple Ridge Dr")
    c.rect(100, 200, 400, 450)  # lot
    c.rect(180, 380, 220, 160)  # house
    c.setDash(4, 3)
    c.rect(220, 300, 140, 80)  # patio
    c.setDash()
    c.setFont("Helvetica", 9)
    c.drawString(250, 335, "Proposed patio 12' x 20'")
    c.drawString(260, 455, "Existing house")
    c.drawString(105, 655, "Property line")
    c.drawString(225, 285, "Rear setback 25'")
    c.drawString(72, 170, "Scale 1\" = 20'  ·  North up")
    c.showPage()

    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, H - 72, "TEXAS RESIDENTIAL CONTRACTOR LICENSE")
    c.setFont("Helvetica", 11)
    for i, line in enumerate([
        "Licensee: Lone Star Patio Builders LLC",
        "License number: TX-RC-58213",
        "Class: Residential Remodeling",
        "Issued: 03/01/2025     Expires: 02/28/2027",
    ]):
        c.drawString(72, H - 110 - i * 20, line)
    c.showPage()

    c.save()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
