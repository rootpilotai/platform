"""Tests for the RabbitMQ EventBus adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrastructure.rabbitmq.rabbitmq_event_bus import RabbitMQConfig, RabbitMQEventBus
from shared.contracts import Event
from shared.contracts.interfaces.event_bus import EventHandler


@pytest.fixture
def config() -> RabbitMQConfig:
    return RabbitMQConfig(url="amqp://test:test@localhost:5672/test")


@pytest.fixture
def event() -> Event:
    return Event(source="test-svc", topic="test.event", payload={"key": "value"})


class TestRabbitMQConfig:
    def test_default_url(self) -> None:
        cfg = RabbitMQConfig()
        assert cfg.url == "amqp://rootpilot:rootpilot@localhost:5672/"

    def test_custom_url(self) -> None:
        cfg = RabbitMQConfig(url="amqp://user:pass@host:5672/vhost")
        assert cfg.url == "amqp://user:pass@host:5672/vhost"

    def test_exchange_defaults_to_topic(self) -> None:
        cfg = RabbitMQConfig()
        assert cfg.exchange_type == "topic"


class TestRabbitMQEventBus:
    async def test_start_connects_and_declares_exchange(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)

        mock_channel = AsyncMock()
        mock_exchange = MagicMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_channel.is_closed = False

        mock_connection = AsyncMock()
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        mock_connection.is_closed = False

        with patch("aio_pika.connect_robust", AsyncMock(return_value=mock_connection)):
            await bus.start()

        assert bus._connection is mock_connection
        assert bus._channel is mock_channel
        assert bus._exchange is mock_exchange

        mock_channel.set_qos.assert_awaited_once_with(prefetch_count=10)
        mock_channel.declare_exchange.assert_awaited_once_with(
            name="rootpilot.events",
            type="topic",
            durable=True,
        )

    async def test_start_is_idempotent(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)

        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=MagicMock())
        mock_channel.is_closed = False

        mock_connection = AsyncMock()
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        mock_connection.is_closed = False

        with patch("aio_pika.connect_robust", AsyncMock(return_value=mock_connection)):
            await bus.start()

        await bus.start()

    async def test_start_reconnects_if_connection_died(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)

        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=MagicMock())
        mock_channel.is_closed = False

        mock_connection = AsyncMock()
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        mock_connection.is_closed = False

        with patch("aio_pika.connect_robust", AsyncMock(return_value=mock_connection)):
            await bus.start()

        bus._connection.is_closed = True

        new_channel = AsyncMock()
        new_channel.declare_exchange = AsyncMock(return_value=MagicMock())
        new_channel.is_closed = False

        new_connection = AsyncMock()
        new_connection.channel = AsyncMock(return_value=new_channel)
        new_connection.is_closed = False

        with patch("aio_pika.connect_robust", AsyncMock(return_value=new_connection)):
            await bus.start()

        assert bus._connection is new_connection

    async def test_close_cleans_up_connection(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)

        mock_channel = AsyncMock()
        mock_channel.is_closed = False

        mock_connection = AsyncMock()
        mock_connection.is_closed = False

        bus._channel = mock_channel
        bus._connection = mock_connection
        bus._exchange = MagicMock()

        await bus.close()

        assert bus._connection is None
        assert bus._channel is None
        assert bus._exchange is None
        assert bus._closed is True
        mock_channel.close.assert_awaited_once()
        mock_connection.close.assert_awaited_once()

    async def test_close_skips_if_already_closed(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)
        bus._closed = True

        mock_channel = AsyncMock()
        bus._channel = mock_channel

        mock_connection = AsyncMock()
        bus._connection = mock_connection

        await bus.close()
        mock_channel.close.assert_not_awaited()
        mock_connection.close.assert_not_awaited()

    async def test_close_closes_subscriber_channels(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)

        sub_channel = AsyncMock()
        sub_channel.is_closed = False

        sub_info = AsyncMock()
        sub_info.close = AsyncMock()

        bus._subscribers = {"test.topic": sub_info}
        bus._channel = AsyncMock()
        bus._channel.is_closed = False
        bus._connection = AsyncMock()
        bus._connection.is_closed = False

        await bus.close()

        sub_info.close.assert_awaited_once()

    async def test_publish_serializes_event_and_publishes(self, config: RabbitMQConfig, event: Event) -> None:
        bus = RabbitMQEventBus(config=config)

        mock_exchange = AsyncMock()
        mock_exchange.is_closed = False
        bus._exchange = mock_exchange
        bus._connection = AsyncMock()
        bus._connection.is_closed = False

        await bus.publish(event)

        mock_exchange.publish.assert_awaited_once()
        call_args = mock_exchange.publish.await_args
        assert call_args is not None

        message = call_args.kwargs["message"]
        routing_key = call_args.kwargs["routing_key"]

        assert routing_key == "test.event"
        assert message.body == event.model_dump_json().encode("utf-8")
        assert message.content_type == "application/json"

    async def test_publish_with_custom_topic(self, config: RabbitMQConfig, event: Event) -> None:
        bus = RabbitMQEventBus(config=config)

        mock_exchange = AsyncMock()
        mock_exchange.is_closed = False
        bus._exchange = mock_exchange
        bus._connection = AsyncMock()
        bus._connection.is_closed = False

        await bus.publish(event, topic="custom.route")

        mock_exchange.publish.assert_awaited_once()
        routing_key = mock_exchange.publish.await_args.kwargs["routing_key"]
        assert routing_key == "custom.route"

    async def test_publish_raises_when_closed(self, config: RabbitMQConfig, event: Event) -> None:
        bus = RabbitMQEventBus(config=config)
        bus._closed = True

        with pytest.raises(RuntimeError, match="EventBus is closed"):
            await bus.publish(event)

    async def test_publish_raises_when_not_connected(self, config: RabbitMQConfig, event: Event) -> None:
        bus = RabbitMQEventBus(config=config)

        with pytest.raises(RuntimeError, match="not connected"):
            await bus.publish(event)

    async def test_subscribe_declares_queue_and_binds(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)

        mock_channel = AsyncMock()
        mock_channel.is_closed = False
        mock_queue = AsyncMock()
        mock_queue.name = "test-queue"
        mock_queue.consume = AsyncMock(return_value="consumer-tag")

        mock_channel.declare_queue = AsyncMock(return_value=mock_queue)

        mock_exchange = MagicMock()

        bus._connection = AsyncMock()
        bus._connection.channel = AsyncMock(return_value=mock_channel)
        bus._connection.is_closed = False

        handler: EventHandler = AsyncMock()

        with patch.object(bus, "_resolve_exchange", AsyncMock(return_value=mock_exchange)):
            await bus.subscribe("test.route", handler)

        mock_channel.declare_queue.assert_awaited_once_with(exclusive=True, auto_delete=True)
        mock_queue.bind.assert_awaited_once_with(exchange=mock_exchange, routing_key="test.route")
        mock_queue.consume.assert_awaited_once()
        assert "test.route" in bus._subscribers
        assert bus._subscribers["test.route"].consumer_tag == "consumer-tag"

    async def test_subscribe_raises_when_closed(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)
        bus._closed = True

        with pytest.raises(RuntimeError, match="EventBus is closed"):
            await bus.subscribe("test", AsyncMock())

    async def test_subscribe_raises_when_not_connected(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)

        with pytest.raises(RuntimeError, match="not connected"):
            await bus.subscribe("test", AsyncMock())

    async def test_health_returns_true_when_connected(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)

        bus._connection = MagicMock()
        bus._connection.is_closed = False
        bus._closed = False

        assert await bus.health() is True

    async def test_health_returns_false_when_closed(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)
        bus._closed = True
        assert await bus.health() is False

    async def test_health_returns_false_when_no_connection(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)
        bus._connection = None
        assert await bus.health() is False

    async def test_health_returns_false_when_disconnected(self, config: RabbitMQConfig) -> None:
        bus = RabbitMQEventBus(config=config)
        bus._connection = MagicMock()
        bus._connection.is_closed = True
        bus._closed = False

        assert await bus.health() is False

    async def test_make_handler_calls_handler_on_message(self, config: RabbitMQConfig, event: Event) -> None:
        bus = RabbitMQEventBus(config=config)

        handler: EventHandler = AsyncMock()
        wrapped = bus._make_handler(handler)

        mock_message = AsyncMock()
        mock_message.body = event.model_dump_json().encode("utf-8")
        mock_message.process = MagicMock()
        mock_message.process.return_value.__aenter__ = AsyncMock()
        mock_message.process.return_value.__aexit__ = AsyncMock()

        await wrapped(mock_message)

        handler.assert_awaited_once()
        called_event = handler.await_args.args[0]
        assert isinstance(called_event, Event)
        assert called_event.id == event.id
        assert called_event.source == event.source
        assert called_event.topic == event.topic

    async def test_make_handler_does_not_raise_on_failure(self, config: RabbitMQConfig, event: Event) -> None:
        bus = RabbitMQEventBus(config=config)

        handler: EventHandler = AsyncMock(side_effect=ValueError("handler error"))
        wrapped = bus._make_handler(handler)

        mock_message = AsyncMock()
        mock_message.body = event.model_dump_json().encode("utf-8")
        mock_message.process = MagicMock()
        mock_message.process.return_value.__aenter__ = AsyncMock()
        mock_message.process.return_value.__aexit__ = AsyncMock()

        await wrapped(mock_message)

        handler.assert_awaited_once()
