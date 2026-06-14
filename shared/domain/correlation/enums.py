from enum import StrEnum


class CorrelationStrategyType(StrEnum):
    TIME_WINDOW = "time_window"
    TRACE_ID = "trace_id"
    SPAN_RELATION = "span_relation"
    REQUEST_ID = "request_id"
    DEPENDENCY = "dependency"
    ERROR_SIGNATURE = "error_signature"


class CorrelationSignal(StrEnum):
    TIME_PROXIMITY = "time_proximity"
    TRACE_MATCH = "trace_match"
    SPAN_PARENT_CHILD = "span_parent_child"
    SPAN_SIBLING = "span_sibling"
    REQUEST_MATCH = "request_match"
    DEPENDENCY_CHAIN = "dependency_chain"
    ERROR_PATTERN = "error_pattern"
