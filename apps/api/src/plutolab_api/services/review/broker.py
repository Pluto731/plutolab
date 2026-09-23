"""Loopback Redis Streams transport; PostgreSQL remains the job authority.

Use a dedicated namespace and durable Redis persistence for process restarts.
Never trim pending entries. Publication consumers are outside this slice.
"""

import logging
import re
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from plutolab_api.services.review.worker import BrokerReceipt, WorkMessage

logger = logging.getLogger(__name__)


class RedisStreamsBroker:
    def __init__(
        self,
        client: Redis,
        *,
        stream: str,
        group: str,
        consumer: str,
        reclaim_ms: int = 60000,
        block_ms: int = 1000,
    ):
        for name in (stream, group, consumer):
            if not re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", name):
                raise ValueError("Invalid broker namespace")
        if type(reclaim_ms) is not int or not 1 <= reclaim_ms <= 3600000:
            raise ValueError("Invalid reclaim window")
        if type(block_ms) is not int or not 1 <= block_ms <= 1000:
            raise ValueError("Invalid read window")
        self.client = client
        self.stream, self.group, self.consumer = stream, group, consumer
        self.reclaim_ms, self.block_ms = reclaim_ms, block_ms
        self.cursor = "0-0"

    @classmethod
    def local(
        cls,
        url: str,
        *,
        stream: str,
        group: str,
        consumer: str,
        reclaim_ms: int = 60000,
        block_ms: int = 1000,
    ) -> "RedisStreamsBroker":
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"redis", "rediss"}
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Broker must use a loopback Redis origin")
        # Resolve localhost without DNS; never log a credential-bearing URL.
        userinfo, separator, host = parsed.netloc.rpartition("@")
        authority = (userinfo + separator if separator else "") + host.replace(
            "localhost", "127.0.0.1"
        )
        client = Redis.from_url(
            urlunsplit(parsed._replace(netloc=authority)),
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=2,
        )
        return cls(
            client,
            stream=stream,
            group=group,
            consumer=consumer,
            reclaim_ms=reclaim_ms,
            block_ms=block_ms,
        )

    async def initialize(self) -> None:
        try:
            await self.client.xgroup_create(self.stream, self.group, id="0-0", mkstream=True)
        except ResponseError as error:
            if not str(error).startswith("BUSYGROUP "):
                raise

    async def publish(self, message: WorkMessage) -> str:
        return await self.client.xadd(self.stream, message.model_dump(mode="json"))

    async def receive(self) -> BrokerReceipt | None:
        claimed = await self.client.xautoclaim(
            self.stream,
            self.group,
            self.consumer,
            self.reclaim_ms,
            start_id=self.cursor,
            count=1,
        )
        self.cursor = claimed[0]
        entries = claimed[1]
        if not entries:
            rows = await self.client.xreadgroup(
                self.group,
                self.consumer,
                {self.stream: ">"},
                count=1,
                block=self.block_ms,
            )
            entries = rows[0][1] if rows else []
        if not entries:
            return None
        receipt_id, payload = entries[0]
        try:
            message = WorkMessage.model_validate(payload)
        except ValidationError:
            # Retain poison data in the stream for local inspection, but prevent
            # endless pending redelivery. Never emit payloads to logs.
            await self.client.xack(self.stream, self.group, receipt_id)
            logger.warning("review_broker_invalid_message")
            return None
        return BrokerReceipt(receipt_id, message)

    async def acknowledge(self, receipt: BrokerReceipt) -> None:
        # One dedicated group owns this stream. Atomic ACK+delete avoids orphaned
        # acknowledged entries while never deleting an unacknowledged message.
        await self.client.eval(
            "local n=redis.call('XACK',KEYS[1],ARGV[1],ARGV[2]); "
            "if n==1 then redis.call('XDEL',KEYS[1],ARGV[2]); end; return n",
            1,
            self.stream,
            self.group,
            receipt.receipt_id,
        )

    async def close(self) -> None:
        await self.client.aclose()
