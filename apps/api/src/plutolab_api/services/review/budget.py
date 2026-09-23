"""Pure local admission/reservation. No live pricing or provider-exact token claims.

The UTF-8 byte estimator deliberately overcounts ordinary text; its error is not
calibrated against a live provider. The caller supplies model limits, versioned
prices and framing overhead, and must send the exact serialized request counted
here, with the reserved output cap. This is a plan, not a billing/spend ledger.
"""

from decimal import ROUND_CEILING, Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from plutolab_api.schemas.review import MoneyUSD, NonNegativeInt, PositiveInt, ReviewPolicy

_MICRO = Decimal("0.000001")
_MILLION = Decimal(1_000_000)


class BudgetContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ProviderProfile(BudgetContract):
    """Required configuration, not hard-coded/current provider specifications."""

    provider: Literal["anthropic"]
    model: str = Field(min_length=1, max_length=200)
    pricing_version: str = Field(min_length=1, max_length=200)
    context_window_tokens: PositiveInt
    max_output_tokens: PositiveInt
    framing_tokens: NonNegativeInt
    input_usd_per_million: MoneyUSD
    output_usd_per_million: MoneyUSD

    @model_validator(mode="after")
    def valid_window(self) -> "ProviderProfile":
        if self.framing_tokens >= self.context_window_tokens:
            raise ValueError("invalid_provider_window")
        return self


class Reservation(BudgetContract):
    input_tokens: PositiveInt
    output_tokens: PositiveInt
    estimated_cost_usd: MoneyUSD


class Rejection(BudgetContract):
    reason: Literal[
        "request_input_limit",
        "context_limit",
        "chunk_limit",
        "total_input_limit",
        "total_output_limit",
        "job_cost_limit",
        "owner_cost_limit",
    ]


class BudgetTotals(BudgetContract):
    chunks: NonNegativeInt = 0
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    estimated_cost_usd: MoneyUSD = "0.000000"


def estimate_tokens(text: str) -> int:
    """Conservative UTF-8 bytes, not characters/4, tiktoken, or exact usage."""
    return len(text.encode("utf-8"))


def estimate_cost(input_tokens: int, output_tokens: int, profile: ProviderProfile) -> str:
    for value in (input_tokens, output_tokens):
        if type(value) is not int or value < 0:
            raise ValueError("invalid_token_count")
    amount = (
        Decimal(input_tokens) * Decimal(profile.input_usd_per_million)
        + Decimal(output_tokens) * Decimal(profile.output_usd_per_million)
    ) / _MILLION
    return format(amount.quantize(_MICRO, rounding=ROUND_CEILING), ".6f")


class BudgetLedger:
    """Per-plan reservations; reject without mutating totals. Never refunds estimates.

    owner_remaining_usd must come from a trusted caller. This local object cannot
    arbitrate concurrent jobs or account for remote usage/retries; reserve those
    atomically in the future execution layer before making provider requests.
    """

    def __init__(self, policy: ReviewPolicy, profile: ProviderProfile, *, owner_remaining_usd: str):
        policy = ReviewPolicy.model_validate(policy.model_dump())
        profile = ProviderProfile.model_validate(profile.model_dump())
        self._budgets = policy.budgets.model_copy(deep=True)
        self._profile = profile
        b = self._budgets
        if policy.provider != profile.provider or policy.model != profile.model:
            raise ValueError("provider_profile_mismatch")
        if b.token_count_mode != "conservative_estimate":
            raise ValueError("provider_exact_counter_unavailable")
        if (
            b.min_changed_lines > b.max_changed_lines
            or b.reserved_output_tokens > profile.max_output_tokens
        ):
            raise ValueError("invalid_budget_configuration")
        if b.reserved_output_tokens + profile.framing_tokens >= min(
            b.context_window_tokens, profile.context_window_tokens
        ):
            raise ValueError("invalid_budget_window")
        remaining = TypeAdapter(MoneyUSD).validate_python(owner_remaining_usd, strict=True)
        self._owner_limit = min(Decimal(remaining), Decimal(b.max_owner_daily_cost_usd))
        self._totals = BudgetTotals()

    @property
    def totals(self) -> BudgetTotals:
        return self._totals

    def preview(self, payload: str) -> Reservation | Rejection:
        if not isinstance(payload, str) or not payload:
            raise ValueError("invalid_request_payload")
        b, p, t = self._budgets, self._profile, self._totals
        inputs = estimate_tokens(payload) + p.framing_tokens
        outputs = b.reserved_output_tokens
        cost = estimate_cost(inputs, outputs, p)
        checks = (
            (inputs > b.max_request_input_tokens, "request_input_limit"),
            (
                inputs + outputs > min(b.context_window_tokens, p.context_window_tokens),
                "context_limit",
            ),
            (t.chunks >= b.max_chunks, "chunk_limit"),
            (t.input_tokens + inputs > b.max_total_input_tokens, "total_input_limit"),
            (t.output_tokens + outputs > b.max_total_output_tokens, "total_output_limit"),
            (
                Decimal(t.estimated_cost_usd) + Decimal(cost) > Decimal(b.max_cost_usd),
                "job_cost_limit",
            ),
            (Decimal(t.estimated_cost_usd) + Decimal(cost) > self._owner_limit, "owner_cost_limit"),
        )
        for rejected, reason in checks:
            if rejected:
                return Rejection.model_validate({"reason": reason})
        return Reservation(input_tokens=inputs, output_tokens=outputs, estimated_cost_usd=cost)

    def reserve(self, payload: str) -> Reservation | Rejection:
        decision = self.preview(payload)
        if isinstance(decision, Reservation):
            t = self._totals
            self._totals = BudgetTotals(
                chunks=t.chunks + 1,
                input_tokens=t.input_tokens + decision.input_tokens,
                output_tokens=t.output_tokens + decision.output_tokens,
                estimated_cost_usd=format(
                    Decimal(t.estimated_cost_usd) + Decimal(decision.estimated_cost_usd), ".6f"
                ),
            )
        return decision
