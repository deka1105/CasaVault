import ast
import operator
import re
from typing import Any, Optional

_COMPARISONS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

_WORD_OP = re.compile(r"\b(AND|OR|NOT)\b")
_PY_OP = {"AND": "and", "OR": "or", "NOT": "not"}

# statutes.yaml conditions write boolean literals lowercase (e.g.
# "landlord_rental_license_valid == false"); Python's grammar needs the
# capitalized form or these parse as unbound Name lookups (always None/false).
_WORD_BOOL = re.compile(r"\b(true|false)\b")
_PY_BOOL = {"true": "True", "false": "False"}


class UnsafeConditionError(ValueError):
    pass


class _Missing:
    """Sentinel for 'this fact was never recorded', distinct from a recorded
    False — the whole point of the tristate evaluator."""


_MISSING = _Missing()


def _parse(condition: str) -> ast.AST:
    normalized = _WORD_OP.sub(lambda m: _PY_OP[m.group(0)], condition)
    normalized = _WORD_BOOL.sub(lambda m: _PY_BOOL[m.group(0)], normalized)
    try:
        return ast.parse(normalized, mode="eval").body
    except SyntaxError as exc:
        raise UnsafeConditionError(f"unparseable condition: {condition!r}") from exc


def evaluate_condition(condition: str, facts: dict[str, Any]) -> bool:
    """Safely evaluate a statutes.yaml `condition` string (e.g.
    'deposit_months > 2 AND tenancy_year == 1') against a facts dict.

    Only boolean and/or/not, comparisons, bare names, and literal constants
    are allowed — no calls, attributes, or subscripts. Conditions come from
    statutes.yaml, not user input, but a grammar this narrow also catches
    authoring mistakes in the statute table before they reach a flag.

    An absent fact makes the whole condition False, never an error — missing
    data must never be misread as a violation. Use evaluate_condition_tristate
    when you need to tell "we know this rule is satisfied" apart from "we
    don't have the facts to say".
    """
    return evaluate_condition_tristate(condition, facts) is True


def evaluate_condition_tristate(condition: str, facts: dict[str, Any]) -> Optional[bool]:
    """Three-valued evaluation: True (fires), False (definitively does not
    fire), or None (undetermined — a fact the condition depends on is absent).

    This is the difference between "your deposit is within the legal cap" and
    "we have no idea what your deposit is", which the boolean version cannot
    express: both came out False. A vault holding a fully compliant lease
    otherwise renders as an empty page, which reads as the product having
    done nothing rather than as evidence that nothing is wrong.

    Kleene logic, so short-circuiting still resolves what it can:
    `deposit_held_months > 1 AND tenancy_year >= 2` against a first-year
    tenancy is definitively False — the second operand settles it — even
    though deposit_held_months is unknown. That correctly reads as "does not
    apply" rather than "unknown".
    """
    return _eval_tristate(_parse(condition), facts)


def referenced_facts(condition: str) -> set[str]:
    """Every fact name a condition depends on — used to tell the user which
    missing facts are keeping a rule undetermined."""
    return {n.id for n in ast.walk(_parse(condition)) if isinstance(n, ast.Name)}


def _eval_tristate(node: ast.AST, facts: dict[str, Any]) -> Optional[bool]:
    if isinstance(node, ast.BoolOp):
        values = [_eval_tristate(v, facts) for v in node.values]
        if isinstance(node.op, ast.And):
            if any(v is False for v in values):
                return False  # one false operand settles an AND
            return True if all(v is True for v in values) else None
        if isinstance(node.op, ast.Or):
            if any(v is True for v in values):
                return True  # one true operand settles an OR
            return False if all(v is False for v in values) else None
        raise UnsafeConditionError(f"unsupported boolean operator in: {ast.dump(node)}")

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = _eval_tristate(node.operand, facts)
        return None if inner is None else not inner

    if isinstance(node, ast.Compare):
        left = _resolve(node.left, facts)
        if left is _MISSING:
            return None
        for op, comparator in zip(node.ops, node.comparators):
            op_fn = _COMPARISONS.get(type(op))
            if op_fn is None:
                raise UnsafeConditionError(f"unsupported comparison operator: {op}")
            right = _resolve(comparator, facts)
            if right is _MISSING:
                return None
            try:
                if not op_fn(left, right):
                    return False
            except TypeError:
                # e.g. a rule comparing a string fact against a number. Treat
                # as undetermined rather than letting one malformed fact take
                # down adjudication for the whole vault.
                return None
            left = right
        return True

    if isinstance(node, ast.Constant):
        return bool(node.value)

    if isinstance(node, ast.Name):
        value = facts.get(node.id, _MISSING)
        return None if value is _MISSING else bool(value)

    raise UnsafeConditionError(f"unsupported expression: {ast.dump(node)}")


def _resolve(node: ast.AST, facts: dict[str, Any]) -> Any:
    if isinstance(node, ast.Name):
        # An explicit null in the facts dict means "asked and not stated",
        # which is still not knowing the answer.
        value = facts.get(node.id, _MISSING)
        return _MISSING if value is None else value
    if isinstance(node, ast.Constant):
        return node.value
    raise UnsafeConditionError(f"unsupported operand: {ast.dump(node)}")


def _eval_node(node: ast.AST, facts: dict[str, Any]) -> Any:
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, facts) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise UnsafeConditionError(f"unsupported boolean operator in: {ast.dump(node)}")

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, facts)

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, facts)
        for op, comparator in zip(node.ops, node.comparators):
            op_fn = _COMPARISONS.get(type(op))
            if op_fn is None:
                raise UnsafeConditionError(f"unsupported comparison operator: {op}")
            right = _eval_node(comparator, facts)
            if left is None or right is None:
                return False
            if not op_fn(left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.Name):
        return facts.get(node.id)

    if isinstance(node, ast.Constant):
        return node.value

    raise UnsafeConditionError(f"unsupported expression: {ast.dump(node)}")
