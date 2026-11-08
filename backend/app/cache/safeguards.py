"""Semantic compatibility safeguards for the Knowlix Semantic Cache Engine.

Prevents false-positive cache collisions where questions share high embedding
cosine similarity but differ fundamentally in intent, polarity, numerical facts,
entities, or interrogative scope.
"""

import re
from typing import Optional, Set, Tuple

# Pre-compiled regex patterns
_RE_NUMBERS = re.compile(r"\b\d+(?:\.\d+)?%?\b")
_RE_YEARS = re.compile(r"\b(?:19|20)\d{2}\b")
_RE_WORDS = re.compile(r"\b[A-Za-z0-9_'-]+\b")

# Negation terms
_NEGATION_WORDS = frozenset({
    "not", "no", "never", "none", "neither", "nor", "without", "hardly",
    "scarcely", "barely", "fails", "fail", "failed", "cannot", "can't",
    "won't", "don't", "didn't", "isn't", "aren't", "wasn't", "weren't",
    "prevent", "prohibit", "exclude", "except", "refuse"
})

# Interrogative keywords
_INTERROGATIVES = frozenset({
    "who", "whom", "whose", "what", "which", "when", "where", "why", "how"
})

# Polar / Aspect contrast groups
_ASPECT_GROUPS = {
    "limitations": frozenset({"limitation", "limitations", "drawback", "drawbacks", "weakness", "weaknesses", "disadvantage", "flaw", "flaws", "risk", "risks"}),
    "advantages": frozenset({"advantage", "advantages", "benefit", "benefits", "strength", "strengths", "merit", "pro", "pros"}),
    "methodology": frozenset({"method", "methodology", "algorithm", "architecture", "implementation", "design", "approach", "technique"}),
    "results": frozenset({"result", "results", "finding", "findings", "outcome", "outcomes", "conclusion", "conclusions"}),
    "authors": frozenset({"author", "authors", "proposer", "proposed", "inventor", "creator", "researcher", "who"}),
    "cost": frozenset({"cost", "price", "budget", "total", "fee", "expense", "amount"}),
}

_COMPARISON_TERMS = frozenset({
    "difference", "differences", "compare", "comparison", "contrasted", "contrast",
    "versus", "vs", "better", "worse", "higher", "lower", "greater", "less"
})


def _extract_tokens(text: str) -> Set[str]:
    return set(token.lower() for token in _RE_WORDS.findall(text))


def _extract_numbers(text: str) -> Set[str]:
    return set(_RE_NUMBERS.findall(text))


def _extract_negations(tokens: Set[str]) -> Set[str]:
    return tokens & _NEGATION_WORDS


def _get_interrogatives(tokens: Set[str]) -> Set[str]:
    return tokens & _INTERROGATIVES


def validate_semantic_compatibility(
    query1: str, query2: str
) -> Tuple[bool, Optional[str]]:
    """Determine whether two queries are semantically safe to share a cached answer.

    Returns (is_compatible, refusal_reason).
    """
    q1_lower = query1.strip().lower()
    q2_lower = query2.strip().lower()

    if q1_lower == q2_lower:
        return True, None

    tokens1 = _extract_tokens(q1_lower)
    tokens2 = _extract_tokens(q2_lower)

    # 1. Negation Safeguard
    negs1 = _extract_negations(tokens1)
    negs2 = _extract_negations(tokens2)
    if bool(negs1) != bool(negs2):
        return False, "negation_mismatch"

    # 2. Numbers and Dates Safeguard
    nums1 = _extract_numbers(q1_lower)
    nums2 = _extract_numbers(q2_lower)
    if nums1 and nums2 and nums1 != nums2:
        return False, "number_mismatch"
    if bool(nums1) != bool(nums2):
        # One has specific numbers (e.g. "in 2024") and the other has none
        return False, "number_presence_mismatch"

    # 3. Interrogative Scope Safeguard
    interrog1 = _get_interrogatives(tokens1)
    interrog2 = _get_interrogatives(tokens2)
    # If both have explicit interrogatives and they don't overlap (e.g. 'who' vs 'what' or 'why' vs 'when')
    if interrog1 and interrog2 and not (interrog1 & interrog2):
        # Allow synonymous pairings e.g. "what are the findings" vs "summarize the findings"
        # but disallow "who proposed" vs "what/why"
        if "who" in interrog1 or "who" in interrog2:
            return False, "interrogative_entity_mismatch"
        if "when" in interrog1 or "when" in interrog2:
            return False, "interrogative_temporal_mismatch"
        if "where" in interrog1 or "where" in interrog2:
            return False, "interrogative_locational_mismatch"

    # 4. Aspect / Polarity Group Safeguard
    # E.g. "limitations" vs "findings/advantages" or "who proposed" vs "limitations"
    for group_name, terms in _ASPECT_GROUPS.items():
        has1 = bool(tokens1 & terms)
        has2 = bool(tokens2 & terms)
        if has1 != has2:
            # Check if contrasting group is active
            if group_name == "limitations" and bool(tokens2 & (_ASPECT_GROUPS["advantages"] | _ASPECT_GROUPS["results"] | _ASPECT_GROUPS["authors"])):
                return False, f"aspect_contrast_{group_name}"
            if group_name == "authors" and bool(tokens2 & (_ASPECT_GROUPS["limitations"] | _ASPECT_GROUPS["methodology"])):
                return False, f"aspect_contrast_{group_name}"
            if group_name == "cost" and not has2:
                return False, "aspect_contrast_cost"

    # 5. Comparison Safeguard
    comp1 = bool(tokens1 & _COMPARISON_TERMS)
    comp2 = bool(tokens2 & _COMPARISON_TERMS)
    if comp1 != comp2:
        return False, "comparison_mismatch"

    return True, None
