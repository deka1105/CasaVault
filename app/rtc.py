from typing import Any


def handoff_for_zip(right_to_counsel: dict[str, Any], zip_code: str | None) -> dict[str, Any]:
    """Right to Counsel zip check (PLAN.md: 'RTC-covered zips -> Philly Tenant
    Hotline; everyone else -> PhillyTenant.org'). Shared by the agent stub and
    the standalone /rtc-check endpoint so the routing logic lives in one place."""
    if zip_code and zip_code in right_to_counsel["covered_zips"]:
        return {
            "route": "hotline",
            "contact": right_to_counsel["hotline"],
            "eligibility": right_to_counsel["eligibility"],
        }
    return {"route": "phillytenant_org", "contact": right_to_counsel["uncovered_fallback"]}
