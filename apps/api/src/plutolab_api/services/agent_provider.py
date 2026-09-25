"""Bounded OpenAI text adapter. All tests inject httpx.MockTransport."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from plutolab_api.schemas.agent_run import ErrorCode


class ProviderError(Exception):
    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ProviderRequest:
    key: SecretStr = field(repr=False)
    messages: list[dict[str, object]] = field(repr=False)
    tools: list[dict[str, object]] = field(default_factory=list)
    model: Literal["gpt-4o-mini"] = "gpt-4o-mini"
    max_output_tokens: int = 2048

    def payload(self) -> dict[str, object]:
        value: dict[str, object] = {
            "model": self.model,
            "messages": self.messages,
            "max_completion_tokens": self.max_output_tokens,
            "n": 1,
            "stream": False,
            "store": False,
        }
        if self.tools:
            value.update(tools=self.tools, parallel_tool_calls=False)
        return value


class FunctionCall(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    arguments: str = Field(max_length=4096, repr=False)


class ToolInvocation(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    type: Literal["function"]
    function: FunctionCall


class Message(BaseModel):
    content: str | None = Field(default=None, max_length=32000, repr=False)
    tool_calls: list[ToolInvocation] = Field(default_factory=list, max_length=1)
    refusal: str | None = Field(default=None, repr=False)


class Choice(BaseModel):
    message: Message
    finish_reason: Literal["stop", "tool_calls", "length", "content_filter"]


class Usage(BaseModel):
    model_config = ConfigDict(strict=True)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)


class Completion(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    choices: list[Choice] = Field(min_length=1, max_length=1)
    usage: Usage


@dataclass(frozen=True)
class ProviderReply:
    text: str | None = field(repr=False)
    tool: ToolInvocation | None
    input_tokens: int
    output_tokens: int


class TextProvider(Protocol):
    requires_api_key: bool

    async def complete(self, request: ProviderRequest) -> ProviderReply: ...


class OpenAITextProvider:
    requires_api_key = True

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def complete(self, request: ProviderRequest) -> ProviderReply:
        if request.model != "gpt-4o-mini":
            raise ProviderError("unsupported_model")
        if (
            type(request.max_output_tokens) is not int
            or not 1 <= request.max_output_tokens <= 16384
        ):
            raise ProviderError("budget_exceeded")
        try:
            async with (
                httpx.AsyncClient(
                    transport=self._transport, timeout=120, follow_redirects=False, trust_env=False
                ) as client,
                client.stream(
                    "POST",
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {request.key.get_secret_value()}"},
                    json=request.payload(),
                ) as response,
            ):
                if response.status_code == 429:
                    raise ProviderError("provider_rate_limit")
                if response.status_code >= 500:
                    raise ProviderError("provider_unavailable")
                if response.status_code in {401, 403}:
                    raise ProviderError("provider_auth")
                if response.status_code != 200:
                    raise ProviderError("provider_invalid")
                raw = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    raw.extend(chunk)
                    if len(raw) > 262144:
                        raise ProviderError("provider_invalid")
            completion = Completion.model_validate_json(bytes(raw))
            choice = completion.choices[0]
            if choice.message.refusal or choice.finish_reason in {"length", "content_filter"}:
                raise ProviderError("provider_invalid")
            tool = choice.message.tool_calls[0] if choice.message.tool_calls else None
            if (tool is not None) != (choice.finish_reason == "tool_calls"):
                raise ProviderError("provider_invalid")
            if tool is None and not choice.message.content:
                raise ProviderError("provider_invalid")
            return ProviderReply(
                choice.message.content,
                tool,
                completion.usage.prompt_tokens,
                completion.usage.completion_tokens,
            )
        except httpx.TimeoutException as exc:
            raise ProviderError("provider_timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("provider_unavailable") from exc
        except (ValidationError, ValueError) as exc:
            raise ProviderError("provider_invalid") from exc
