import ast
import operator
import re
from typing import Any

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


def evaluate_condition(condition: str, facts: dict[str, Any]) -> bool:
    """Safely evaluate a statutes.yaml `condition` string (e.g.
    'deposit_months > 2 AND tenancy_year == 1') against a facts dict.

    Only boolean and/or/not, comparisons, bare names, and literal constants
    are allowed — no calls, attributes, or subscripts. Conditions come from
    statutes.yaml, not user input, but a grammar this narrow also catches
    authoring mistakes in the statute table before they reach a flag.
    An absent fact makes any comparison involving it False, never an error —
    missing data should never be misread as a violation.
    """
    normalized = _WORD_OP.sub(lambda m: _PY_OP[m.group(0)], condition)
    normalized = _WORD_BOOL.sub(lambda m: _PY_BOOL[m.group(0)], normalized)
    try:
        node = ast.parse(normalized, mode="eval").body
    except SyntaxError as exc:
        raise UnsafeConditionError(f"unparseable condition: {condition!r}") from exc
    return bool(_eval_node(node, facts))


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
