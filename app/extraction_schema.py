from typing import Optional

from pydantic import BaseModel, Field


class ExtractedFacts(BaseModel):
    """Fixed extraction schema — one field per fact any rule in
    statutes.yaml's `condition` strings can reference, plus
    forwarding_address_provided (used by the deposit-return clock).

    Every field is optional: the extractor fills in only what a given
    document actually states and leaves the rest null. It must never infer,
    guess, or judge legality — that's the rules engine's job (PLAN.md:
    'It never judges legality'). Keep this schema in sync with
    statutes.yaml — a new rule with a condition on an unlisted fact will
    silently never fire from extracted documents.
    """

    deposit_amount: Optional[float] = Field(None, description="Security deposit amount in dollars, if stated")
    deposit_months: Optional[float] = Field(
        None, description="Deposit expressed as a number of months' rent, if the lease states it that way"
    )
    deposit_held_months: Optional[float] = Field(
        None, description="Months' rent currently held as deposit, if distinct from deposit_months"
    )
    deposit_increased: Optional[bool] = Field(
        None, description="Whether the deposit was increased alongside a rent increase"
    )
    tenancy_year: Optional[int] = Field(
        None, description="Which year of the tenancy this document/event falls in (1, 2, 3, ...)"
    )
    tenancy_years: Optional[int] = Field(
        None, description="Total whole years of continuous tenancy/possession so far"
    )
    clause_waives_deposit_rights: Optional[bool] = Field(
        None, description="Whether the lease contains a clause purporting to waive deposit-return rights"
    )
    landlord_rental_license_valid: Optional[bool] = Field(
        None, description="Whether the landlord is shown to hold a valid, current Philadelphia rental license"
    )
    certificate_of_rental_suitability_provided: Optional[bool] = Field(
        None, description="Whether a Certificate of Rental Suitability and the tenant handbook were provided at signing"
    )
    li_violations_open_days: Optional[int] = Field(
        None, description="Number of days an L&I violation on the property has been open, if stated"
    )
    waives_implied_warranty_of_habitability: Optional[bool] = Field(
        None, description="Whether the lease purports to waive the implied warranty of habitability"
    )
    lockout_or_utility_shutoff: Optional[bool] = Field(
        None, description="Whether the document describes a lockout or utility shutoff used against the tenant"
    )
    forwarding_address_provided: Optional[bool] = Field(
        None, description="Whether the tenant provided a written forwarding address at move-out"
    )
