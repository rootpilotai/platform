from fastapi import Request

from app.config import OtelAdapterSettings


def get_settings(request: Request) -> OtelAdapterSettings:
    return request.app.state.settings
