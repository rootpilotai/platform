from pydantic import Field

from shared.config import BaseAppSettings


class NotificationServiceSettings(BaseAppSettings):
    service_name: str = "notification-service"
    host: str = Field(default="0.0.0.0", description="Bind address for the HTTP server.")
    port: int = Field(default=8003, ge=1024, le=65535, description="Bind port for the HTTP server.")
    event_bus_url: str = Field(
        default="amqp://rootpilot:rootpilot@localhost:5672/",
        description="Event bus connection URL.",
    )

    slack_enabled: bool = Field(default=False, description="Enable Slack notifications.")
    slack_bot_token: str = Field(default="", description="Slack bot user OAuth token.")
    slack_default_channel: str = Field(default="#incidents", description="Default Slack channel.")

    discord_enabled: bool = Field(default=False, description="Enable Discord notifications.")
    discord_webhook_url: str = Field(default="", description="Discord webhook URL.")
    discord_username: str = Field(default="RootPilot", description="Bot username for Discord messages.")
