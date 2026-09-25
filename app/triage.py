"""Decide which documents in an upload are worth sending to the extractor.

A real Philadelphia lease is not one PDF. The one this was built against is a
DocuSign envelope of **25 files and 102 pages**: the NAA apartment lease
contract, a Philadelphia acknowledgment of required documents, an inventory
and condition form, a fees disclosure — and twenty-one addenda and city
brochures, including a 28-page Partners for Good Housing handbook and a
13-page bed bug brochure.

Sending all 25 to the model costs 25 requests. The configured key's free tier
allows 20 per DAY. So triage is not an optimization here; without it a single
real lease cannot be processed at all.

The categories are about whether a document can contain facts *about this
tenancy*, which is the only thing the statute table can adjudicate:

  PRIORITY   carries the terms — deposit, rent, dates, disclosures, condition
  SECONDARY  addenda that may carry a waiver or an extra obligation
  SKIP       government-published or informational material that is byte-for-
             byte identical for every tenant in the city, plus the DocuSign
             audit trail (which holds no lease terms at all, only names, email
             addresses and signer IP addresses)

Only SKIP is asserted confidently. Anything unrecognized falls to SECONDARY
and is read if budget remains, because a wrong skip loses a fact silently
while a wrong read only costs a request.
"""

import re
from dataclasses import dataclass

PRIORITY = "priority"
SECONDARY = "secondary"
SKIP = "skip"

# How many SECONDARY documents to read per upload once PRIORITY ones are done.
# Tuned against the 20/day free tier: a real bundle then costs ~7 requests,
# leaving room to iterate in the same day.
DEFAULT_SECONDARY_BUDGET = 3

_SKIP_PATTERNS = (
    r"brochure",
    r"\bguide\b",
    r"handbook",
    r"partners[_ ]?(for|in)[_ ]?good[_ ]?housing",
    r"certificate[_ ]of[_ ]completion",
    r"^summary\b",
)

_PRIORITY_PATTERNS = (
    r"lease[_ ]?(contract|form|agreement)",
    r"apartment[_ ]?lease",
    r"acknowledgment|acknowledgement",
    r"required[_ ]?documents",
    r"inventory|condition",
    r"fees?[_ ]?disclosure",
    r"rent[_ ]?concession",
    r"security[_ ]?deposit",
    r"buy-?out",
)


@dataclass(frozen=True)
class TriageDecision:
    category: str
    extract: bool
    reason: str


def classify(filename: str) -> str:
    name = (filename or "").lower()
    # SKIP is checked first: "PHILADELPHIA_PARTNERS_FOR_GOOD_HOUSING" would
    # otherwise be caught by nothing, but "CITY_OF_PHILADELPHIA_BED_BUG_
    # BROCHURE" contains no priority term either way — the ordering matters
    # for names that hit both lists, e.g. a "lease summary brochure".
    for pattern in _SKIP_PATTERNS:
        if re.search(pattern, name):
            return SKIP
    for pattern in _PRIORITY_PATTERNS:
        if re.search(pattern, name):
            return PRIORITY
    return SECONDARY


def plan(filenames: list[str], secondary_budget: int = DEFAULT_SECONDARY_BUDGET) -> list[TriageDecision]:
    """Decide, for a whole batch at once, which files to read.

    Batch-level rather than per-file because the budget is only meaningful
    across the set: whether to spend a request on the ninth addendum depends
    on how many were spent already.
    """
    decisions: list[TriageDecision] = []
    remaining = secondary_budget

    for name in filenames:
        category = classify(name)
        if category == SKIP:
            decisions.append(
                TriageDecision(
                    SKIP,
                    False,
                    "Stored, not read — informational material with no facts specific to this tenancy.",
                )
            )
        elif category == PRIORITY:
            decisions.append(TriageDecision(PRIORITY, True, "Read — carries the terms of this tenancy."))
        elif remaining > 0:
            remaining -= 1
            decisions.append(TriageDecision(SECONDARY, True, "Read — an addendum that may add terms or a waiver."))
        else:
            decisions.append(
                TriageDecision(
                    SECONDARY,
                    False,
                    "Stored, not read — reading budget for this upload was already spent on the main documents.",
                )
            )
    return decisions
