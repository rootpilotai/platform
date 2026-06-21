from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.contracts.events.enums import Severity
from shared.contracts.events.telemetry import TelemetryEvent
from shared.domain.timeline.enums import TimelineEventCategory

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

_ANOMALY_METRIC_PATTERNS: dict[str, TimelineEventCategory] = {
    "error": TimelineEventCategory.FAILURE,
    "failure": TimelineEventCategory.FAILURE,
    "exception": TimelineEventCategory.FAILURE,
    "panic": TimelineEventCategory.FAILURE,
    "latency": TimelineEventCategory.METRIC_ANOMALY,
    "timeout": TimelineEventCategory.DEPENDENCY_FAILURE,
    "degraded": TimelineEventCategory.METRIC_ANOMALY,
}

_DEFAULT_SEVERITY_MAP: dict[str, Severity] = {
    "error": Severity.ERROR,
    "critical": Severity.CRITICAL,
    "warn": Severity.WARNING,
    "warning": Severity.WARNING,
    "info": Severity.INFO,
    "debug": Severity.DEBUG,
}


def _hex_id(raw: bytes) -> str:
    return raw.hex() if raw else ""


def _ts_to_dt(nanos: int) -> datetime:
    return datetime.fromtimestamp(nanos / 1_000_000_000, tz=UTC)


def _severity_from_otel(severity_text: str, severity_number: int) -> Severity:
    if severity_text:
        lowered = severity_text.lower()
        if lowered in _DEFAULT_SEVERITY_MAP:
            return _DEFAULT_SEVERITY_MAP[lowered]
    if severity_number >= 17:
        return Severity.CRITICAL
    if severity_number >= 13:
        return Severity.ERROR
    if severity_number >= 9:
        return Severity.WARNING
    if severity_number >= 5:
        return Severity.INFO
    return Severity.DEBUG


def _classify_metric(name: str, value: float) -> tuple[TimelineEventCategory, Severity]:
    lowered = name.lower()
    for pattern, category in _ANOMALY_METRIC_PATTERNS.items():
        if pattern in lowered:
            return category, Severity.ERROR
    if value < 0:
        return TimelineEventCategory.METRIC_ANOMALY, Severity.WARNING
    return TimelineEventCategory.HEALTH_CHECK, Severity.INFO


def _attrs_to_tags(attributes: Any) -> dict[str, str]:
    tags: dict[str, str] = {}
    if attributes is None:
        return tags
    try:
        for kv in attributes:
            key = kv.key
            value = kv.value
            if value.HasField("string_value"):
                tags[key] = value.string_value
            elif value.HasField("int_value"):
                tags[key] = str(value.int_value)
            elif value.HasField("double_value"):
                tags[key] = str(value.double_value)
            elif value.HasField("bool_value"):
                tags[key] = str(value.bool_value).lower()
    except Exception:
        pass
    return tags


_SERVICE_NAME_ALIASES: dict[str, str] = {
    "frontend-web": "frontend",
}


class OtelNormalizer:
    def __init__(
        self,
        source: str = "otel-adapter",
        latency_threshold_ms: float = 1000.0,
    ) -> None:
        self._source = source
        self._latency_threshold_ms = latency_threshold_ms

    def _resolve_source(self, resource_tags: dict[str, str]) -> str:
        raw = resource_tags.get("service.name", self._source)
        return _SERVICE_NAME_ALIASES.get(raw, raw)

    def normalize_metrics(self, resource_metrics: Sequence[Any]) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []
        for rm in resource_metrics:
            resource_tags = _attrs_to_tags(getattr(rm.resource, "attributes", None))
            for sm in rm.scope_metrics:
                for metric in sm.metrics:
                    events.extend(self._normalize_metric(metric, resource_tags))
        return events

    def normalize_traces(self, resource_spans: Sequence[Any]) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []
        for rs in resource_spans:
            resource_tags = _attrs_to_tags(getattr(rs.resource, "attributes", None))
            for ss in rs.scope_spans:
                for span in ss.spans:
                    events.extend(self._normalize_span(span, resource_tags))
        return events

    def normalize_logs(self, resource_logs: Sequence[Any]) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []
        for rl in resource_logs:
            resource_tags = _attrs_to_tags(getattr(rl.resource, "attributes", None))
            for sl in rl.scope_logs:
                for log in sl.log_records:
                    events.extend(self._normalize_log(log, resource_tags))
        return events

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_metric(
        self,
        metric: Any,
        resource_tags: dict[str, str],
    ) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []
        name = metric.name
        unit = metric.unit or None

        points = self._extract_datapoints(metric)
        for value, attrs, ts in points:
            tags = {**resource_tags, **_attrs_to_tags(attrs)}
            category, severity = _classify_metric(name, value)
            event = TelemetryEvent(
                metric=name,
                value=value,
                unit=unit,
                tags=tags,
                source=self._resolve_source(tags),
                timestamp=ts,
                severity=severity,
            )
            event.__otel_category__ = category
            events.append(event)
        return events

    def _normalize_span(
        self,
        span: Any,
        resource_tags: dict[str, str],
    ) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []
        span_id = _hex_id(getattr(span, "span_id", b""))
        trace_id = _hex_id(getattr(span, "trace_id", b""))
        parent_span_id = _hex_id(getattr(span, "parent_span_id", b""))
        tags = {
            **resource_tags,
            "span.name": span.name or "",
            "span.kind": str(span.kind),
            **_attrs_to_tags(getattr(span, "attributes", None)),
        }

        end_time = _ts_to_dt(span.end_time_unix_nano)
        duration_ms = (span.end_time_unix_nano - span.start_time_unix_nano) / 1_000_000

        status_code = getattr(span.status, "code", 0) if span.HasField("status") else 0
        is_error = status_code == 2

        http_code_str = tags.get("http.status_code", tags.get("http.response.status_code", ""))
        try:
            http_code = int(http_code_str)
            if http_code >= 500:
                is_error = True
        except (ValueError, TypeError):
            pass

        if is_error:
            status_desc = getattr(span.status, "message", "") if span.HasField("status") else ""
            tags["status.message"] = status_desc
            event = TelemetryEvent(
                metric="span.error",
                value=1.0,
                unit=None,
                tags=tags,
                source=self._resolve_source(tags),
                timestamp=end_time,
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                severity=Severity.ERROR,
            )
            event.__otel_category__ = TimelineEventCategory.FAILURE
            events.append(event)

        if duration_ms > self._latency_threshold_ms:
            event = TelemetryEvent(
                metric="span.latency",
                value=duration_ms,
                unit="ms",
                tags=tags,
                source=self._resolve_source(tags),
                timestamp=end_time,
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                severity=Severity.WARNING,
            )
            event.__otel_category__ = TimelineEventCategory.METRIC_ANOMALY
            events.append(event)

        span_event = TelemetryEvent(
            metric=f"span.{span.name or 'unknown'}",
            value=duration_ms,
            unit="ms",
            tags=tags,
            source=self._resolve_source(tags),
            timestamp=end_time,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            severity=Severity.INFO,
        )
        span_event.__otel_category__ = TimelineEventCategory.HEALTH_CHECK
        events.append(span_event)

        for span_event_proto in span.events:
            se_tags = {
                **tags,
                "span_event.name": span_event_proto.name or "",
                **_attrs_to_tags(getattr(span_event_proto, "attributes", None)),
            }
            se_time = _ts_to_dt(span_event_proto.time_unix_nano)
            se = TelemetryEvent(
                metric=f"span_event.{span_event_proto.name or 'unknown'}",
                value=1.0,
                tags=se_tags,
                source=self._resolve_source(se_tags),
                timestamp=se_time,
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                severity=Severity.INFO,
            )
            se.__otel_category__ = TimelineEventCategory.HEALTH_CHECK
            events.append(se)

        return events

    def _normalize_log(
        self,
        log: Any,
        resource_tags: dict[str, str],
    ) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []
        trace_id = _hex_id(getattr(log, "trace_id", b""))
        span_id = _hex_id(getattr(log, "span_id", b""))

        severity = _severity_from_otel(
            getattr(log, "severity_text", ""),
            getattr(log, "severity_number", 0),
        )
        body_str = self._log_body(log)
        tags = {
            **resource_tags,
            "log.body": body_str,
            **_attrs_to_tags(getattr(log, "attributes", None)),
        }

        ts = _ts_to_dt(log.time_unix_nano)

        event = TelemetryEvent(
            metric="log.record",
            value=1.0,
            tags=tags,
            source=self._resolve_source(tags),
            timestamp=ts,
            trace_id=trace_id,
            span_id=span_id,
            severity=severity,
        )

        if severity in (Severity.ERROR, Severity.CRITICAL):
            event.__otel_category__ = TimelineEventCategory.FAILURE
        else:
            event.__otel_category__ = TimelineEventCategory.HEALTH_CHECK

        events.append(event)
        return events

    # ------------------------------------------------------------------
    # Metric data point extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_datapoints(
        metric: Any,
    ) -> list[tuple[float, Any, datetime]]:
        points: list[tuple[float, Any, datetime]] = []

        if metric.HasField("gauge"):
            for dp in metric.gauge.data_points:
                points.append(
                    (
                        dp.as_double if dp.HasField("as_double") else float(dp.as_int),
                        dp.attributes,
                        _ts_to_dp_time(dp),
                    )
                )

        elif metric.HasField("sum"):
            for dp in metric.sum.data_points:
                points.append(
                    (
                        dp.as_double if dp.HasField("as_double") else float(dp.as_int),
                        dp.attributes,
                        _ts_to_dp_time(dp),
                    )
                )

        elif metric.HasField("histogram"):
            for dp in metric.histogram.data_points:
                count_val = float(dp.count)
                points.append((count_val, dp.attributes, _ts_to_dp_time(dp)))
                if dp.HasField("sum") and dp.count > 0:
                    avg = dp.sum / dp.count
                    points.append((avg, dp.attributes, _ts_to_dp_time(dp)))

        elif metric.HasField("summary"):
            for dp in metric.summary.data_points:
                for q in dp.quantile_values:
                    points.append(
                        (
                            q.value,
                            dp.attributes,
                            _ts_to_dp_time(dp),
                        )
                    )

        return points

    @staticmethod
    def _log_body(log: Any) -> str:
        body = getattr(log, "body", None)
        if body is None:
            return ""
        try:
            if body.HasField("string_value"):
                return body.string_value
        except Exception:
            pass
        return str(body)


def _ts_to_dp_time(dp: Any) -> datetime:
    nanos = getattr(dp, "time_unix_nano", 0) or 0
    return _ts_to_dt(nanos)
