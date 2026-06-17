# ruff: noqa: N801, N802, RUF012
# These protobuf mock classes intentionally mirror the OTLP proto naming.
from __future__ import annotations

from typing import Any

from app.services.otel_normalizer import OtelNormalizer

from shared.contracts.events.enums import Severity
from shared.domain.timeline.enums import TimelineEventCategory


def _make_attrs(**kwargs: str) -> list[Any]:
    class _Value:
        def __init__(self, val: Any) -> None:
            self._val = val
            self._fields: dict[str, bool] = {}

        def _set_field(self, name: str) -> None:
            self._fields[name] = True

        def HasField(self, field: str) -> bool:
            return self._fields.get(field, False)

        def __getattr__(self, name: str) -> Any:
            if name in ("string_value", "int_value", "double_value", "bool_value"):
                return self._val
            return None

    class _Attr:
        def __init__(self, key: str, val: Any) -> None:
            self.key = key
            self.value = _Value(val)
            if isinstance(val, str):
                self.value._set_field("string_value")
            elif isinstance(val, bool):
                self.value._set_field("bool_value")
            elif isinstance(val, int):
                self.value._set_field("int_value")
            elif isinstance(val, float):
                self.value._set_field("double_value")

    return [_Attr(k, v) for k, v in kwargs.items()]


def _make_dp(
    value: float,
    attrs: list[Any] | None = None,
    time_unix_nano: int = 1700000000000000000,
) -> Any:
    dp = type("_DP", (), {"HasField": lambda self, f: f == "as_double"})()
    dp.as_double = value
    dp.as_int = int(value)
    dp.attributes = attrs or []
    dp.time_unix_nano = time_unix_nano
    return dp


def _make_resource(attrs: list[Any] | None = None) -> Any:
    class _Resource:
        attributes = attrs or []

    return _Resource()


# ------------------------------------------------------------------
# Metric tests
# ------------------------------------------------------------------


def test_normalize_gauge_metric() -> None:
    normalizer = OtelNormalizer(source="test", latency_threshold_ms=1000)

    class _Metric:
        name = "cpu.usage"
        unit = "%"
        description = "CPU usage percentage"

        class gauge:
            data_points = [_make_dp(85.5, attrs=_make_attrs(host="web-1"))]

        def HasField(self, field: str) -> bool:
            return field == "gauge"

    class _SM:
        metrics = [_Metric()]

    class _RM:
        resource = _make_resource()
        scope_metrics = [_SM()]

    events = normalizer.normalize_metrics([_RM()])
    assert len(events) == 1
    ev = events[0]
    assert ev.metric == "cpu.usage"
    assert ev.value == 85.5
    assert ev.unit == "%"
    assert ev.tags.get("host") == "web-1"
    assert ev.source == "test"
    assert ev.severity == Severity.INFO


def test_normalize_sum_metric() -> None:
    normalizer = OtelNormalizer(source="test")

    class _Metric:
        name = "http.requests.total"
        unit = "count"
        description = "Total HTTP requests"

        class sum:
            data_points = [_make_dp(42.0)]

        def HasField(self, field: str) -> bool:
            return field == "sum"

    class _SM:
        metrics = [_Metric()]

    class _RM:
        resource = _make_resource()
        scope_metrics = [_SM()]

    events = normalizer.normalize_metrics([_RM()])
    assert len(events) == 1
    assert events[0].value == 42.0


def test_normalize_histogram_metric() -> None:
    normalizer = OtelNormalizer(source="test")

    class _DP:
        count = 10
        sum = 500.0
        attributes = []
        time_unix_nano = 1700000000000000000

        def HasField(self, field: str) -> bool:
            return field in ("sum", "count")

    class _Metric:
        name = "request.duration"
        unit = "ms"

        class histogram:
            data_points = [_DP()]

        def HasField(self, field: str) -> bool:
            return field == "histogram"

    class _SM:
        metrics = [_Metric()]

    class _RM:
        resource = _make_resource()
        scope_metrics = [_SM()]

    events = normalizer.normalize_metrics([_RM()])
    assert len(events) == 2
    assert events[0].metric == "request.duration"
    assert events[1].value == 50.0


def test_metric_anomaly_classification() -> None:
    normalizer = OtelNormalizer(source="test")

    class _Metric:
        name = "error.rate"
        unit = "%"

        class gauge:
            data_points = [_make_dp(15.0)]

        def HasField(self, field: str) -> bool:
            return field == "gauge"

    class _SM:
        metrics = [_Metric()]

    class _RM:
        resource = _make_resource()
        scope_metrics = [_SM()]

    events = normalizer.normalize_metrics([_RM()])
    assert len(events) == 1
    assert events[0].severity == Severity.ERROR
    assert events[0].__otel_category__ == TimelineEventCategory.FAILURE


# ------------------------------------------------------------------
# Span tests
# ------------------------------------------------------------------


def _make_span(
    name: str = "test-span",
    trace_id: bytes = b"\x01" * 16,
    span_id: bytes = b"\x02" * 8,
    parent_span_id: bytes = b"\x03" * 8,
    status_code: int = 0,
    status_message: str = "",
    start_time: int = 1700000000000000000,
    end_time: int = 1700000000500000000,
    attrs: list[Any] | None = None,
    events: list[Any] | None = None,
) -> Any:
    status = type("_Status", (), {"HasField": lambda self, f: True})()
    status.code = status_code
    status.message = status_message

    span = type("_Span", (), {"HasField": lambda self, f: f == "status"})()
    span.name = name
    span.trace_id = trace_id
    span.span_id = span_id
    span.parent_span_id = parent_span_id
    span.kind = 1
    span.start_time_unix_nano = start_time
    span.end_time_unix_nano = end_time
    span.attributes = attrs or []
    span.events = events or []
    span.status = status
    return span


def test_normalize_healthy_span() -> None:
    normalizer = OtelNormalizer(source="test", latency_threshold_ms=1000)
    span = _make_span(
        name="ok-span",
        start_time=1700000000000000000,
        end_time=1700000000100000000,
    )

    class _SS:
        spans = [span]

    class _RS:
        resource = _make_resource()
        scope_spans = [_SS()]

    events = normalizer.normalize_traces([_RS()])
    assert any(e.trace_id == "01010101010101010101010101010101" for e in events)
    assert any(e.span_id == "0202020202020202" for e in events)


def test_normalize_error_span() -> None:
    normalizer = OtelNormalizer(source="test")
    span = _make_span(
        name="failing-span",
        status_code=2,
        status_message="timeout",
        start_time=1700000000000000000,
        end_time=1700000000500000000,
    )

    class _SS:
        spans = [span]

    class _RS:
        resource = _make_resource()
        scope_spans = [_SS()]

    events = normalizer.normalize_traces([_RS()])
    error_events = [e for e in events if e.metric == "span.error"]
    assert len(error_events) == 1
    assert error_events[0].severity == Severity.ERROR
    assert error_events[0].__otel_category__ == TimelineEventCategory.FAILURE


def test_normalize_high_latency_span() -> None:
    normalizer = OtelNormalizer(source="test", latency_threshold_ms=100)

    start = 1700000000000000000
    end = 1700000000200000000
    span = _make_span(
        name="slow-span",
        start_time=start,
        end_time=end,
    )

    class _SS:
        spans = [span]

    class _RS:
        resource = _make_resource()
        scope_spans = [_SS()]

    events = normalizer.normalize_traces([_RS()])
    latency_events = [e for e in events if e.metric == "span.latency"]
    assert len(latency_events) == 1
    assert latency_events[0].value == 200.0
    assert latency_events[0].__otel_category__ == TimelineEventCategory.METRIC_ANOMALY


# ------------------------------------------------------------------
# Log tests
# ------------------------------------------------------------------


def _make_log(
    body: str = "test log",
    severity_text: str = "INFO",
    severity_number: int = 9,
    trace_id: bytes = b"\x01" * 16,
    span_id: bytes = b"\x02" * 8,
    time_unix_nano: int = 1700000000000000000,
    attrs: list[Any] | None = None,
) -> Any:
    log_body = type("_Body", (), {"HasField": lambda self, f: f == "string_value"})()
    log_body.string_value = body

    log = type("_Log", (), {})()
    log.body = log_body
    log.severity_text = severity_text
    log.severity_number = severity_number
    log.trace_id = trace_id
    log.span_id = span_id
    log.time_unix_nano = time_unix_nano
    log.attributes = attrs or []
    return log


def test_normalize_info_log() -> None:
    normalizer = OtelNormalizer(source="test")
    log = _make_log(body="everything is fine")

    class _SL:
        log_records = [log]

    class _RL:
        resource = _make_resource()
        scope_logs = [_SL()]

    events = normalizer.normalize_logs([_RL()])
    assert len(events) == 1
    assert events[0].metric == "log.record"
    assert events[0].severity == Severity.INFO
    assert events[0].__otel_category__ == TimelineEventCategory.HEALTH_CHECK
    assert "everything is fine" in events[0].tags.get("log.body", "")


def test_normalize_error_log() -> None:
    normalizer = OtelNormalizer(source="test")
    log = _make_log(
        body="connection refused",
        severity_text="ERROR",
        severity_number=17,
    )

    class _SL:
        log_records = [log]

    class _RL:
        resource = _make_resource()
        scope_logs = [_SL()]

    events = normalizer.normalize_logs([_RL()])
    assert len(events) == 1
    assert events[0].severity == Severity.ERROR
    assert events[0].__otel_category__ == TimelineEventCategory.FAILURE


def test_normalize_critical_log() -> None:
    normalizer = OtelNormalizer(source="test")
    log = _make_log(
        body="kernel panic",
        severity_text="CRITICAL",
        severity_number=21,
    )

    class _SL:
        log_records = [log]

    class _RL:
        resource = _make_resource()
        scope_logs = [_SL()]

    events = normalizer.normalize_logs([_RL()])
    assert len(events) == 1
    assert events[0].severity == Severity.CRITICAL
    assert events[0].__otel_category__ == TimelineEventCategory.FAILURE


def test_log_trace_context_preserved() -> None:
    normalizer = OtelNormalizer(source="test")
    log = _make_log(
        body="traced log",
        severity_text="WARN",
        trace_id=b"\xaa" * 16,
        span_id=b"\xbb" * 8,
    )

    class _SL:
        log_records = [log]

    class _RL:
        resource = _make_resource()
        scope_logs = [_SL()]

    events = normalizer.normalize_logs([_RL()])
    assert len(events) == 1
    assert events[0].trace_id == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert events[0].span_id == "bbbbbbbbbbbbbbbb"
