#!/usr/bin/env python3
"""Seed the local database with 20+ realistic Philadelphia demo vaults.

Covers every data type the app supports: leases, insurance, incidents,
city records, move-in/out, payments, inspections, repairs, notices,
photos, deadlines, and multi-vault addresses for the CARFAX history view.

Run:
    source .venv/bin/activate
    python seed_demo.py          # against a running local server
    python seed_demo.py --base https://casavault.vercel.app  # production
"""

import argparse
import json
import sys
import time
from datetime import date, timedelta

import httpx

BASE = "http://127.0.0.1:8000"


def api(method, path, **kwargs):
    url = f"{BASE}{path}"
    r = httpx.request(method, url, timeout=30, **kwargs)
    if r.status_code >= 400:
        print(f"  WARN {method} {path} → {r.status_code}: {r.text[:200]}")
        return None
    return r.json() if r.status_code != 204 else None


def vault(address, unit=None, zip_code=None, label=None):
    body = {"address": address}
    if unit:
        body["unit"] = unit
    if zip_code:
        body["zip_code"] = zip_code
    if label:
        body["label"] = label
    v = api("POST", "/api/vaults", json=body)
    if v:
        print(f"  vault {v['id'][:8]}  {address}")
    return v


def event(vault_id, event_type, occurred_at, notes=None, facts=None):
    body = {"event_type": event_type, "occurred_at": str(occurred_at)}
    if notes:
        body["notes"] = notes
    if facts:
        body["facts"] = facts
    return api("POST", f"/api/vaults/{vault_id}/events", json=body)


def incident(vault_id, **kwargs):
    return api("POST", f"/api/vaults/{vault_id}/incidents", json=kwargs)


def city_record(vault_id):
    return api("POST", f"/api/vaults/{vault_id}/city-record")


def today():
    return date.today()


def ago(days):
    return today() - timedelta(days=days)


def seed():
    print("\n=== Seeding demo data ===\n")

    # ------------------------------------------------------------------
    # 1. Fishtown — compliant lease, full facts, no flags
    # ------------------------------------------------------------------
    print("1. Fishtown — compliant lease, all clear")
    v = vault("2318 E Norris Street", unit="#1", zip_code="19125")
    event(v["id"], "lease_signed", ago(180), "Signed 12-month lease via DocuSign", {
        "deposit_amount": 800.0,
        "deposit_months": 0.6,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
        "clause_waives_deposit_rights": False,
        "waives_implied_warranty_of_habitability": False,
    })
    event(v["id"], "move_in", ago(175), "Keys received, walkthrough done")
    event(v["id"], "payment", ago(145), "First month rent $1,350")
    event(v["id"], "insurance_upload", ago(170), "Renters insurance - State Farm policy HO4")

    # ------------------------------------------------------------------
    # 2. Kensington — deposit too high, no escrow disclosure
    # ------------------------------------------------------------------
    print("2. Kensington — deposit violations")
    v = vault("3012 Kensington Avenue", unit="2F", zip_code="19134")
    event(v["id"], "lease_signed", ago(90), "Lease signed, year one", {
        "deposit_amount": 3200.0,
        "deposit_months": 2.5,
        "tenancy_year": 1,
        "deposit_bank_disclosed": False,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
        "clause_waives_deposit_rights": False,
    })
    event(v["id"], "move_in", ago(85))
    event(v["id"], "payment", ago(60), "Monthly rent $1,280")

    # ------------------------------------------------------------------
    # 3. University City — long tenancy, deposit freeze triggered
    # ------------------------------------------------------------------
    print("3. University City — 6-year tenancy, deposit freeze")
    v = vault("4015 Spruce Street", unit="3R", zip_code="19104")
    event(v["id"], "lease_signed", ago(2200), "Original lease 2020", {
        "deposit_amount": 1500.0,
        "deposit_months": 1.0,
        "deposit_held_months": 1.0,
        "tenancy_year": 6,
        "tenancy_years": 6,
        "deposit_increased": True,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    event(v["id"], "notice_received", ago(45), "Rent increase notice, deposit raised from $1,500 to $1,800")
    event(v["id"], "payment", ago(30), "Rent $1,800 including new deposit")
    incident(v["id"],
        category="appliance", urgency="routine",
        summary="Dishwasher leaking from the door seal",
        reported_at=str(ago(20)),
        management_email="manager@spruce-apts.com",
        reporter_name="M. Thompson",
    )

    # ------------------------------------------------------------------
    # 4. South Philly — no rental license (biggest flag)
    # ------------------------------------------------------------------
    print("4. South Philly — no rental license")
    v = vault("1847 S 8th Street", zip_code="19148")
    event(v["id"], "lease_signed", ago(365), "1-year lease with private landlord", {
        "deposit_amount": 1000.0,
        "deposit_months": 1.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "landlord_rental_license_valid": False,
        "certificate_of_rental_suitability_provided": False,
    })
    event(v["id"], "move_in", ago(360))
    event(v["id"], "repair_requested", ago(200), "Kitchen faucet dripping for weeks")
    event(v["id"], "repair_requested", ago(120), "Bathroom ceiling stain growing — possible leak above")
    incident(v["id"],
        category="water_leak", urgency="urgent",
        summary="Water stain on bathroom ceiling spreading, dripping when upstairs runs water",
        detail="First reported 4 months ago, management said they'd send someone. No one came.",
        affects_essential_service=False,
        previously_reported=True,
        reported_at=str(ago(120)),
        management_email="tony.landlord@gmail.com",
        reporter_name="R. Gonzalez",
    )

    # ------------------------------------------------------------------
    # 5. Germantown — deposit waiver clause (void on its face)
    # ------------------------------------------------------------------
    print("5. Germantown — deposit waiver clause")
    v = vault("5423 Germantown Avenue", unit="A", zip_code="19144")
    event(v["id"], "lease_signed", ago(60), "Lease included a waiver of deposit return rights", {
        "deposit_amount": 2400.0,
        "deposit_months": 2.0,
        "tenancy_year": 1,
        "clause_waives_deposit_rights": True,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    event(v["id"], "move_in", ago(55))
    event(v["id"], "insurance_upload", ago(50), "USAA renters policy uploaded")

    # ------------------------------------------------------------------
    # 6. Manayunk — move-out with deadline clock
    # ------------------------------------------------------------------
    print("6. Manayunk — moved out, deposit clock ticking")
    v = vault("4338 Main Street", unit="2", zip_code="19127")
    event(v["id"], "lease_signed", ago(400), "12-month lease", {
        "deposit_amount": 1600.0,
        "deposit_months": 1.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    event(v["id"], "move_in", ago(395))
    event(v["id"], "inspection", ago(35), "Move-out walkthrough with landlord present")
    event(v["id"], "move_out", ago(30), "Forwarding address given in writing", {
        "forwarding_address_provided": True,
    })

    # ------------------------------------------------------------------
    # 7. West Philly — move-out WITHOUT forwarding address
    # ------------------------------------------------------------------
    print("7. West Philly — move-out, no forwarding address")
    v = vault("221 S 46th Street", unit="#3", zip_code="19139")
    event(v["id"], "lease_signed", ago(750), "Lease signed year 2", {
        "deposit_amount": 1200.0,
        "deposit_months": 1.0,
        "tenancy_year": 2,
        "deposit_held_months": 1.0,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    event(v["id"], "move_out", ago(15), "Left keys with super, did not provide forwarding address", {
        "forwarding_address_provided": False,
    })

    # ------------------------------------------------------------------
    # 8. Northern Liberties — multiple incidents, full lifecycle
    # ------------------------------------------------------------------
    print("8. Northern Liberties — incident lifecycle")
    v = vault("934 N 2nd Street", unit="4B", zip_code="19123")
    event(v["id"], "lease_signed", ago(300), "Lease signed", {
        "deposit_amount": 1800.0,
        "deposit_months": 1.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    event(v["id"], "move_in", ago(295))
    # Heat emergency
    incident(v["id"],
        category="heat", urgency="emergency",
        summary="No heat, thermostat reads 48F inside",
        detail="Boiler stopped working at 3am. Outside temperature is 22F. Children in the unit.",
        affects_essential_service=True,
        previously_reported=False,
        reported_at=str(ago(60)),
        management_email="emergency@nlproperties.com",
        insurance_email="claims@lemonade.com",
        reporter_name="S. Patel",
    )
    # Pest issue — routine
    incident(v["id"],
        category="pest", urgency="routine",
        summary="Mice droppings found in kitchen cabinets",
        reported_at=str(ago(40)),
        management_email="maintenance@nlproperties.com",
        reporter_name="S. Patel",
    )
    # Security issue — urgent
    incident(v["id"],
        category="security", urgency="urgent",
        summary="Front door lock mechanism broken, door does not latch",
        affects_essential_service=True,
        previously_reported=False,
        reported_at=str(ago(10)),
        management_email="emergency@nlproperties.com",
        reporter_name="S. Patel",
    )
    event(v["id"], "insurance_upload", ago(290), "Lemonade renters insurance policy")

    # ------------------------------------------------------------------
    # 9–10. Brewerytown — TWO vaults at same address (history threshold)
    # ------------------------------------------------------------------
    print("9-10. Brewerytown — two tenants, same building (history shows)")
    BREW_ADDR = "2714 W Master Street"
    v1 = vault(BREW_ADDR, unit="1st Fl", zip_code="19121")
    event(v1["id"], "lease_signed", ago(500), "Lease signed 2025", {
        "deposit_amount": 1000.0,
        "deposit_months": 1.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    incident(v1["id"],
        category="water_leak", urgency="urgent",
        summary="Pipe burst under kitchen sink",
        affects_essential_service=True,
        reported_at=str(ago(300)),
        management_email="office@brewerytown-mgmt.com",
        reporter_name="A. Williams",
    )
    incident(v1["id"],
        category="mold", urgency="urgent",
        summary="Black mold growing on bathroom ceiling after persistent leak",
        affects_essential_service=False,
        previously_reported=True,
        reported_at=str(ago(250)),
        management_email="office@brewerytown-mgmt.com",
        reporter_name="A. Williams",
    )

    v2 = vault(BREW_ADDR, unit="2nd Fl", zip_code="19121")
    event(v2["id"], "lease_signed", ago(200), "New tenant, same building", {
        "deposit_amount": 1200.0,
        "deposit_months": 1.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": False,
        "landlord_rental_license_valid": True,
    })
    incident(v2["id"],
        category="heat", urgency="emergency",
        summary="Radiators not working in bedroom and living room",
        affects_essential_service=True,
        reported_at=str(ago(50)),
        management_email="office@brewerytown-mgmt.com",
        insurance_email="claims@progressive.com",
        reporter_name="D. Jackson",
    )

    # ------------------------------------------------------------------
    # 11. Rittenhouse — luxury, everything compliant
    # ------------------------------------------------------------------
    print("11. Rittenhouse — luxury, fully compliant")
    v = vault("1811 Chestnut Street", unit="PH-A", zip_code="19103")
    event(v["id"], "lease_signed", ago(400), "14-month lease, professional management", {
        "deposit_amount": 4000.0,
        "deposit_months": 1.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
        "clause_waives_deposit_rights": False,
        "waives_implied_warranty_of_habitability": False,
    })
    event(v["id"], "move_in", ago(395))
    event(v["id"], "payment", ago(365), "Monthly rent $4,200")
    event(v["id"], "payment", ago(335), "Monthly rent $4,200")
    event(v["id"], "insurance_upload", ago(390), "Chubb renters insurance HO4-Premium")
    event(v["id"], "inspection", ago(180), "Annual inspection — no issues noted")

    # ------------------------------------------------------------------
    # 12. Point Breeze — L&I violations over 30 days
    # ------------------------------------------------------------------
    print("12. Point Breeze — open L&I violations > 30 days")
    v = vault("1523 S 22nd Street", zip_code="19146")
    event(v["id"], "lease_signed", ago(150), "Lease signed", {
        "deposit_amount": 900.0,
        "deposit_months": 1.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    event(v["id"], "city_record", ago(5), "L&I records pulled", {
        "landlord_rental_license_valid": True,
        "li_violations_open_days": 67,
    })
    incident(v["id"],
        category="structural", urgency="urgent",
        summary="Front steps crumbling, railing loose — matches the open L&I violation",
        reported_at=str(ago(45)),
        management_email="landlord@example.com",
        reporter_name="K. Brown",
    )

    # ------------------------------------------------------------------
    # 13. Strawberry Mansion — year 2, deposit still at 2 months
    # ------------------------------------------------------------------
    print("13. Strawberry Mansion — year 2 deposit cap violation")
    v = vault("2841 N 31st Street", zip_code="19132")
    event(v["id"], "lease_signed", ago(450), "Lease signed 2025", {
        "deposit_amount": 2000.0,
        "deposit_months": 2.0,
        "deposit_held_months": 2.0,
        "tenancy_year": 2,
        "tenancy_years": 2,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    event(v["id"], "notice_received", ago(30), "Renewal offer received — deposit not reduced")

    # ------------------------------------------------------------------
    # 14. Fairmount — notice received, repair timeline
    # ------------------------------------------------------------------
    print("14. Fairmount — eviction notice + RTC covered zip")
    v = vault("2209 Fairmount Avenue", zip_code="19130")
    event(v["id"], "lease_signed", ago(700), "Original lease", {
        "deposit_amount": 1500.0,
        "deposit_months": 1.0,
        "tenancy_year": 2,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    event(v["id"], "notice_received", ago(14), "10-day notice to vacate received")
    event(v["id"], "photo", ago(14), "Photo of the notice taped to door")

    # ------------------------------------------------------------------
    # 15. East Falls — insurance claim after incident
    # ------------------------------------------------------------------
    print("15. East Falls — incident with insurance CC")
    v = vault("3540 Midvale Avenue", unit="B", zip_code="19129")
    event(v["id"], "lease_signed", ago(200), "Lease signed", {
        "deposit_amount": 1100.0,
        "deposit_months": 1.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    event(v["id"], "insurance_upload", ago(195), "Allstate renters policy R-445912")
    incident(v["id"],
        category="water_leak", urgency="emergency",
        summary="Ceiling collapsed in bedroom from upstairs water leak",
        detail="Water damage to furniture, electronics, and clothing. Bedroom is unusable. Staying with family.",
        affects_essential_service=True,
        previously_reported=False,
        reported_at=str(ago(8)),
        management_email="leasing@eastfalls-living.com",
        insurance_email="claims@allstate.com",
        reporter_name="J. Rivera",
    )

    # ------------------------------------------------------------------
    # 16–17. Chinatown — two tenants, same address (history visible)
    # ------------------------------------------------------------------
    print("16-17. Chinatown — two vaults, shared address")
    CT_ADDR = "1019 Race Street"
    v1 = vault(CT_ADDR, unit="3A", zip_code="19107")
    event(v1["id"], "lease_signed", ago(600), "Lease 2025", {
        "deposit_amount": 1400.0,
        "deposit_months": 1.0,
        "tenancy_year": 2,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    incident(v1["id"],
        category="pest", urgency="routine",
        summary="Cockroach infestation in kitchen and bathroom",
        reported_at=str(ago(400)),
        management_email="office@chinatown-realty.com",
        reporter_name="L. Chen",
    )

    v2 = vault(CT_ADDR, unit="2B", zip_code="19107")
    event(v2["id"], "lease_signed", ago(100), "New tenant", {
        "deposit_amount": 1500.0,
        "deposit_months": 1.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    incident(v2["id"],
        category="electrical", urgency="urgent",
        summary="Outlets in living room sparking when anything is plugged in",
        affects_essential_service=True,
        reported_at=str(ago(15)),
        management_email="office@chinatown-realty.com",
        reporter_name="T. Nguyen",
    )

    # ------------------------------------------------------------------
    # 18. Olde Kensington — habitability waiver in lease
    # ------------------------------------------------------------------
    print("18. Olde Kensington — habitability waiver + no certificate")
    v = vault("1712 N Front Street", zip_code="19122")
    event(v["id"], "lease_signed", ago(90), "Lease with problematic clauses", {
        "deposit_amount": 1000.0,
        "deposit_months": 1.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "landlord_rental_license_valid": True,
        "certificate_of_rental_suitability_provided": False,
        "waives_implied_warranty_of_habitability": True,
    })
    event(v["id"], "move_in", ago(85))
    event(v["id"], "repair_requested", ago(30), "Radiator in bedroom leaking rusty water onto floor")

    # ------------------------------------------------------------------
    # 19. Passyunk — landlord view, everything clean
    # ------------------------------------------------------------------
    print("19. Passyunk — landlord's own record, all compliant")
    v = vault("1601 E Passyunk Avenue", zip_code="19148", label="Passyunk rental (landlord)")
    event(v["id"], "lease_signed", ago(365), "Tenant signed 12-mo lease", {
        "deposit_amount": 1300.0,
        "deposit_months": 1.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
        "clause_waives_deposit_rights": False,
    })
    event(v["id"], "move_in", ago(360))
    event(v["id"], "inspection", ago(180), "6-month inspection, no issues")
    event(v["id"], "payment", ago(30), "Rent collected $1,300")
    event(v["id"], "insurance_upload", ago(355), "Landlord property insurance — Erie Indemnity")

    # ------------------------------------------------------------------
    # 20. Roxborough — fresh vault, no facts yet (shows "needs facts")
    # ------------------------------------------------------------------
    print("20. Roxborough — brand new, needs facts")
    v = vault("6247 Ridge Avenue", zip_code="19128")
    # No events — adjudication report shows all rules as "unknown"

    # ------------------------------------------------------------------
    # 21. Port Richmond — multiple event types, repair timeline
    # ------------------------------------------------------------------
    print("21. Port Richmond — dense timeline")
    v = vault("3118 Richmond Street", unit="1", zip_code="19134")
    event(v["id"], "lease_signed", ago(500), "Lease signed 2025", {
        "deposit_amount": 800.0,
        "deposit_months": 0.8,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    event(v["id"], "move_in", ago(495))
    event(v["id"], "insurance_upload", ago(490), "GEICO renters policy")
    event(v["id"], "payment", ago(465), "First month $1,000")
    event(v["id"], "repair_requested", ago(300), "Kitchen sink drain clogged")
    event(v["id"], "inspection", ago(290), "Plumber visited, drain cleared")
    event(v["id"], "notice_received", ago(100), "Lease renewal offer — rent increase to $1,100")
    event(v["id"], "payment", ago(60), "Monthly rent $1,100 (new rate)")
    event(v["id"], "photo", ago(45), "Cracked window pane in bedroom — photo for record")
    incident(v["id"],
        category="structural", urgency="routine",
        summary="Cracked window pane in bedroom, draft coming through",
        reported_at=str(ago(45)),
        management_email="richmond-rentals@gmail.com",
        reporter_name="F. O'Brien",
    )
    event(v["id"], "repair_requested", ago(20), "Window pane replaced by maintenance")

    # ------------------------------------------------------------------
    # 22. Spring Garden — lockout (self-help eviction)
    # ------------------------------------------------------------------
    print("22. Spring Garden — lockout event")
    v = vault("1415 Spring Garden Street", zip_code="19130")
    event(v["id"], "lease_signed", ago(400), "Lease signed", {
        "deposit_amount": 1500.0,
        "deposit_months": 1.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
        "lockout_or_utility_shutoff": True,
    })
    event(v["id"], "photo", ago(10), "Photo of new locks on front door — locked out")
    incident(v["id"],
        category="security", urgency="emergency",
        summary="Landlord changed the locks while I was at work — cannot enter my own apartment",
        detail="All belongings still inside. Called police, they said it's a civil matter.",
        affects_essential_service=True,
        previously_reported=False,
        reported_at=str(ago(10)),
        management_email="landlord@springgarden.com",
        reporter_name="C. Martinez",
    )

    # ------------------------------------------------------------------
    # 23. Bella Vista — second-year tenant, deposit returned properly
    # ------------------------------------------------------------------
    print("23. Bella Vista — model tenancy, year 2")
    v = vault("940 S 9th Street", zip_code="19147")
    event(v["id"], "lease_signed", ago(700), "Year one lease", {
        "deposit_amount": 2800.0,
        "deposit_months": 2.0,
        "tenancy_year": 1,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    event(v["id"], "lease_signed", ago(335), "Renewal — deposit reduced to 1 month per statute", {
        "deposit_amount": 1400.0,
        "deposit_months": 1.0,
        "deposit_held_months": 1.0,
        "tenancy_year": 2,
        "tenancy_years": 2,
        "deposit_bank_disclosed": True,
        "certificate_of_rental_suitability_provided": True,
        "landlord_rental_license_valid": True,
    })
    event(v["id"], "payment", ago(30), "Monthly rent $1,400")

    # ------------------------------------------------------------------
    # 24–25. Cedar Park — three vaults (well above threshold)
    # ------------------------------------------------------------------
    print("24-25-26. Cedar Park — three tenants, repair history visible")
    CP_ADDR = "4812 Baltimore Avenue"
    for i, (unit, name, cat, urg, summary, d) in enumerate([
        ("A", "N. Okafor", "appliance", "routine", "Refrigerator not cooling properly", 400),
        ("B", "E. Smith", "water_leak", "urgent", "Bathroom faucet won't shut off completely", 200),
        ("C", "P. Kim", "mold", "urgent", "Mold visible on bedroom wall near window", 50),
    ], start=24):
        vx = vault(CP_ADDR, unit=unit, zip_code="19143")
        event(vx["id"], "lease_signed", ago(d + 30), f"Lease signed, unit {unit}", {
            "deposit_amount": 1000.0,
            "deposit_months": 1.0,
            "tenancy_year": 1,
            "deposit_bank_disclosed": True,
            "certificate_of_rental_suitability_provided": True,
            "landlord_rental_license_valid": True,
        })
        incident(vx["id"],
            category=cat, urgency=urg, summary=summary,
            reported_at=str(ago(d)),
            management_email="cedarpark-property@gmail.com",
            reporter_name=name,
        )

    # ------------------------------------------------------------------
    # Pull City records for a few vaults that have real-looking addresses
    # ------------------------------------------------------------------
    print("\nPulling City records (will fail soft if Carto is unreachable)...")
    # These may or may not return data depending on whether the address
    # matches a real L&I record. The point is to exercise the endpoint.
    for vid in []:  # Skip by default — uncomment to try live City lookups
        city_record(vid)

    print("\n=== Done ===")
    print("Open http://127.0.0.1:8000 to see the demo data.")
    print("Try these addresses on the landing page:")
    print("  - 2714 W Master Street  (Brewerytown — 2 tenants, history visible)")
    print("  - 1019 Race Street       (Chinatown — 2 tenants)")
    print("  - 4812 Baltimore Avenue  (Cedar Park — 3 tenants, full history)")
    print("  - 1847 S 8th Street      (South Philly — no rental license)")
    print("  - 6247 Ridge Avenue      (Roxborough — empty vault, all unknown)")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed CasaVault with demo data")
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="API base URL")
    args = parser.parse_args()
    BASE = args.base
    seed()
