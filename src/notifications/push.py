"""Push Notification Provider.

Provides Firebase Cloud Messaging (FCM) integration.
"""

import logging
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

from config.settings import get_settings
from src.database.orm import User, UserPreference
from src.database.connection import get_async_session
from src.reminders.dispatcher import ChannelProvider, NotificationResult, NotificationChannel
from sqlalchemy import select

logger = logging.getLogger(__name__)
settings = get_settings()


class FirebasePushProvider(ChannelProvider):
    """Firebase Cloud Messaging (FCM) provider.

    Sends push notifications to Android, iOS, and web clients.
    """

    def __init__(
        self,
        credentials_path: str = None,
        project_id: str = None,
    ):
        """Initialize Firebase provider.

        Args:
            credentials_path: Path to Firebase service account JSON.
            project_id: Firebase project ID.
        """
        self.credentials_path = credentials_path or getattr(settings, 'firebase_credentials_path', '')
        self.project_id = project_id or getattr(settings, 'firebase_project_id', '')
        self._initialized = False
        self._messaging = None

    def _initialize(self):
        """Initialize Firebase Admin SDK."""
        if self._initialized:
            return

        if not self.credentials_path:
            logger.warning("Firebase credentials not configured")
            return

        try:
            import firebase_admin
            from firebase_admin import credentials, messaging

            # Check if already initialized
            try:
                firebase_admin.get_app()
            except ValueError:
                # Initialize with credentials
                cred = credentials.Certificate(self.credentials_path)
                firebase_admin.initialize_app(cred)

            self._messaging = messaging
            self._initialized = True
            logger.info("Firebase initialized successfully")

        except ImportError:
            logger.warning("firebase-admin package not installed")
        except Exception as e:
            logger.error(f"Firebase initialization error: {e}")

    async def send(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send a push notification via FCM.

        Args:
            user_id: The user's ID.
            title: Notification title.
            body: Notification body.
            data: Optional additional data.

        Returns:
            NotificationResult.
        """
        self._initialize()

        if not self._messaging:
            return NotificationResult(
                channel=NotificationChannel.PUSH,
                success=False,
                error="Firebase not configured",
            )

        # Get user's FCM tokens
        tokens = await self._get_user_fcm_tokens(user_id)
        if not tokens:
            return NotificationResult(
                channel=NotificationChannel.PUSH,
                success=False,
                error="No FCM tokens found for user",
            )

        try:
            # Prepare notification
            notification = self._messaging.Notification(
                title=title,
                body=body,
            )

            # Prepare data payload (must be strings)
            data_payload = {}
            if data:
                for key, value in data.items():
                    if isinstance(value, str):
                        data_payload[key] = value
                    else:
                        data_payload[key] = json.dumps(value)

            # Add click action for web
            webpush_config = self._messaging.WebpushConfig(
                notification=self._messaging.WebpushNotification(
                    title=title,
                    body=body,
                    icon="/icon.png",
                ),
                fcm_options=self._messaging.WebpushFCMOptions(
                    link="/tasks",
                ),
            )

            # Send to multiple tokens
            if len(tokens) == 1:
                # Single device
                message = self._messaging.Message(
                    notification=notification,
                    data=data_payload,
                    token=tokens[0],
                    webpush=webpush_config,
                )
                response = self._messaging.send(message)
                message_id = response

            else:
                # Multiple devices
                message = self._messaging.MulticastMessage(
                    notification=notification,
                    data=data_payload,
                    tokens=tokens,
                    webpush=webpush_config,
                )
                response = self._messaging.send_multicast(message)

                # Check for failed tokens
                if response.failure_count > 0:
                    failed_tokens = []
                    for idx, result in enumerate(response.responses):
                        if not result.success:
                            failed_tokens.append(tokens[idx])

                    # Could remove failed tokens here
                    logger.warning(f"Failed to send to {response.failure_count} tokens")

                message_id = f"multicast_{response.success_count}_{datetime.utcnow().timestamp()}"

            logger.info(f"Push notification sent to {len(tokens)} devices for user {user_id}")

            return NotificationResult(
                channel=NotificationChannel.PUSH,
                success=True,
                message_id=message_id,
            )

        except Exception as e:
            logger.error(f"FCM error: {e}")
            return NotificationResult(
                channel=NotificationChannel.PUSH,
                success=False,
                error=str(e),
            )

    async def _get_user_fcm_tokens(self, user_id: uuid.UUID) -> List[str]:
        """Get user's FCM tokens from preferences.

        Args:
            user_id: The user's ID.

        Returns:
            List of FCM tokens.
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(UserPreference)
                .where(
                    UserPreference.user_id == user_id,
                    UserPreference.category == "push_tokens",
                )
            )
            prefs = result.scalars().all()

            tokens = []
            for pref in prefs:
                if pref.value:
                    token = pref.value.get("token") if isinstance(pref.value, dict) else pref.value
                    if token:
                        tokens.append(token)

            return tokens

    async def register_token(
        self,
        user_id: uuid.UUID,
        token: str,
        device_type: str = "web",
        device_name: str = None,
    ) -> bool:
        """Register an FCM token for a user.

        Args:
            user_id: The user's ID.
            token: The FCM token.
            device_type: Type of device (web, ios, android).
            device_name: Optional device name.

        Returns:
            True if registered successfully.
        """
        async with get_async_session() as session:
            # Check if token already exists
            result = await session.execute(
                select(UserPreference)
                .where(
                    UserPreference.user_id == user_id,
                    UserPreference.category == "push_tokens",
                    UserPreference.key == token[:20],  # Use prefix as key
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                existing.value = {
                    "token": token,
                    "device_type": device_type,
                    "device_name": device_name,
                    "registered_at": datetime.utcnow().isoformat(),
                }
            else:
                # Create new
                pref = UserPreference(
                    user_id=user_id,
                    category="push_tokens",
                    key=token[:20],
                    value={
                        "token": token,
                        "device_type": device_type,
                        "device_name": device_name,
                        "registered_at": datetime.utcnow().isoformat(),
                    },
                    source="explicit",
                )
                session.add(pref)

            await session.commit()
            return True

    async def unregister_token(
        self,
        user_id: uuid.UUID,
        token: str,
    ) -> bool:
        """Unregister an FCM token.

        Args:
            user_id: The user's ID.
            token: The FCM token to remove.

        Returns:
            True if removed successfully.
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(UserPreference)
                .where(
                    UserPreference.user_id == user_id,
                    UserPreference.category == "push_tokens",
                    UserPreference.key == token[:20],
                )
            )
            pref = result.scalar_one_or_none()

            if pref:
                await session.delete(pref)
                await session.commit()
                return True

            return False

    async def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send a notification to all subscribers of a topic.

        Args:
            topic: The topic name.
            title: Notification title.
            body: Notification body.
            data: Optional additional data.

        Returns:
            NotificationResult.
        """
        self._initialize()

        if not self._messaging:
            return NotificationResult(
                channel=NotificationChannel.PUSH,
                success=False,
                error="Firebase not configured",
            )

        try:
            notification = self._messaging.Notification(
                title=title,
                body=body,
            )

            data_payload = {}
            if data:
                for key, value in data.items():
                    data_payload[key] = str(value) if not isinstance(value, str) else value

            message = self._messaging.Message(
                notification=notification,
                data=data_payload,
                topic=topic,
            )

            response = self._messaging.send(message)

            logger.info(f"Push notification sent to topic {topic}")

            return NotificationResult(
                channel=NotificationChannel.PUSH,
                success=True,
                message_id=response,
            )

        except Exception as e:
            logger.error(f"FCM topic send error: {e}")
            return NotificationResult(
                channel=NotificationChannel.PUSH,
                success=False,
                error=str(e),
            )
