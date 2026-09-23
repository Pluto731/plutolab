"""Local synthetic prices/limits; all sockets denied and no provider execution."""

import json
import socket
from decimal import Decimal

import pytest
from pydantic import ValidationError

from plutolab_api.services.review.budget import (
    BudgetLedger,
    ProviderProfile,
    Rejection,
    Reservation,
    estimate_cost,
    estimate_tokens,
)
from plutolab_api.services.review.chunking import plan_chunks
from plutolab_api.services.review.diff import prepare_diff
from tests.test_review_diff import SHA, STANDARD, addition
from tests.test_review_diff import policy as base_policy


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Slice 11: no sockets")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def policy(**changes):
    data = base_policy(maximum=10000, files=100, context=100).model_dump()
    data["budgets"].update(
        context_window_tokens=100000,
        max_request_input_tokens=90000,
        reserved_output_tokens=100,
        max_total_input_tokens=1000000,
        max_total_output_tokens=10000,
        max_chunks=100,
        max_cost_usd="10.000000",
        max_owner_daily_cost_usd="20.000000",
    )
    data["budgets"].update(changes)
    return type(base_policy()).model_validate(data)


def profile(**changes):
    values = {
        "provider": "anthropic",
        "model": "local",
        "pricing_version": "synthetic-test-v1",
        "context_window_tokens": 100000,
        "max_output_tokens": 1000,
        "framing_tokens": 10,
        "input_usd_per_million": "1.000000",
        "output_usd_per_million": "2.000000",
    }
    values.update(changes)
    return ProviderProfile(**values)


def plan(
    text=STANDARD,
    *,
    rules=None,
    provider=None,
    remaining="20.000000",
    prompt="Review these excerpts.",
):
    rules = rules or policy()
    return plan_chunks(
        prepare_diff(text, head_sha=SHA, policy=rules),
        rules,
        provider or profile(),
        system_prompt=prompt,
        owner_remaining_usd=remaining,
    )


def test_pack_hunks_and_preserve_every_mapping():
    result = plan()
    assert len(result.chunks) == 1 and len(result.chunks[0].hunks) == 2
    original = prepare_diff(STANDARD, head_sha=SHA, policy=policy())
    assert (
        tuple(line for h in result.chunks[0].hunks for line in h.lines) == original.files[0].lines
    )
    assert result.chunks[0].hunks[1].positions == (7, 8)
    assert result.chunks[0].hunks[1].old_range == (30, 30)
    assert result.chunks[0].hunks[1].new_range == (31, 31)
    assert result.coverage.included_lines == 5 and result.coverage.reviewed_line_ratio == "1"
    assert result.coverage.status == "complete"
    assert plan() == result


def test_payload_exactly_counted_including_prompt_metadata_and_escaping():
    result = plan(prompt='Review "code"\n中文 🔒')
    chunk = result.chunks[0]
    assert chunk.reservation.input_tokens == len(chunk.payload.encode("utf-8")) + 10
    assert json.loads(chunk.payload)["system_prompt"] == 'Review "code"\n中文 🔒'
    assert result.totals.input_tokens == chunk.reservation.input_tokens
    assert result.totals.output_tokens == 100
    assert result.totals.estimated_cost_usd == estimate_cost(
        result.totals.input_tokens, 100, profile()
    )


def test_files_never_mixed():
    result = plan(addition("a.py") + addition("b.py"))
    assert len(result.chunks) == 2
    assert [c.hunks[0].path for c in result.chunks] == ["a.py", "b.py"]
    assert all(len({h.path for h in c.hunks}) == 1 for c in result.chunks)


def test_pack_splits_only_at_hunk_boundary():
    full = plan()
    first = full.chunks[0].hunks[0]
    # Set a cap which fits either hunk alone, but not the pair.
    result = plan(rules=policy(max_request_input_tokens=full.totals.input_tokens - 1))
    assert len(result.chunks) == 2
    assert result.chunks[0].hunks == (first,)
    assert result.coverage.included_lines == 5


def test_oversized_hunk_is_atomic_and_later_small_hunk_can_fit():
    large = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+"
        + "x" * 8000
        + "\n@@ -10 +10 @@\n-a\n+b\n"
    )
    result = plan(large, rules=policy(max_request_input_tokens=3000))
    assert result.hunks[0].status == "skipped_budget"
    assert result.hunks[0].reason == "request_input_limit"
    assert len(result.chunks) == 1 and result.chunks[0].hunks[0].new_range == (10, 10)
    assert result.coverage.reviewed_line_ratio == "1/2"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"max_chunks": 1}, "chunk_limit"),
        ({"max_total_output_tokens": 100}, "total_output_limit"),
        ({"max_total_input_tokens": 1000}, "total_input_limit"),
        ({"max_cost_usd": "0.001000"}, "job_cost_limit"),
    ],
)
def test_deterministic_job_cutoffs(change, reason):
    result = plan(addition("a.py") + addition("b.py") + addition("c.py"), rules=policy(**change))
    assert result.coverage.skipped_budget > 0
    assert reason in result.coverage.reasons
    assert result == plan(
        addition("a.py") + addition("b.py") + addition("c.py"), rules=policy(**change)
    )
    assert result.totals.chunks <= policy(**change).budgets.max_chunks


def test_provider_context_overrides_policy_window():
    result = plan(provider=profile(context_window_tokens=300))
    assert result.coverage.status == "skipped" and not result.chunks
    assert "context_limit" in result.coverage.reasons


def test_filtered_and_budget_and_missing_coverage():
    text = addition("uv.lock") + addition("a.py") + addition("b.py")
    result = plan(text, rules=policy(max_chunks=1))
    assert (
        result.coverage.total_lines,
        result.coverage.included_lines,
        result.coverage.skipped_budget,
        result.coverage.skipped_filter,
    ) == (3, 1, 1, 1)
    assert result.coverage.reviewed_line_ratio == "1/3"
    assert [f.status for f in result.files] == ["skipped_filter", "included", "skipped_budget"]
    rules = policy()
    diff = prepare_diff(
        addition(), head_sha=SHA, policy=rules, expected_changed_lines=3, expected_files=2
    )
    missing = plan_chunks(
        diff, rules, profile(), system_prompt="Review", owner_remaining_usd="10.000000"
    )
    assert missing.coverage.missing_lines == 2 and missing.coverage.skipped_filter == 2
    assert missing.coverage.reviewed_line_ratio == "1/3"


def test_slice10_truncated_changes_remain_budget_skips():
    result = plan(rules=policy(max_changed_lines=2))
    assert result.coverage.total_lines == 5 and result.coverage.included_lines == 2
    assert result.coverage.skipped_budget == 3
    omitted = next(h for h in result.hunks if h.source_header is None)
    assert omitted.changed_lines == 3 and omitted.reason == "diff_line_limit"
    assert json.loads(result.chunks[0].payload)["format"] == "review_hunk_excerpts_v1"


def test_more_than_1000_lines_multiple_files():
    parts = []
    for i in range(12):
        path = f"src/f{i}.py"
        parts.append(f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n")
        for j in range(10):
            line = 1 + j * 20
            parts.append(f"@@ -{line},5 +{line},5 @@\n" + "-old\n" * 5 + "+中文🚀\n" * 5)
    result = plan(
        "".join(parts), rules=policy(max_request_input_tokens=9000, max_total_input_tokens=100000)
    )
    assert result.coverage.total_lines == 1200
    assert (
        result.coverage.included_lines
        + result.coverage.skipped_budget
        + result.coverage.skipped_filter
        == 1200
    )
    assert 0 < result.coverage.included_lines < 1200
    assert result.totals.input_tokens <= 100000
    assert all(c.reservation.input_tokens <= 9000 for c in result.chunks)
    assert len({h.id for c in result.chunks for h in c.hunks}) == sum(
        len(c.hunks) for c in result.chunks
    )


@pytest.mark.parametrize("text", ["ascii", "中文", "🚀", '"\\\n'])
def test_utf8_conservative_estimate(text):
    assert estimate_tokens(text) == len(text.encode("utf-8"))
    assert estimate_tokens(text) >= len(text)


def test_round_cost_up_never_down():
    p = profile(input_usd_per_million="0.000001", output_usd_per_million="0.000001")
    assert estimate_cost(1, 1, p) == "0.000001"


@pytest.mark.parametrize(
    ("changes", "payload", "reason"),
    [
        ({"max_request_input_tokens": 10}, "x", "request_input_limit"),
        ({"max_total_input_tokens": 10}, "x", "total_input_limit"),
        ({"max_total_output_tokens": 99}, "x", "total_output_limit"),
        ({"max_cost_usd": "0.000000"}, "x", "job_cost_limit"),
    ],
)
def test_reject_has_no_reservation_side_effects(changes, payload, reason):
    ledger = BudgetLedger(policy(**changes), profile(), owner_remaining_usd="20.000000")
    before = ledger.totals
    decision = ledger.reserve(payload)
    assert isinstance(decision, Rejection) and decision.reason == reason
    assert ledger.totals == before


def test_exact_boundary_and_no_silent_overrun():
    ledger = BudgetLedger(
        policy(max_total_input_tokens=11, max_total_output_tokens=100, max_cost_usd="0.000211"),
        profile(),
        owner_remaining_usd="20.000000",
    )
    assert isinstance(ledger.reserve("x"), Reservation)
    assert ledger.totals.estimated_cost_usd == "0.000211"
    before = ledger.totals
    assert isinstance(ledger.reserve("x"), Rejection)
    assert ledger.totals == before


def test_owner_remaining_and_daily_cap():
    assert plan(remaining="0.000000").coverage.status == "skipped"
    assert "owner_cost_limit" in plan(remaining="0.000000").coverage.reasons
    result = plan(rules=policy(max_owner_daily_cost_usd="0.000000"))
    assert "owner_cost_limit" in result.coverage.reasons


@pytest.mark.parametrize(
    "change",
    [
        {"token_count_mode": "provider_exact"},
        {"min_changed_lines": 10001},
        {"reserved_output_tokens": 1001},
        {"context_window_tokens": 100},
    ],
)
def test_bad_budget_config_fails_closed(change):
    with pytest.raises(ValueError):
        BudgetLedger(policy(**change), profile(), owner_remaining_usd="20.000000")


def test_profile_model_must_match():
    with pytest.raises(ValueError, match="provider_profile_mismatch"):
        plan(provider=profile(model="another-model"))


@pytest.mark.parametrize(
    "change",
    [
        {"framing_tokens": -1},
        {"framing_tokens": 100000},
        {"input_usd_per_million": "-1.000000"},
        {"context_window_tokens": True},
        {"pricing_version": ""},
    ],
)
def test_profile_validation(change):
    with pytest.raises(ValidationError):
        profile(**change)


def test_costs_sum_exactly_and_reservations_immutable():
    result = plan(addition("a.py") + addition("b.py"))
    assert Decimal(result.totals.estimated_cost_usd) == sum(
        Decimal(c.reservation.estimated_cost_usd) for c in result.chunks
    )
    with pytest.raises(ValidationError):
        result.totals.chunks = 999


def test_mutating_source_policy_does_not_change_ledger():
    rules = policy(max_chunks=1)
    ledger = BudgetLedger(rules, profile(), owner_remaining_usd="20.000000")
    rules.budgets.max_chunks = 100
    assert isinstance(ledger.reserve("x"), Reservation)
    assert isinstance(ledger.reserve("x"), Rejection)


def test_empty_and_all_filtered():
    assert plan("").coverage.status == "skipped"
    result = plan(addition("uv.lock"))
    assert not result.chunks and result.coverage.skipped_filter == 1
    assert result.totals.estimated_cost_usd == "0.000000"


def test_corrupt_aggregate_coverage_rejected():
    rules = policy()
    diff = prepare_diff(STANDARD, head_sha=SHA, policy=rules).model_copy(
        update={"included_changed_lines": 99}
    )
    with pytest.raises(ValueError, match="invalid_diff_coverage"):
        plan_chunks(diff, rules, profile(), system_prompt="Review", owner_remaining_usd="20.000000")


@pytest.mark.parametrize("bad", ["", None, 12])
def test_bad_request_payload_rejected_without_spend(bad):
    ledger = BudgetLedger(policy(), profile(), owner_remaining_usd="20.000000")
    with pytest.raises(ValueError, match="invalid_request_payload"):
        ledger.reserve(bad)
    assert ledger.totals.chunks == 0


@pytest.mark.parametrize("bad", [True, -1, 1.5])
def test_invalid_token_counts(bad):
    with pytest.raises(ValueError, match="invalid_token_count"):
        estimate_cost(bad, 1, profile())


@pytest.mark.parametrize(
    "change",
    [
        {"side": "LEFT"},
        {"position": 0},
        {"new_line": 999},
        {"comment_context": "bad header\n+hello"},
    ],
)
def test_corrupt_line_mapping_rejected(change):
    rules = policy()
    diff = prepare_diff(addition(), head_sha=SHA, policy=rules)
    line = diff.files[0].lines[0].model_copy(update=change)
    file = diff.files[0].model_copy(update={"lines": (line,)})
    diff = diff.model_copy(update={"files": (file,)})
    with pytest.raises(ValueError):
        plan_chunks(diff, rules, profile(), system_prompt="Review", owner_remaining_usd="20.000000")


@pytest.mark.parametrize("cap", ["max_changed_lines", "max_files"])
def test_incompatible_prepared_diff_policy_rejected(cap):
    diff = prepare_diff(addition("a.py") + addition("b.py"), head_sha=SHA, policy=policy())
    with pytest.raises(ValueError, match="diff_policy_mismatch"):
        plan_chunks(
            diff,
            policy(**{cap: 1}),
            profile(),
            system_prompt="Review",
            owner_remaining_usd="20.000000",
        )


def test_disabled_policy_does_not_reserve_budget():
    rules = policy()
    rules.enabled = False
    result = plan(rules=rules)
    assert result.coverage.skipped_filter == 5 and result.totals.chunks == 0


def test_output_reservation_charged_per_chunk_not_per_hunk():
    combined = plan()
    split = plan(rules=policy(max_request_input_tokens=combined.totals.input_tokens - 1))
    assert combined.totals.output_tokens == 100
    assert split.totals.output_tokens == 200


def test_expensive_output_alone_exhausts_cost_cap():
    result = plan(provider=profile(output_usd_per_million="1000000.000000"))
    assert result.coverage.status == "skipped"
    assert "job_cost_limit" in result.coverage.reasons
    assert result.totals.output_tokens == 0


def test_higher_provider_price_reduces_coverage():
    text = addition("a.py") + addition("b.py")
    cheap = plan(text)
    expensive = plan(text, provider=profile(input_usd_per_million="1000000.000000"))
    assert cheap.coverage.included_lines == 2 and expensive.coverage.included_lines == 0


@pytest.mark.parametrize("kind", ["added", "deleted", "renamed"])
def test_file_identity_and_null_ranges_survive_chunking(kind):
    text = addition("new.py")
    if kind == "deleted":
        text = "diff --git a/old.py b/old.py\ndeleted file mode 100644\n--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n"
    elif kind == "renamed":
        text = "diff --git a/old.py b/new.py\nrename from old.py\nrename to new.py\n--- a/old.py\n+++ b/new.py\n@@ -1 +1 @@\n-old\n+new\n"
    result = plan(text)
    hunk = result.chunks[0].hunks[0]
    assert hunk.old_path == (None if kind == "added" else "old.py")
    assert hunk.new_path == (None if kind == "deleted" else "new.py")
    assert hunk.old_range == (None if kind == "added" else (1, 1))
    assert hunk.new_range == (None if kind == "deleted" else (1, 1))
