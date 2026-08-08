from pathlib import Path

import pytest

from app.memory.policy import PolicyConfigError, load_write_policy

POLICY_PATH = Path(__file__).resolve().parent.parent / "config" / "policy.yaml"


def test_load_write_policy_from_repository_config() -> None:
    policy = load_write_policy(POLICY_PATH)
    assert "preference" in policy.allowed_types
    assert "sensitive" in policy.require_approval


def test_resolve_write_status_approved_for_internal() -> None:
    policy = load_write_policy(POLICY_PATH)
    assert policy.resolve_write_status("internal") == "approved"


def test_resolve_write_status_pending_for_sensitive() -> None:
    policy = load_write_policy(POLICY_PATH)
    assert policy.resolve_write_status("sensitive") == "pending_approval"


def test_missing_policy_file_raises(tmp_path: Path) -> None:
    with pytest.raises(PolicyConfigError):
        load_write_policy(tmp_path / "missing.yaml")


def test_require_approval_must_be_subset_of_allowed_sensitivities(
    tmp_path: Path,
) -> None:
    bad = tmp_path / "policy.yaml"
    bad.write_text(
        "long_term:\n"
        "  write:\n"
        "    allowed_types: [fact]\n"
        "    allowed_sensitivities: [internal]\n"
        "    require_approval: [sensitive]\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyConfigError):
        load_write_policy(bad)
