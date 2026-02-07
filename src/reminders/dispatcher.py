"""Notification Dispatcher - Sends notifications across channels.

Supports:
- Push notifications
- Email
- SMS (placeholder)
- Slack/Discord (placeholder)
- In-app notifications
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Protocol
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import User, UserPreference
from src.database.connection import get_async_session
from src.reminders.engine import ReminderEvent


class NotificationChannel(Enum):
    """Available notification channels."""
    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    DISCORD = "discord"
    IN_APP = "in_app"


@dataclass
class NotificationResult:
    """Result of a notification send attempt."""
    channel: NotificationChannel
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class ChannelProvider(ABC):
    """Abstract base for notification channel providers."""

    @abstractmethod
    async def send(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send a notification.

        Args:
            user_id: The user's ID.
            title: Notification title.
            body: Notification body.
            data: Optional additional data.

        Returns:
            NotificationResult.
        """
        pass


class PushProvider(ChannelProvider):
    """Push notification provider (placeholder)."""

    async def send(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send a push notification.

        In production, this would integrate with Firebase, APNs, etc.
        """
        # Placeholder - would call push notification service
        print(f"[PUSH] To {user_id}: {title} - {body}")
        return NotificationResult(
            channel=NotificationChannel.PUSH,
            success=True,
            message_id=f"push_{datetime.utcnow().timestamp()}",
        )


class EmailProvider(ChannelProvider):
    """Email notification provider (placeholder)."""

    async def send(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send an email notification.

        In production, this would integrate with SendGrid, SES, etc.
        """
        # Get user email
        async with get_async_session() as session:
            user = await session.get(User, user_id)
            email = user.email if user else None

        if not email:
            return NotificationResult(
                channel=NotificationChannel.EMAIL,
                success=False,
                error="User email not found",
            )

        # Placeholder - would call email service
        print(f"[EMAIL] To {email}: {title} - {body}")
        return NotificationResult(
            channel=NotificationChannel.EMAIL,
            success=True,
            message_id=f"email_{datetime.utcnow().timestamp()}",
        )


class InAppProvider(ChannelProvider):
    """In-app notification provider."""

    def __init__(self):
        """Initialize with in-memory store (for demo)."""
        self._notifications: Dict[uuid.UUID, List[Dict[str, Any]]] = {}

    async def send(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Store an in-app notification."""
        if user_id not in self._notifications:
            self._notifications[user_id] = []

        notification = {
            "id": str(uuid.uuid4()),
            "title": title,
            "body": body,
            "data": data or {},
            "created_at": datetime.utcnow().isoformat(),
            "read": False,
        }
        self._notifications[user_id].append(notification)

        # Keep only last 100 notifications
        if len(self._notifications[user_id]) > 100:
            self._notifications[user_id] = self._notifications[user_id][-100:]

        return NotificationResult(
            channel=NotificationChannel.IN_APP,
            success=True,
            message_id=notification["id"],
        )

    async def get_notifications(
        self,
        user_id: uuid.UUID,
        unread_only: bool = False,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get notifications for a user.

        Args:
            user_id: The user's ID.
            unread_only: Only return unread notifications.
            limit: Maximum notifications to return.

        Returns:
            List of notification dicts.
        """
        notifications = self._notifications.get(user_id, [])

        if unread_only:
            notifications = [n for n in notifications if not n["read"]]

        return notifications[-limit:]

    async def mark_read(
        self,
        user_id: uuid.UUID,
        notification_id: str,
    ) -> bool:
        """Mark a notification as read.

        Args:
            user_id: The user's ID.
            notification_id: The notification ID.

        Returns:
            True if marked as read.
        """
        notifications = self._notifications.get(user_id, [])
        for n in notifications:
            if n["id"] == notification_id:
                n["read"] = True
                return True
        return False


class NotificationDispatcher:
    """Dispatches notifications across configured channels.

    Manages:
    - Channel providers
    - User preferences
    - Fallback logic
    """

    def __init__(self):
        """Initialize with default providers."""
        self._providers: Dict[NotificationChannel, ChannelProvider] = {
            NotificationChannel.PUSH: PushProvider(),
            NotificationChannel.EMAIL: EmailProvider(),
            NotificationChannel.IN_APP: InAppProvider(),
        }

    def register_provider(
        self,
        channel: NotificationChannel,
        provider: ChannelProvider,
    ) -> None:
        """Register a channel provider.

        Args:
            channel: The channel.
            provider: The provider implementation.
        """
        self._providers[channel] = provider

    async def dispatch(
        self,
        event: ReminderEvent,
    ) -> List[NotificationResult]:
        """Dispatch a reminder event to all configured channels.

        Args:
            event: The reminder event.

        Returns:
            List of NotificationResults.
        """
        results = []

        # Get user's preferred channels
        channels = await self._get_user_channels(event.user_id, event.channels)

        # Build notification content
        title = "Task Reminder"
        body = event.message

        data = {
            "reminder_id": str(event.reminder_id),
            "type": event.reminder_type.value,
        }
        if event.task_id:
            data["task_id"] = str(event.task_id)

        # Send to each channel
        for channel_name in channels:
            try:
                channel = NotificationChannel(channel_name)
            except ValueError:
                continue

            provider = self._providers.get(channel)
            if not provider:
                results.append(NotificationResult(
                    channel=channel,
                    success=False,
                    error=f"No provider for channel: {channel_name}",
                ))
                continue

            result = await provider.send(
                user_id=event.user_id,
                title=title,
                body=body,
                data=data,
            )
            results.append(result)

        # Always add in-app notification as fallback
        if NotificationChannel.IN_APP.value not in channels:
            in_app = self._providers.get(NotificationChannel.IN_APP)
            if in_app:
                result = await in_app.send(
                    user_id=event.user_id,
                    title=title,
                    body=body,
                    data=data,
                )
                results.append(result)

        return results

    async def _get_user_channels(
        self,
        user_id: uuid.UUID,
        default_channels: List[str],
    ) -> List[str]:
        """Get user's preferred notification channels.

        Args:
            user_id: The user's ID.
            default_channels: Default channels if no preference.

        Returns:
            List of channel names.
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(UserPreference)
                .where(
                    UserPreference.user_id == user_id,
                    UserPreference.category == "notifications",
                    UserPreference.key == "channels",
                )
            )
            pref = result.scalar_one_or_none()

            if pref and pref.value:
                return pref.value if isinstance(pref.value, list) else [pref.value]

        return default_channels

    async def send_notification(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str,
        channels: Optional[List[str]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> List[NotificationResult]:
        """Send a direct notification (not from reminder).

        Args:
            user_id: The user's ID.
            title: Notification title.
            body: Notification body.
            channels: Channels to use (or user's default).
            data: Optional additional data.

        Returns:
            List of NotificationResults.
        """
        results = []

        # Get channels
        actual_channels = await self._get_user_channels(
            user_id,
            channels or ["push", "in_app"],
        )

        for channel_name in actual_channels:
            try:
                channel = NotificationChannel(channel_name)
            except ValueError:
                continue

            provider = self._providers.get(channel)
            if provider:
                result = await provider.send(
                    user_id=user_id,
                    title=title,
                    body=body,
                    data=data,
                )
                results.append(result)

        return results

    async def get_in_app_notifications(
        self,
        user_id: uuid.UUID,
        unread_only: bool = False,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get in-app notifications for a user.

        Args:
            user_id: The user's ID.
            unread_only: Only return unread.
            limit: Maximum to return.

        Returns:
            List of notifications.
        """
        in_app = self._providers.get(NotificationChannel.IN_APP)
        if isinstance(in_app, InAppProvider):
            return await in_app.get_notifications(user_id, unread_only, limit)
        return []

    async def mark_notification_read(
        self,
        user_id: uuid.UUID,
        notification_id: str,
    ) -> bool:
        """Mark an in-app notification as read.

        Args:
            user_id: The user's ID.
            notification_id: The notification ID.

        Returns:
            True if marked.
        """
        in_app = self._providers.get(NotificationChannel.IN_APP)
        if isinstance(in_app, InAppProvider):
            return await in_app.mark_read(user_id, notification_id)
        return False


# Global dispatcher
_dispatcher: Optional[NotificationDispatcher] = None


def get_dispatcher() -> NotificationDispatcher:
    """Get the global notification dispatcher."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher
