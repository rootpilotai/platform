from fastapi import Request

from app.config import CorrelationServiceSettings
from shared.domain.timeline.services import TimelineReconstructor


def get_settings(request: Request) -> CorrelationServiceSettings:
    return request.app.state.settings


def get_reconstructor(request: Request) -> TimelineReconstructor:
    return request.app.state.reconstructor
