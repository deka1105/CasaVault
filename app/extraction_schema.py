from typing import Optional

from pydantic import BaseModel, Field


class ExtractedFacts(BaseModel):
    """Extraction schema for rental documents.

    Two categories of fields:
    1. Rule-linked: referenced by statutes.yaml conditions — keep in sync.
    2. General lease terms: not tied to a rule but useful for the timeline,
       evidence packet, and agent Q&A (e.g. prorated rent, lease dates,
       buy-out terms).

    Every field is optional: the extractor fills in only what a given
    document actually states and leaves the rest null. It must never infer,
    guess, or judge legality — that's the rules engine's job.
    """

    # --- Rule-linked facts (keep in sync with statutes.yaml) ---

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
    deposit_bank_disclosed: Optional[bool] = Field(
        None,
        description=(
            "Whether the document states the name AND address of the banking institution "
            "holding the security deposit. True only if an actual bank name/address is "
            "written in; false if the field is present but left blank."
        ),
    )
    forwarding_address_provided: Optional[bool] = Field(
        None, description="Whether the tenant provided a written forwarding address at move-out"
    )

    # --- Lease term facts (general, used by agent and timeline) ---

    monthly_rent: Optional[float] = Field(None, description="Base monthly rent amount in dollars")
    prorated_rent: Optional[float] = Field(
        None, description="Prorated first month's rent in dollars, if different from full monthly rent"
    )
    prorated_rent_period: Optional[str] = Field(
        None, description="The date range the prorated rent covers, e.g. '5/12/2026 to 5/31/2026'"
    )
    lease_start_date: Optional[str] = Field(None, description="Lease start date, e.g. '2026-05-12'")
    lease_end_date: Optional[str] = Field(None, description="Lease end date, e.g. '2027-08-11'")
    lease_term_months: Optional[int] = Field(None, description="Total lease term in months, if stated")
    pet_deposit: Optional[float] = Field(None, description="Pet deposit or pet fee amount in dollars, if any")
    late_fee_amount: Optional[float] = Field(
        None, description="Late fee amount in dollars (flat rate), if stated"
    )
    late_fee_percent: Optional[float] = Field(
        None, description="Late fee as a percentage of rent, if stated instead of flat rate"
    )
    late_fee_grace_days: Optional[int] = Field(
        None, description="Number of days after rent is due before the late fee applies"
    )
    returned_check_fee: Optional[float] = Field(None, description="Fee for returned/bounced checks in dollars")
    move_out_notice_days: Optional[int] = Field(
        None, description="Number of days' written notice required before moving out"
    )

    # --- Utilities ---
    utilities_included: Optional[str] = Field(
        None, description="Comma-separated list of utilities the landlord pays for, e.g. 'water, sewer, trash'"
    )
    utilities_tenant_pays: Optional[str] = Field(
        None, description="Comma-separated list of utilities the tenant pays for, if listed"
    )

    # --- Insurance ---
    renter_insurance_required: Optional[bool] = Field(
        None, description="Whether the lease requires the tenant to carry renter's insurance"
    )
    insurance_minimum_coverage: Optional[float] = Field(
        None, description="Minimum personal liability coverage required in dollars, if stated"
    )

    # --- Occupancy ---
    apartment_number: Optional[str] = Field(None, description="The apartment or unit number")
    property_address: Optional[str] = Field(None, description="The street address of the property")
    landlord_name: Optional[str] = Field(None, description="The owner or management company name")

    # --- Buy-out / Early termination ---
    buyout_amount: Optional[float] = Field(
        None, description="Lease buy-out or early termination fee in dollars, if stated"
    )
    buyout_notice_days: Optional[int] = Field(
        None, description="Number of days' notice required for the buy-out option, if stated"
    )
    buyout_conditions: Optional[str] = Field(
        None, description="Summary of conditions or requirements for the buy-out, if stated"
    )

    # --- Rent concession ---
    rent_concession_amount: Optional[float] = Field(
        None, description="Dollar amount of any rent concession or credit, if stated"
    )
    rent_concession_description: Optional[str] = Field(
        None, description="Brief description of the concession (e.g. 'first month free', '$500 off move-in')"
    )

    # --- Fees disclosure ---
    application_fee: Optional[float] = Field(None, description="Application fee in dollars, if stated")
    admin_fee: Optional[float] = Field(None, description="Administrative or move-in fee in dollars, if stated")
    other_fees: Optional[str] = Field(
        None, description="Any other named fees and amounts, e.g. 'trash valet $25/mo, parking $75/mo'"
    )

    # --- Lead / environmental ---
    lead_paint_disclosure: Optional[bool] = Field(
        None, description="Whether a lead-based paint disclosure was provided (required for pre-1978 buildings)"
    )
    building_year_built: Optional[int] = Field(
        None, description="Year the building was constructed, if stated in the document"
    )

    # --- Acknowledgments (from Philadelphia Acknowledgment form) ---
    partners_good_housing_provided: Optional[bool] = Field(
        None, description="Whether the Partners in Good Housing handbook was provided at signing"
    )
    bed_bug_disclosure_provided: Optional[bool] = Field(
        None, description="Whether a bed bug disclosure/addendum was provided"
    )

    # --- Inventory / condition ---
    condition_notes: Optional[str] = Field(
        None, description="Summary of pre-existing damage or condition noted at move-in"
    )

    # --- Catch-all for document-specific terms ---
    additional_terms: Optional[str] = Field(
        None,
        description=(
            "Any other notable terms, clauses, or obligations from this document that "
            "don't fit the above fields. Summarize briefly, e.g. "
            "'subletting prohibited; no smoking in unit; class action waiver included'"
        ),
    )
