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
    # A waiver is the table's highest-value detectable clause
    # (statutes.yaml, deposit_waiver_void: "void on its face, detectable by
    # extraction alone"), and the master addendum is where a real lease hides
    # them — the one tested against buries "Resident Waives Right to Withhold
    # Rent" in section 29 of its community policies.
    r"waiver|waives",
    r"master[_ ]?addendum",
    r"community[_ ]?policies",
)

# Ranking for SECONDARY documents, which compete for a limited budget.
# Without this the budget is spent in whatever order the file picker returned
# — alphabetically, that meant reading the marijuana addendum and skipping
# the master addendum.
_SECONDARY_RELEVANCE = (
    (r"lead|habitability|mold|repair|maintenance", 5),
    (r"utility|utilities", 4),
    (r"insurance|damage", 3),
    (r"pet|parking|storage", 2),
    (r"bed[_ ]?bug", 2),
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
    categories = [classify(name) for name in filenames]

    # Spend the secondary budget on the most promising addenda, not on
    # whichever happened to sort first.
    ranked = sorted(
        (i for i, c in enumerate(categories) if c == SECONDARY),
        key=lambda i: (-relevance(filenames[i]), i),
    )
    fund = set(ranked[:secondary_budget])

    decisions: list[TriageDecision] = []
    for i, (name, category) in enumerate(zip(filenames, categories)):
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
        elif i in fund:
            decisions.append(TriageDecision(SECONDARY, True, "Read — an addendum that may add terms or a waiver."))
        else:
            decisions.append(
                TriageDecision(
                    SECONDARY,
                    False,
                    "Stored, not read — the reading budget for this upload went to the main documents.",
                )
            )
    return decisions


def relevance(filename: str) -> int:
    name = (filename or "").lower()
    for pattern, score in _SECONDARY_RELEVANCE:
        if re.search(pattern, name):
            return score
    return 0
