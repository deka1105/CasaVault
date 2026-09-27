"""Generate professional-looking PDF test leases for CasaVault demo."""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.pdfgen import canvas

OUTDIR = os.path.dirname(os.path.abspath(__file__))

NAVY = HexColor("#1a2744")
DARK_GRAY = HexColor("#333333")
MID_GRAY = HexColor("#666666")
LIGHT_GRAY = HexColor("#e8e8e8")
ACCENT = HexColor("#2c5f8a")
RED_FLAG = HexColor("#c0392b")
GREEN_OK = HexColor("#27ae60")

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    "LeaseTitle", parent=styles["Title"],
    fontSize=22, leading=28, textColor=NAVY,
    spaceAfter=4, alignment=TA_CENTER,
    fontName="Helvetica-Bold",
))
styles.add(ParagraphStyle(
    "LeaseSubtitle", parent=styles["Normal"],
    fontSize=11, leading=14, textColor=MID_GRAY,
    alignment=TA_CENTER, spaceAfter=20,
    fontName="Helvetica",
))
styles.add(ParagraphStyle(
    "SectionHead", parent=styles["Heading2"],
    fontSize=13, leading=17, textColor=NAVY,
    spaceBefore=18, spaceAfter=8,
    fontName="Helvetica-Bold",
    borderWidth=0, borderPadding=0,
))
styles.add(ParagraphStyle(
    "SubSection", parent=styles["Heading3"],
    fontSize=11, leading=14, textColor=ACCENT,
    spaceBefore=12, spaceAfter=6,
    fontName="Helvetica-Bold",
))
styles.add(ParagraphStyle(
    "Body", parent=styles["Normal"],
    fontSize=10, leading=14, textColor=DARK_GRAY,
    spaceAfter=6, alignment=TA_JUSTIFY,
    fontName="Helvetica",
))
styles.add(ParagraphStyle(
    "BodyBold", parent=styles["Normal"],
    fontSize=10, leading=14, textColor=DARK_GRAY,
    spaceAfter=6, fontName="Helvetica-Bold",
))
styles.add(ParagraphStyle(
    "Small", parent=styles["Normal"],
    fontSize=8, leading=10, textColor=MID_GRAY,
    spaceAfter=4, fontName="Helvetica",
))
styles.add(ParagraphStyle(
    "CheckItem", parent=styles["Normal"],
    fontSize=10, leading=14, textColor=DARK_GRAY,
    leftIndent=20, spaceAfter=3,
    fontName="Helvetica",
))
styles.add(ParagraphStyle(
    "Warning", parent=styles["Normal"],
    fontSize=10, leading=14, textColor=RED_FLAG,
    spaceAfter=6, fontName="Helvetica-Bold",
    leftIndent=10, borderWidth=1, borderColor=RED_FLAG,
    borderPadding=6, backColor=HexColor("#fdf2f2"),
))
styles.add(ParagraphStyle(
    "Footer", parent=styles["Normal"],
    fontSize=7, leading=9, textColor=MID_GRAY,
    alignment=TA_CENTER, fontName="Helvetica",
))
styles.add(ParagraphStyle(
    "SignLine", parent=styles["Normal"],
    fontSize=10, leading=20, textColor=DARK_GRAY,
    fontName="Helvetica",
))


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY,
                       spaceBefore=6, spaceAfter=6)

def thick_hr():
    return HRFlowable(width="100%", thickness=1.5, color=NAVY,
                       spaceBefore=10, spaceAfter=10)

def section(title):
    return Paragraph(title.upper(), styles["SectionHead"])

def subsection(title):
    return Paragraph(title, styles["SubSection"])

def body(text):
    return Paragraph(text, styles["Body"])

def bold(text):
    return Paragraph(text, styles["BodyBold"])

def check(checked, text):
    mark = "&#x2611;" if checked else "&#x2610;"
    return Paragraph(f"{mark}&nbsp;&nbsp;{text}", styles["CheckItem"])

def warning(text):
    return Paragraph(text, styles["Warning"])

def sign_block(name, date, label="Resident"):
    return [
        Spacer(1, 20),
        hr(),
        Table(
            [[f"{label} Signature: {name}", f"Date: {date}"]],
            colWidths=[3.5*inch, 2.5*inch],
            style=TableStyle([
                ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
                ("FONTSIZE", (0,0), (-1,-1), 10),
                ("TEXTCOLOR", (0,0), (-1,-1), DARK_GRAY),
                ("BOTTOMPADDING", (0,0), (-1,-1), 2),
            ])
        ),
    ]

def kv_table(rows, col1=2.2*inch, col2=4.3*inch):
    data = [[Paragraph(f"<b>{k}</b>", styles["Body"]),
             Paragraph(v, styles["Body"])] for k, v in rows]
    return Table(data, colWidths=[col1, col2], style=TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, LIGHT_GRAY),
    ]))


def header_footer(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFillColor(NAVY)
    canvas_obj.rect(0, letter[1] - 40, letter[0], 40, fill=True, stroke=False)
    canvas_obj.setFillColor(white)
    canvas_obj.setFont("Helvetica-Bold", 9)
    canvas_obj.drawString(0.75*inch, letter[1] - 26, doc.title or "")
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.setFillColor(MID_GRAY)
    canvas_obj.drawCentredString(letter[0]/2, 0.4*inch,
        f"Page {doc.page}  |  This document is for demonstration purposes only  |  Not a real lease")
    canvas_obj.restoreState()


def build_pdf(filename, title, subtitle, story_fn):
    path = os.path.join(OUTDIR, filename)
    doc = SimpleDocTemplate(
        path, pagesize=letter,
        topMargin=0.9*inch, bottomMargin=0.75*inch,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        title=title,
    )
    story = [
        Spacer(1, 10),
        Paragraph(title, styles["LeaseTitle"]),
        Paragraph(subtitle, styles["LeaseSubtitle"]),
        thick_hr(),
    ]
    story_fn(story)
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"  Created: {path}")


# ============================================================================
# LEASE 1 — COMPLIANT (Chestnut Hill)
# ============================================================================
def lease_01(story):
    story.append(section("Parties"))
    story.append(kv_table([
        ("Landlord/Owner:", "Chestnut Hill Properties LLC"),
        ("Management Office:", "Chestnut Hill Gardens Leasing Office, 8200 Germantown Avenue, Philadelphia PA 19118"),
        ("Email:", "leasing@chestnuthillgardens.com"),
        ("Resident:", "Maria Torres"),
    ]))

    story.append(section("Lease Term"))
    story.append(kv_table([
        ("Property Address:", "8200 Germantown Avenue, Unit 3B, Philadelphia, PA 19118"),
        ("Lease Begins:", "June 1, 2026"),
        ("Lease Ends:", "May 31, 2027"),
        ("Tenancy Year:", "1 (first year)"),
        ("Term:", "12 months"),
    ]))

    story.append(section("Rent"))
    story.append(kv_table([
        ("Monthly Rent:", "$1,450.00"),
        ("Due Date:", "1st of each month"),
        ("Late Fee:", "$50.00 after 5-day grace period"),
        ("Returned Check Fee:", "$30.00"),
    ]))

    story.append(section("Security Deposit"))
    story.append(kv_table([
        ("Deposit Amount:", "$1,450.00"),
        ("Deposit in Months' Rent:", "1.0 month (within two-month first-year cap)"),
        ("Escrow Bank:", "Citizens Bank"),
        ("Bank Address:", "8100 Germantown Avenue, Philadelphia, PA 19118"),
        ("Amount Deposited:", "$1,450.00"),
        ("Pet Deposit:", "None — no pets permitted"),
    ]))

    story.append(section("Utilities"))
    story.append(kv_table([
        ("Landlord Pays:", "Water, sewer, trash collection"),
        ("Resident Pays:", "Electric, gas, internet/cable"),
    ]))

    story.append(section("Insurance"))
    story.append(body("Resident is required to maintain renter's insurance with minimum personal liability coverage of <b>$100,000</b> throughout the lease term."))

    story.append(section("Early Termination / Buy-Out"))
    story.append(body("Resident may terminate this lease early by providing 60 days' written notice and paying a buy-out fee equal to two (2) months' rent (<b>$2,900.00</b>). All other lease obligations must be current."))

    story.append(section("Move-Out Notice"))
    story.append(body("Resident must provide at least <b>60 days'</b> written notice before moving out."))

    # --- Page break for acknowledgment ---
    story.append(PageBreak())

    story.append(section("Philadelphia Acknowledgment of Receipt of Required Documents"))
    story.append(body("Property: 8200 Germantown Avenue, Unit 3B, Philadelphia, PA 19118"))
    story.append(Spacer(1, 8))
    story.append(body("I, the undersigned Resident, acknowledge that at or before the signing of this lease, I received the following from the Landlord:"))
    story.append(Spacer(1, 6))
    story.append(check(True, "Certificate of Rental Suitability issued by Philadelphia Licenses and Inspections, dated April 15, 2026 (within 60 days of lease start)"))
    story.append(check(True, "Partners in Good Housing handbook published by the City of Philadelphia"))
    story.append(check(True, "Lead-based paint disclosure and EPA pamphlet (building constructed 1952)"))
    story.append(check(True, "Bed bug disclosure addendum"))
    story.append(Spacer(1, 10))
    story.append(bold("Rental License Status"))
    story.append(kv_table([
        ("License Status:", "Active"),
        ("License Expiration:", "December 31, 2026"),
    ]))
    story.extend(sign_block("Maria Torres", "May 28, 2026"))

    story.append(section("Resident Fees Disclosure"))
    story.append(kv_table([
        ("Application Fee:", "$50.00"),
        ("Administrative/Move-in Fee:", "$150.00"),
        ("Parking:", "$75.00/month (optional, 1 space)"),
    ]))

    story.append(section("Inventory and Condition — Unit 3B"))
    story.append(body("<b>Move-in date:</b> June 1, 2026"))
    story.append(kv_table([
        ("Living Room:", "Good condition. Minor scuff on baseboard near front door."),
        ("Kitchen:", "Good condition. All appliances functional."),
        ("Bedroom:", "Good condition. Small nail hole above window."),
        ("Bathroom:", "Good condition. Caulk around tub shows minor wear."),
        ("General:", "Smoke detectors tested and functional. All locks operational."),
    ]))

    story.append(section("Lead-Based Paint Disclosure"))
    story.append(kv_table([
        ("Building Year Built:", "1952"),
        ("Disclosure Provided:", "Yes"),
        ("EPA Pamphlet Provided:", "Yes"),
    ]))


# ============================================================================
# LEASE 2 — MINOR: No Certificate (West Philly)
# ============================================================================
def lease_02(story):
    story.append(section("Parties"))
    story.append(kv_table([
        ("Landlord/Owner:", "James Whitfield (individual owner)"),
        ("Contact:", "4520 Baltimore Avenue, Philadelphia PA 19143"),
        ("Email:", "jwhitfield.rentals@gmail.com"),
        ("Resident:", "Kevin Okafor"),
    ]))

    story.append(section("Lease Term"))
    story.append(kv_table([
        ("Property Address:", "4520 Baltimore Avenue, Unit 2A, Philadelphia, PA 19143"),
        ("Lease Begins:", "July 1, 2026"),
        ("Lease Ends:", "June 30, 2027"),
        ("Tenancy Year:", "1 (first year)"),
        ("Term:", "12 months"),
    ]))

    story.append(section("Rent"))
    story.append(kv_table([
        ("Monthly Rent:", "$1,200.00"),
        ("Due Date:", "1st of each month"),
        ("Late Fee:", "$50.00 after 5-day grace period"),
        ("Returned Check Fee:", "$25.00"),
    ]))

    story.append(section("Security Deposit"))
    story.append(kv_table([
        ("Deposit Amount:", "$1,200.00"),
        ("Deposit in Months' Rent:", "1.0 month"),
        ("Pet Deposit:", "$300.00 (one cat permitted)"),
        ("Combined Total:", "$1,500.00 (1.25 months' rent — within two-month cap)"),
        ("Escrow Bank:", "TD Bank"),
        ("Bank Address:", "4400 Chestnut Street, Philadelphia, PA 19104"),
        ("Amount Deposited:", "$1,500.00"),
    ]))

    story.append(section("Utilities"))
    story.append(kv_table([
        ("Landlord Pays:", "Water, sewer, trash"),
        ("Resident Pays:", "Electric, gas, internet"),
    ]))

    story.append(section("Insurance"))
    story.append(body("Renter's insurance is recommended but not required."))

    story.append(section("Early Termination"))
    story.append(body("No early termination option. Resident is responsible for rent through the full lease term or until a replacement tenant is found by the landlord."))

    story.append(section("Move-Out Notice"))
    story.append(body("Resident must provide at least <b>30 days'</b> written notice before moving out."))

    # --- Acknowledgment ---
    story.append(PageBreak())
    story.append(section("Signing Acknowledgment"))
    story.append(body("Property: 4520 Baltimore Avenue, Unit 2A, Philadelphia, PA 19143"))
    story.append(Spacer(1, 6))
    story.append(body("I, the undersigned Resident, acknowledge receipt of:"))
    story.append(Spacer(1, 6))
    story.append(check(True, "Lead-based paint disclosure (building constructed 1928)"))
    story.append(check(True, "Bed bug disclosure addendum"))
    story.append(check(False, "<b>Certificate of Rental Suitability — NOT PROVIDED at signing</b>"))
    story.append(check(False, "<b>Partners in Good Housing handbook — NOT PROVIDED at signing</b>"))
    story.append(Spacer(1, 8))
    story.append(warning('NOTE: The landlord stated that the Certificate of Rental Suitability and Partners in Good Housing handbook would be provided "within a few weeks after move-in." As of the signing date, neither document has been received.'))
    story.append(Spacer(1, 8))
    story.append(bold("Rental License Status"))
    story.append(kv_table([
        ("License Status:", "Active"),
        ("License Expiration:", "March 31, 2027"),
    ]))
    story.extend(sign_block("Kevin Okafor", "June 25, 2026"))

    story.append(section("Resident Fees Disclosure"))
    story.append(kv_table([
        ("Application Fee:", "$35.00"),
        ("Administrative Fee:", "$0"),
        ("Other Fees:", "None"),
    ]))

    story.append(section("Inventory and Condition — Unit 2A"))
    story.append(body("<b>Move-in date:</b> July 1, 2026"))
    story.append(kv_table([
        ("Living Room:", "Fair condition. Paint peeling near window frame. Hardwood floor scratched near radiator."),
        ("Kitchen:", "Good condition. Refrigerator has a dent on the door. All appliances work."),
        ("Bedroom:", "Good condition."),
        ("Bathroom:", "Caulk around tub needs replacement. Exhaust fan is noisy but operational."),
        ("General:", "Smoke detectors functional. Front door deadbolt is stiff."),
    ]))

    story.append(section("Lead-Based Paint Disclosure"))
    story.append(kv_table([
        ("Building Year Built:", "1928"),
        ("Disclosure Provided:", "Yes"),
        ("EPA Pamphlet Provided:", "Yes"),
    ]))


# ============================================================================
# LEASE 3 — MINOR: No Escrow Disclosure (Fishtown)
# ============================================================================
def lease_03(story):
    story.append(section("Parties"))
    story.append(kv_table([
        ("Landlord/Owner:", "Robert and Susan Chen (individual owners)"),
        ("Contact:", "Susan Chen, 267-555-0142, susanchen.properties@gmail.com"),
        ("Resident:", "Ashley Williams"),
    ]))

    story.append(section("Lease Term"))
    story.append(kv_table([
        ("Property Address:", "1835 Frankford Avenue, Unit 1R, Philadelphia, PA 19125"),
        ("Lease Begins:", "August 1, 2026"),
        ("Lease Ends:", "July 31, 2027"),
        ("Tenancy Year:", "1 (first year)"),
        ("Term:", "12 months"),
    ]))

    story.append(section("Rent"))
    story.append(kv_table([
        ("Monthly Rent:", "$1,650.00"),
        ("Due Date:", "1st of each month"),
        ("Late Fee:", "$75.00 after 5-day grace period"),
        ("Returned Check Fee:", "$35.00"),
        ("Rent Concession:", "$200.00 off first month's rent"),
    ]))

    story.append(section("Security Deposit"))
    story.append(kv_table([
        ("Deposit Amount:", "$1,650.00"),
        ("Deposit in Months' Rent:", "1.0 month"),
        ("Pet Deposit:", "None — no pets permitted"),
    ]))
    story.append(Spacer(1, 6))
    story.append(warning("NOTE: The security deposit is held by the Landlord. No separate escrow account information has been provided to the Resident at the time of signing. The Landlord stated they will provide escrow details at a later date. No bank name or address has been disclosed."))

    story.append(section("Utilities"))
    story.append(kv_table([
        ("Landlord Pays:", "Water, sewer, trash"),
        ("Resident Pays:", "Electric, gas, internet/cable"),
    ]))

    story.append(section("Insurance"))
    story.append(body("Resident is required to maintain renter's insurance with minimum personal liability coverage of <b>$100,000</b> throughout the lease term."))

    story.append(section("Early Termination / Buy-Out"))
    story.append(body("Resident may terminate this lease early by providing 60 days' written notice and paying a buy-out fee equal to two (2) months' rent (<b>$3,300.00</b>)."))

    story.append(section("Move-Out Notice"))
    story.append(body("Resident must provide at least <b>60 days'</b> written notice before moving out."))

    # --- Acknowledgment ---
    story.append(PageBreak())
    story.append(section("Philadelphia Acknowledgment of Receipt of Required Documents"))
    story.append(body("Property: 1835 Frankford Avenue, Unit 1R, Philadelphia, PA 19125"))
    story.append(Spacer(1, 6))
    story.append(body("I, the undersigned Resident, acknowledge receipt of the following at or before lease signing:"))
    story.append(Spacer(1, 6))
    story.append(check(True, "Certificate of Rental Suitability issued by Philadelphia Licenses and Inspections, dated June 20, 2026"))
    story.append(check(True, "Partners in Good Housing handbook"))
    story.append(check(True, "Lead-based paint disclosure (building constructed 1920)"))
    story.append(check(True, "Bed bug disclosure addendum"))
    story.append(Spacer(1, 8))
    story.append(bold("Rental License Status"))
    story.append(kv_table([
        ("License Status:", "Active"),
        ("License Expiration:", "September 30, 2026"),
    ]))
    story.extend(sign_block("Ashley Williams", "July 25, 2026"))

    story.append(section("Resident Fees Disclosure"))
    story.append(kv_table([
        ("Application Fee:", "$50.00"),
        ("Administrative/Move-in Fee:", "$200.00"),
        ("Trash Valet:", "$15.00/month"),
        ("Parking:", "Not available"),
    ]))

    story.append(section("Inventory and Condition — Unit 1R"))
    story.append(body("<b>Move-in date:</b> August 1, 2026"))
    story.append(kv_table([
        ("Living Room:", "Good condition. One small crack in ceiling plaster."),
        ("Kitchen:", "Good condition. Dishwasher runs but is loud."),
        ("Bedroom 1:", "Good condition."),
        ("Bedroom 2:", "Fair. Closet door slides off track."),
        ("Bathroom:", "Good condition."),
        ("General:", "Smoke and CO detectors functional. All locks work."),
    ]))

    story.append(section("Lead-Based Paint Disclosure"))
    story.append(kv_table([
        ("Building Year Built:", "1920"),
        ("Disclosure Provided:", "Yes"),
        ("EPA Pamphlet Provided:", "Yes"),
    ]))


# ============================================================================
# LEASE 4 — MAJOR: Deposit Overcharge + Waiver (North Philly)
# ============================================================================
def lease_04(story):
    story.append(section("Parties"))
    story.append(kv_table([
        ("Landlord/Owner:", "Broad Street Holdings LLC"),
        ("Management Office:", "North Philly Residences, 2741 N Broad Street, Philadelphia PA 19132"),
        ("Email:", "office@northphillyresidences.com"),
        ("Resident:", "Darnell Jackson"),
    ]))

    story.append(section("Lease Term"))
    story.append(kv_table([
        ("Property Address:", "2741 North Broad Street, Unit 4F, Philadelphia, PA 19132"),
        ("Lease Begins:", "September 1, 2026"),
        ("Lease Ends:", "August 31, 2027"),
        ("Tenancy Year:", "1 (first year)"),
        ("Term:", "12 months"),
    ]))

    story.append(section("Rent"))
    story.append(kv_table([
        ("Monthly Rent:", "$950.00"),
        ("Due Date:", "1st of each month"),
        ("Late Fee:", "$100.00 after 3-day grace period"),
        ("Returned Check Fee:", "$50.00"),
    ]))

    story.append(section("Security Deposit"))
    story.append(warning("DEPOSIT AMOUNT: $2,850.00 — equivalent to THREE (3) months' rent. Pennsylvania law caps the first-year deposit at two months' rent (68 P.S. &sect; 250.511a(a))."))
    story.append(kv_table([
        ("Deposit Amount:", "$2,850.00"),
        ("Deposit in Months' Rent:", "3.0 months"),
        ("Pet Deposit:", "None"),
    ]))
    story.append(Spacer(1, 4))
    story.append(body("The security deposit is held by the Landlord's operating account. <b>No separate escrow account is maintained for the deposit.</b> No bank name or address has been disclosed to the Resident."))

    story.append(section("Utilities"))
    story.append(kv_table([
        ("Landlord Pays:", "Trash collection"),
        ("Resident Pays:", "Electric, gas, water, sewer, internet"),
    ]))

    story.append(section("Insurance"))
    story.append(body("Renter's insurance is not required."))

    story.append(section("Move-Out Notice"))
    story.append(body("Resident must provide at least <b>30 days'</b> written notice before moving out."))

    # --- Master Addendum with Waiver ---
    story.append(PageBreak())
    story.append(section("Master Addendum and Community Policies"))
    story.append(subsection("Section 12 — Waiver of Deposit Protections"))
    story.append(warning("This section purports to waive the tenant's deposit rights under Pennsylvania law. Under 68 P.S. &sect; 250.511a(f), any such waiver is void and unenforceable."))
    story.append(Spacer(1, 6))
    story.append(body("Resident acknowledges and agrees that:"))
    story.append(body("(a) The security deposit provisions of the Pennsylvania Landlord and Tenant Act of 1951, specifically 68 P.S. &sect; 250.511a, shall not apply to this tenancy."))
    story.append(body("(b) Resident waives any and all rights to the return of, or limitations on, the security deposit as provided under said statute."))
    story.append(body("(c) Resident waives the right to receive interest on the security deposit regardless of the duration of the tenancy."))
    story.append(body("(d) Upon vacating the premises, the Landlord shall have sole discretion in determining the disposition of the security deposit, and the Resident agrees to accept the Landlord's determination as final."))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Resident Initials: DJ&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Date: August 28, 2026", styles["SignLine"]))

    # --- Acknowledgment ---
    story.append(section("Philadelphia Acknowledgment of Receipt of Required Documents"))
    story.append(body("Property: 2741 North Broad Street, Unit 4F, Philadelphia, PA 19132"))
    story.append(Spacer(1, 6))
    story.append(check(True, "Certificate of Rental Suitability, dated August 10, 2026"))
    story.append(check(True, "Partners in Good Housing handbook"))
    story.append(check(True, "Lead-based paint disclosure (building constructed 1965)"))
    story.append(check(True, "Bed bug disclosure addendum"))
    story.append(Spacer(1, 8))
    story.append(bold("Rental License Status"))
    story.append(kv_table([
        ("License Status:", "Active"),
        ("License Expiration:", "February 28, 2027"),
    ]))
    story.extend(sign_block("Darnell Jackson", "August 28, 2026"))

    story.append(section("Resident Fees Disclosure"))
    story.append(kv_table([
        ("Application Fee:", "$75.00"),
        ("Administrative/Move-in Fee:", "$300.00"),
        ("Lock Change Fee:", "$100.00"),
        ("Common Area Maintenance:", "$25.00/month"),
    ]))

    story.append(section("Inventory and Condition — Unit 4F"))
    story.append(body("<b>Move-in date:</b> September 1, 2026"))
    story.append(kv_table([
        ("Living Room:", "Fair condition. Carpet stained near entryway. Patched hole in wall near window."),
        ("Kitchen:", "Dated. Cabinet door loose on upper right. Stove burner #3 does not ignite."),
        ("Bedroom:", "Fair condition. Window does not lock properly."),
        ("Bathroom:", "Toilet runs intermittently. Tile cracked near shower base."),
        ("General:", "Smoke detector functional. Deadbolt works. Intercom non-functional."),
    ]))

    story.append(section("Lead-Based Paint Disclosure"))
    story.append(kv_table([
        ("Building Year Built:", "1965"),
        ("Disclosure Provided:", "Yes"),
        ("EPA Pamphlet Provided:", "Yes"),
    ]))


# ============================================================================
# LEASE 5 — MAJOR: No License + No Cert + No Escrow (Kensington)
# ============================================================================
def lease_05(story):
    story.append(section("Parties"))
    story.append(kv_table([
        ("Landlord/Owner:", "Victor Morano"),
        ("Contact:", "215-555-0198 (text preferred)"),
        ("Resident:", "Sandra Reyes"),
    ]))

    story.append(section("Lease Term"))
    story.append(kv_table([
        ("Property Address:", "3127 Kensington Avenue, Second Floor, Philadelphia, PA 19134"),
        ("Lease Begins:", "October 1, 2026"),
        ("Lease Ends:", "September 30, 2027"),
        ("Tenancy Year:", "1 (first year)"),
        ("Term:", "12 months"),
    ]))

    story.append(section("Rent"))
    story.append(kv_table([
        ("Monthly Rent:", "$1,100.00"),
        ("Due Date:", "1st of each month"),
        ("Late Fee:", "$150.00 — charged on the 2nd day (no grace period stated)"),
        ("Returned Check Fee:", "$75.00"),
    ]))

    story.append(section("Security Deposit"))
    story.append(kv_table([
        ("Deposit Amount:", "$2,200.00"),
        ("Deposit in Months' Rent:", "2.0 months"),
        ("Pet Deposit:", "None — no pets permitted under any circumstances"),
    ]))
    story.append(Spacer(1, 4))
    story.append(warning("The security deposit is held by the Landlord personally. No escrow account is maintained. No bank name or address has been provided to the Resident."))

    story.append(section("Utilities"))
    story.append(kv_table([
        ("Landlord Pays:", "None"),
        ("Resident Pays:", "All utilities — electric, gas, water, sewer, trash, internet"),
    ]))

    story.append(section("Move-Out Notice"))
    story.append(body("Resident must provide 60 days' written notice before the end of the lease term. Failure to provide notice results in automatic month-to-month renewal at a rate of <b>$1,250.00/month</b>."))

    # --- Documents at Signing ---
    story.append(PageBreak())
    story.append(section("Documents Provided at Signing"))
    story.append(body("Property: 3127 Kensington Avenue, Second Floor, Philadelphia PA 19134"))
    story.append(Spacer(1, 6))
    story.append(bold("Documents received:"))
    story.append(check(True, "Lease agreement (this document)"))
    story.append(check(True, "Lead-based paint disclosure (building constructed approximately 1915)"))
    story.append(Spacer(1, 8))
    story.append(bold("Documents NOT received:"))
    story.append(check(False, '<b>Certificate of Rental Suitability — NOT PROVIDED.</b> The landlord stated the property "doesn\'t need one" and that the requirement "only applies to big buildings."'))
    story.append(check(False, "<b>Partners in Good Housing handbook — NOT PROVIDED.</b> The landlord stated he was not familiar with this document."))
    story.append(check(False, "<b>Bed bug disclosure addendum — NOT PROVIDED.</b>"))

    story.append(Spacer(1, 10))
    story.append(section("Rental License Status"))
    story.append(warning('When asked about the rental license, the Landlord stated that the license "is being renewed" and that it will be "taken care of soon." No copy of a current, valid Philadelphia Rental License was provided or shown to the Resident. A search of Philadelphia L&amp;I records on September 28, 2026 shows no active rental license for this address. The most recent license expired on March 31, 2025 — over 18 months ago.'))
    story.extend(sign_block("Sandra Reyes", "September 27, 2026"))

    # --- Problematic lease terms ---
    story.append(section("Additional Lease Terms"))

    story.append(subsection("Section 8 — Liability and Condition of Premises"))
    story.append(body('The Resident accepts the premises in "as-is" condition. The Landlord makes no representations regarding the habitability, safety, or code compliance of the unit. <b>Resident waives the right to withhold rent for any reason related to the condition of the premises.</b>'))

    story.append(subsection("Section 9 — Repairs"))
    story.append(body('All repair requests must be made in writing and delivered by hand to the Landlord at 3127 Kensington Avenue. The Landlord will address repairs "at his earliest convenience." The Landlord is not responsible for repairs resulting from normal wear and tear during the first 90 days of occupancy.'))

    story.append(subsection("Section 10 — Entry"))
    story.append(body("The Landlord reserves the right to enter the premises at any time with or without notice for the purpose of inspection, maintenance, or showing the unit to prospective tenants or buyers."))

    # --- Condition Report ---
    story.append(PageBreak())
    story.append(section("Condition at Move-In"))
    story.append(body("<b>Unit:</b> Second Floor, 3127 Kensington Avenue"))
    story.append(body("<b>Move-in date:</b> October 1, 2026"))
    story.append(Spacer(1, 6))

    story.append(kv_table([
        ("Living Room:", "Multiple ceiling water stains. Paint peeling along two walls. Front window cracked and taped. Radiator cover missing. Outlet near kitchen doorway has exposed wiring with no cover plate."),
        ("Kitchen:", "Stove has only 2 of 4 working burners. Refrigerator runs but does not maintain temperature below 45&deg;F. Under-sink area shows signs of previous water damage and possible mold. No exhaust fan."),
        ("Bedroom:", "Window does not open. Closet door missing. Smoke detector removed from ceiling (mount present, no unit). Peeling paint on ceiling — building is pre-1978, possible lead-based paint."),
        ("Bathroom:", "Toilet leaks at base. Hot water takes 4+ minutes to arrive. Exhaust fan non-functional. Tile cracked and grout missing around tub."),
        ("General:", "No carbon monoxide detector found in unit. Front door lock requires significant force. Intercom/buzzer non-functional. Hallway light out. Multiple code violations likely present."),
    ]))

    story.append(section("Lead-Based Paint Disclosure"))
    story.append(kv_table([
        ("Building Year Built:", "Approximately 1915"),
        ("Disclosure Provided:", "Yes"),
        ("Known Lead Paint:", 'Landlord checked "unknown" on disclosure form'),
        ("EPA Pamphlet Provided:", "Yes"),
    ]))


# ============================================================================
# BUILD ALL
# ============================================================================
if __name__ == "__main__":
    print("Generating test lease PDFs...")
    build_pdf(
        "01_compliant_chestnut_hill.pdf",
        "Apartment Lease Agreement",
        "Chestnut Hill Gardens  |  8200 Germantown Avenue, Unit 3B  |  Philadelphia, PA 19118",
        lease_01,
    )
    build_pdf(
        "02_minor_no_certificate_west_philly.pdf",
        "Apartment Lease Agreement",
        "West Philly Apartments  |  4520 Baltimore Avenue, Unit 2A  |  Philadelphia, PA 19143",
        lease_02,
    )
    build_pdf(
        "03_minor_no_escrow_fishtown.pdf",
        "Apartment Lease Agreement",
        "Fishtown Living  |  1835 Frankford Avenue, Unit 1R  |  Philadelphia, PA 19125",
        lease_03,
    )
    build_pdf(
        "04_major_deposit_overcharge_and_waiver_north_philly.pdf",
        "Apartment Lease Agreement",
        "North Philly Residences  |  2741 North Broad Street, Unit 4F  |  Philadelphia, PA 19132",
        lease_04,
    )
    build_pdf(
        "05_major_no_license_no_cert_no_escrow_kensington.pdf",
        "Apartment Lease Agreement",
        "3127 Kensington Avenue, Second Floor  |  Philadelphia, PA 19134",
        lease_05,
    )
    print("\nDone! All 5 PDFs generated.")
