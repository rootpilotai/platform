from enum import StrEnum


class TimelineEventCategory(StrEnum):
    DEPLOYMENT = "deployment"
    FAILURE = "failure"
    RETRY = "retry"
    OUTAGE = "outage"
    METRIC_ANOMALY = "metric_anomaly"
    CONFIG_CHANGE = "config_change"
    SCALING_EVENT = "scaling_event"
    HEALTH_CHECK = "health_check"
    DEPENDENCY_FAILURE = "dependency_failure"
    RECOVERY = "recovery"


class TimelineEventSource(StrEnum):
    TELEMETRY = "telemetry"
    INCIDENT = "incident"
    DEPLOYMENT = "deployment"
    LOG = "log"
    MANUAL = "manual"
