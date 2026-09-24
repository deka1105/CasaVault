from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class StatuteTable:
    jurisdiction: str
    rules: list[dict[str, Any]]
    right_to_counsel: dict[str, Any]

    @property
    def verified_rules(self) -> list[dict[str, Any]]:
        """Rules safe to surface to a user. Draft rules are excluded — see
        CLAUDE.md and the status legend at the top of statutes.yaml."""
        return [r for r in self.rules if r.get("status") == "verified"]

    def get_rule(self, rule_id: str) -> dict[str, Any] | None:
        return next((r for r in self.rules if r.get("id") == rule_id), None)


def load_statute_table(path: Path) -> StatuteTable:
    data = yaml.safe_load(path.read_text())
    return StatuteTable(
        jurisdiction=data["jurisdiction"],
        rules=data["rules"],
        right_to_counsel=data["right_to_counsel"],
    )
