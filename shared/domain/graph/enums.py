from enum import StrEnum


class DependencyType(StrEnum):
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    EVENT = "event"
    GRPC = "grpc"
    DATABASE = "database"
    CUSTOM = "custom"


class ServiceStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"
