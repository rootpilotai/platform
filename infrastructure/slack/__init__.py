"""Slack notification provider adapter."""

from infrastructure.slack.slack_notification_provider import (
    SlackNotificationProvider,
    SlackProviderConfig,
)

__all__ = [
    "SlackNotificationProvider",
    "SlackProviderConfig",
]
