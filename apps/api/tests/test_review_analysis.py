"""Local mock tests for structured review parsing and restricted syntax checks."""

import asyncio
import socket

import pytest
from pydantic import ValidationError

from plutolab_api.schemas.review_analysis import FindingCandidate
from plutolab_api.services.review.analyzer import analyze_plan, parse_provider_response
from plutolab_api.services.review.linter import check_python_syntax
from tests.test_review_chunking_budget import plan as make_plan
from tests.test_review_diff import STANDARD


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Slice 12 is local only")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def response(*, path="src/a.py", line=11, side="RIGHT", **changes):
    finding = {
        "file_path": path,
        "line": line,
        "side": side,
        "severity": "HIGH",
        "category": "security",
        "title": "Unsafe operation",
        "comment_body": "Validate this value before use.",
        "suggestion": "Add a validation guard.",
    }
    finding.update(changes)
    return {"summary": "Review summary", "findings": [finding]}


class MockProvider:
    def __init__(self, *results):
        self.results = list(results)
        self.payloads = []

    async def complete(self, payload):
        self.payloads.append(payload)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_strict_candidate_schema_rejects_unknown_or_unsafe_fields():
    candidate = response()["findings"][0]
    assert FindingCandidate.model_validate(candidate).file_path == "src/a.py"
    for key, value in (("extra", True), ("file_path", "../secret.py"), ("line", True)):
        invalid = dict(candidate)
        invalid[key] = value
        with pytest.raises(ValidationError):
            FindingCandidate.model_validate(invalid)


def test_json_parser_accepts_fence_and_rejects_bad_or_duplicate_json():
    import json

    raw = json.dumps(response())
    assert parse_provider_response(f"```json\n{raw}\n```").summary == "Review summary"
    for invalid in (
        "{not json}",
        '{"summary":"x","summary":"y","findings":[]}',
        '{"summary":"x","findings":[],"untrusted":"extra"}',
        '{"summary":"x","findings":[{"file_path":"a","line":0}]}',
        '{"summary":"x","findings":[],"n":NaN}',
        '{"summary":"\\ud800","findings":[]}',
    ):
        with pytest.raises(ValueError, match="invalid_provider_response"):
            parse_provider_response(invalid)


@pytest.mark.asyncio
async def test_structured_finding_is_clamped_to_a_verified_diff_position():
    import json

    provider = MockProvider(json.dumps(response(line=999)))
    result = await analyze_plan(provider, make_plan())
    assert result.status == "complete"
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert (finding.file_path, finding.line, finding.side) == ("src/a.py", 31, "RIGHT")
    assert finding.line_was_clamped is True
    assert finding.evidence == "after"
    assert len(finding.fingerprint) == 64


@pytest.mark.asyncio
async def test_exact_line_is_preserved_and_duplicate_findings_are_deduplicated():
    import json

    data = response(line=12)
    data["findings"].append(dict(data["findings"][0]))
    result = await analyze_plan(MockProvider(json.dumps(data)), make_plan())
    assert result.status == "complete"
    assert len(result.findings) == 1
    assert result.findings[0].line == 12
    assert result.findings[0].line_was_clamped is False


@pytest.mark.asyncio
async def test_out_of_diff_path_is_dropped_and_coverage_becomes_partial():
    import json

    result = await analyze_plan(
        MockProvider(json.dumps(response(path="other/file.py"))), make_plan()
    )
    assert result.status == "partial"
    assert result.findings == ()
    assert result.warnings == ("finding_outside_prepared_diff",)


@pytest.mark.asyncio
async def test_malformed_provider_output_degrades_and_records_safe_failure():
    result = await analyze_plan(MockProvider("not json"), make_plan())
    assert result.status == "partial"
    assert result.failed_chunks == 1
    assert result.findings == ()
    assert result.warnings == ("provider_response_invalid",)


@pytest.mark.asyncio
async def test_provider_failure_does_not_raise_or_leak_exception_text():
    result = await analyze_plan(MockProvider(RuntimeError("secret token text")), make_plan())
    assert result.status == "partial"
    assert result.failed_chunks == 1
    assert result.warnings == ("provider_unavailable",)
    assert "secret" not in str(result.model_dump())


@pytest.mark.asyncio
async def test_timeout_is_bounded_and_degrades_to_partial():
    class SlowProvider:
        async def complete(self, payload):
            await asyncio.sleep(1.1)
            return "{}"

    result = await analyze_plan(SlowProvider(), make_plan(), timeout_seconds=1)
    assert result.failed_chunks == 1
    assert result.warnings == ("provider_timeout",)
    assert result.status == "partial"


def test_static_checks_are_opt_in_and_never_execute_source():
    sources = {"src/a.py": "value = 1\n"}
    paths = frozenset(sources)
    assert check_python_syntax(sources, allowed_paths=paths).status == "disabled"
    assert check_python_syntax(sources, allowed_paths=paths, enabled=True).status == "complete"
    unsafe = "raise RuntimeError('must not execute')\nvalue =\n"
    result = check_python_syntax({"src/a.py": unsafe}, allowed_paths=paths, enabled=True)
    assert result.status == "complete"
    assert len(result.issues) == 1 and result.issues[0].line == 2


def test_static_checks_restrict_scope_and_degrade_on_missing_or_oversized_source():
    assert (
        check_python_syntax(None, allowed_paths=frozenset({"a.py"}), enabled=True).status
        == "skipped"
    )
    result = check_python_syntax(
        {"other.py": "x =", "src/a.py": "x ="},
        allowed_paths=frozenset({"src/a.py"}),
        enabled=True,
    )
    assert result.status == "complete"
    assert [issue.path for issue in result.issues] == ["src/a.py"]
    oversized = check_python_syntax(
        {"src/a.py": "x = 1\n" * 200_000},
        allowed_paths=frozenset({"src/a.py"}),
        enabled=True,
    )
    assert oversized.status == "partial"
    assert oversized.warnings == ("source_size_limit_exceeded",)


@pytest.mark.asyncio
async def test_optional_static_issue_is_mapped_to_changed_line():
    import json

    provider = MockProvider(json.dumps({"summary": "Checked", "findings": []}))
    result = await analyze_plan(
        provider,
        make_plan(STANDARD),
        static_sources={"src/a.py": "ok = 1\ninvalid =\n"},
        include_static_checks=True,
    )
    assert result.static_check_status == "complete"
    assert result.status == "complete"
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.category == "quality"
    assert finding.line == 10
    assert finding.line_was_clamped is True


def test_timeout_bounds_are_validated():
    with pytest.raises(ValueError, match="timeout_seconds_out_of_range"):
        asyncio.run(analyze_plan(MockProvider(), make_plan(), timeout_seconds=0))
