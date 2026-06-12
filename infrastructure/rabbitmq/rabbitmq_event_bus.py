"""RabbitMQ EventBus adapter implementation."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractRobustConnection,
)
from pydantic import BaseModel, Field

from shared.contracts import Event, EventBus
from shared.contracts.interfaces.event_bus import EventHandler

logger = logging.getLogger(__name__)


class RabbitMQConfig(BaseModel):
    url: str = Field(
        default="amqp://rootpilot:rootpilot@localhost:5672/",
        description="RabbitMQ AMQP connection URL.",
    )
    exchange_name: str = Field(
        default="rootpilot.events",
        description="Default exchange name for event publishing.",
    )
    exchange_type: str = Field(
        default="topic",
        description="Exchange type (topic, direct, fanout).",
    )
    prefetch_count: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="QoS prefetch count for consumers.",
    )
    connection_timeout: float = Field(
        default=10.0,
        ge=1.0,
        description="Connection timeout in seconds.",
    )


class _SubscriberInfo:
    __slots__ = ("queue_name", "channel", "consumer_tag", "topic")

    def __init__(
        self,
        topic: str,
        queue_name: str,
        channel: AbstractChannel,
        consumer_tag: str,
    ) -> None:
        self.topic = topic
        self.queue_name = queue_name
        self.channel = channel
        self.consumer_tag = consumer_tag

    async def close(self) -> None:
        if not self.channel.is_closed:
            await self.channel.close()


class RabbitMQEventBus(EventBus):
    def __init__(self, config: RabbitMQConfig | None = None) -> None:
        self._config = config or RabbitMQConfig()
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: AbstractExchange | None = None
        self._subscribers: dict[str, _SubscriberInfo] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    async def start(self) -> None:
        async with self._lock:
            if self._connection is not None and not self._connection.is_closed:
                return

            self._closed = False
            self._connection = await aio_pika.connect_robust(
                self._config.url,
                timeout=self._config.connection_timeout,
            )
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=self._config.prefetch_count)
            self._exchange = await self._channel.declare_exchange(
                name=self._config.exchange_name,
                type=self._config.exchange_type,
                durable=True,
            )

            logger.info(
                "Connected to RabbitMQ",
                extra={"exchange": self._config.exchange_name},
            )

    async def close(self) -> None:
        async with self._lock:
            self._closed = True

            for subscriber in self._subscribers.values():
                await subscriber.close()
            self._subscribers.clear()

            if self._channel is not None and not self._channel.is_closed:
                await self._channel.close()

            if self._connection is not None and not self._connection.is_closed:
                await self._connection.close()
                logger.info("RabbitMQ connection closed")

            self._connection = None
            self._channel = None
            self._exchange = None

    async def publish(self, event: Event, topic: str | None = None) -> None:
        if self._closed:
            raise RuntimeError("EventBus is closed")

        routing_key = topic or event.topic
        exchange = await self._resolve_exchange()

        message = aio_pika.Message(
            body=event.model_dump_json().encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await exchange.publish(
            message=message,
            routing_key=routing_key,
        )

        logger.debug(
            "Published event",
            extra={"routing_key": routing_key, "event_id": event.id, "source": event.source},
        )

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        if self._closed:
            raise RuntimeError("EventBus is closed")
        if self._connection is None or self._connection.is_closed:
            raise RuntimeError("EventBus is not connected")

        channel = await self._connection.channel()
        await channel.set_qos(prefetch_count=self._config.prefetch_count)

        queue = await channel.declare_queue(exclusive=True, auto_delete=True)

        exchange = await self._resolve_exchange()
        await queue.bind(exchange=exchange, routing_key=topic)

        consumer_tag = await queue.consume(
            callback=self._make_handler(handler),
        )

        info = _SubscriberInfo(
            topic=topic,
            queue_name=queue.name,
            channel=channel,
            consumer_tag=consumer_tag,
        )
        self._subscribers[topic] = info

        logger.info(
            "Subscribed to topic",
            extra={"topic": topic, "queue": queue.name},
        )

    async def health(self) -> bool:
        if self._closed:
            return False
        if self._connection is None or self._connection.is_closed:
            return False
        return True

    async def _resolve_exchange(self) -> AbstractExchange:
        async with self._lock:
            if self._exchange is None:
                if self._connection is None or self._connection.is_closed:
                    raise RuntimeError("EventBus is not connected")
                channel = await self._connection.channel()
                self._exchange = await channel.declare_exchange(
                    name=self._config.exchange_name,
                    type=self._config.exchange_type,
                    durable=True,
                )
                await channel.close()
        return self._exchange

    def _make_handler(
        self, handler: EventHandler
    ) -> Callable[[AbstractIncomingMessage], Awaitable[None]]:
        async def _on_message(message: AbstractIncomingMessage) -> None:
            async with message.process(requeue=True):
                try:
                    event = Event.model_validate_json(message.body)
                    await handler(event)
                except Exception:
                    logger.exception("Failed to process event message")

        return _on_message
