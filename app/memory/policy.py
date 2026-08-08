"""Config-driven write policy: allowed types, sensitivities, and approval gates.

`type` and `sensitivity` are validated against `config/policy.yaml` rather
than a hardcoded enum, so introducing a new memory type or sensitivity tier
requires a reviewed change to that file, not a code change.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class PolicyConfigError(ValueError):
    """Raised when the policy file is missing, malformed, or inconsistent."""


@dataclass(frozen=True, slots=True)
class WritePolicy:
    """Resolved write policy for long-term memory proposals."""

    allowed_types: frozenset[str]
    allowed_sensitivities: frozenset[str]
    require_approval: frozenset[str]

    def validate_type(self, type_: str) -> None:
        """Reject a memory type not declared in `allowed_types`."""

        if type_ not in self.allowed_types:
            raise PolicyConfigError(f"type '{type_}' is not an allowed memory type")

    def validate_sensitivity(self, sensitivity: str) -> None:
        """Reject a sensitivity tier not declared in `allowed_sensitivities`."""

        if sensitivity not in self.allowed_sensitivities:
            raise PolicyConfigError(f"sensitivity '{sensitivity}' is not recognized")

    def resolve_write_status(self, sensitivity: str) -> str:
        """Return `pending_approval` for gated sensitivities, else `approved`."""

        return (
            "pending_approval" if sensitivity in self.require_approval else "approved"
        )


def load_write_policy(path: Path) -> WritePolicy:
    """Load and cross-validate the long-term memory write policy."""

    if not path.is_file():
        raise PolicyConfigError(f"policy file not found: {path}")

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PolicyConfigError(f"unable to read policy file: {path}") from exc

    try:
        raw = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        raise PolicyConfigError(f"invalid YAML in policy file: {path}") from exc

    try:
        write = raw["long_term"]["write"]
        allowed_types = frozenset(write["allowed_types"])
        allowed_sensitivities = frozenset(write["allowed_sensitivities"])
        require_approval = frozenset(write["require_approval"])
    except (KeyError, TypeError) as exc:
        raise PolicyConfigError(f"malformed policy file: {path}") from exc
    if not allowed_types:
        raise PolicyConfigError("policy must declare at least one allowed_types entry")
    if not allowed_sensitivities:
        raise PolicyConfigError(
            "policy must declare at least one allowed_sensitivities entry"
        )
    if not require_approval.issubset(allowed_sensitivities):
        raise PolicyConfigError(
            "require_approval entries must all be allowed_sensitivities"
        )
    return WritePolicy(
        allowed_types=allowed_types,
        allowed_sensitivities=allowed_sensitivities,
        require_approval=require_approval,
    )
