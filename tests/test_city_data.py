"""Philadelphia L&I lookup — address matching, fail-soft, and fact derivation.

Everything here runs offline. The live City API is exercised separately (see
the manual check in CLAUDE.md); these tests must not depend on a third party
being up, or the suite becomes a weather report.
"""

from datetime import date

import pytest

from app import city_data
from app.city_data import CityRecord, derive_facts, normalize_address, split_house_number


# --- the VIN problem: one building, many spellings -------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("200 Spring Garden Street #213", "200 SPRING GARDEN ST"),
        ("200 Spring Garden St #213, Philadelphia, PA 19123", "200 SPRING GARDEN ST"),
        ("3617 SPRING GARDEN ST", "3617 SPRING GARDEN ST"),
        ("1519 Spring Garden St", "1519 SPRING GARDEN ST"),
        ("123 N. 3rd Street, Apt 4B", "123 N 3RD ST"),
        ("4047 spring garden street unit 2", "4047 SPRING GARDEN ST"),
        ("  939   Spring Garden  St  ", "939 SPRING GARDEN ST"),
        ("1500 Market Street, Suite 1200", "1500 MARKET ST"),
    ],
)
def test_addresses_normalize_to_the_form_the_city_stores(raw, expected):
    """The City records a rental licence against the building, never the
    apartment, so the unit has to come off before matching — and the same
    building arrives spelled a dozen ways."""
    assert normalize_address(raw) == expected


def test_a_hyphenated_range_matches_its_first_number():
    """The City files some buildings as ranges: "3514-16 Spring Garden St".
    A resident searching "3514 Spring Garden St" must still find them."""
    pattern = city_data._address_regex(normalize_address("3514 Spring Garden St"))
    assert pattern == "^3514(-[0-9]+)? SPRING GARDEN ST"


def test_house_number_split():
    assert split_house_number("4047 SPRING GARDEN ST") == ("4047", "SPRING GARDEN ST")
    assert split_house_number("SPRING GARDEN ST") == (None, "SPRING GARDEN ST")


@pytest.mark.parametrize(
    "hostile",
    [
        "1 MAIN ST'; DROP TABLE violations;--",
        "'; SELECT * FROM business_licenses --",
        "1 MAIN ST/*",
        "1 MAIN ST\\'",
    ],
)
def test_sql_metacharacters_never_reach_the_query(hostile):
    """The normalized address is interpolated into SQL sent to Carto, so the
    grammar is an allowlist rather than an escaping routine — easier to be
    certain of. Anything outside [A-Z0-9 ] yields no query at all."""
    pattern = city_data._address_regex(normalize_address(hostile))
    if pattern is not None:
        assert "'" not in pattern and ";" not in pattern and "--" not in pattern


# --- fail soft: an outage is not a finding ---------------------------------

def test_city_outage_is_reported_as_unavailable_not_as_a_clean_record(monkeypatch):
    """The distinction that keeps this honest. If the City API is down and we
    said "no licence found", we would be accusing a landlord of being
    unlicensed on the strength of a network error."""
    def boom(_sql):
        raise city_data.CityDataUnavailable("connection timed out")

    monkeypatch.setattr(city_data, "_query", boom)
    record = city_data.fetch_city_record("4047 Spring Garden St")

    assert record.unavailable is True
    assert record.address_found is False
    assert derive_facts(record) == {}, "an outage must produce no facts at all"


def test_an_unparseable_address_produces_no_query():
    record = city_data.fetch_city_record("not really an address")
    assert record.address_found is False
    assert derive_facts(record) == {}


# --- fact derivation -------------------------------------------------------

def _record(licenses=None, violations=None):
    rec = CityRecord(query_address="4047 SPRING GARDEN ST")
    rec.licenses = licenses or []
    rec.violations = violations or []
    rec.address_found = bool(rec.licenses or rec.violations)
    return rec


def test_an_active_unexpired_rental_licence_passes_the_rule():
    rec = _record(licenses=[
        {"licensetype": "Rental", "licensestatus": "Active", "expirationdate": "2027-02-28T05:00:00Z"}
    ])
    assert derive_facts(rec, today=date(2026, 9, 25))["landlord_rental_license_valid"] is True


def test_an_inactive_rental_licence_fires_the_rule():
    rec = _record(licenses=[
        {"licensetype": "Rental", "licensestatus": "Inactive", "expirationdate": "2012-02-29T05:00:00Z"}
    ])
    assert derive_facts(rec, today=date(2026, 9, 25))["landlord_rental_license_valid"] is False


def test_an_expired_but_active_licence_is_not_treated_as_current():
    rec = _record(licenses=[
        {"licensetype": "Rental", "licensestatus": "Active", "expirationdate": "2020-02-28T05:00:00Z"}
    ])
    assert derive_facts(rec, today=date(2026, 9, 25))["landlord_rental_license_valid"] is False


def test_no_licence_row_asserts_nothing_about_the_licence():
    """Absence of evidence is not evidence of absence. A property may be
    owner-occupied, or filed under a different address string. Emitting
    False here would publish an accusation the data does not support."""
    rec = _record(violations=[
        {"violationstatus": "COMPLIED", "violationdate": "2026-06-30T00:00:00Z"}
    ])
    facts = derive_facts(rec, today=date(2026, 9, 25))
    assert "landlord_rental_license_valid" not in facts


def test_open_violations_report_the_longest_running_one():
    rec = _record(violations=[
        {"violationstatus": "OPEN", "violationdate": "2026-08-01T00:00:00Z"},
        {"violationstatus": "OPEN", "violationdate": "2026-06-20T00:00:00Z"},
        {"violationstatus": "COMPLIED", "violationdate": "2020-01-01T00:00:00Z"},
    ])
    facts = derive_facts(rec, today=date(2026, 9, 25))
    assert facts["li_violations_open_days"] == (date(2026, 9, 25) - date(2026, 6, 20)).days


def test_a_known_address_with_nothing_open_reports_zero_days():
    """Zero is a real answer — it is what lets open_violations_over_30_days
    resolve to "no issue found" instead of sitting in "needs facts"."""
    rec = _record(licenses=[{"licensetype": "Rental", "licensestatus": "Active", "expirationdate": None}])
    assert derive_facts(rec, today=date(2026, 9, 25))["li_violations_open_days"] == 0


def test_an_address_absent_from_city_data_reports_no_violation_count():
    """Distinct from the case above: if we never found the address, "no open
    violations" would be a claim about a property we failed to locate."""
    assert "li_violations_open_days" not in derive_facts(_record(), today=date(2026, 9, 25))
