"""SMS Notification Provider.

Provides Twilio SMS integration.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from config.settings import get_settings
from src.database.orm import User, UserPreference
from src.database.connection import get_async_session
from src.reminders.dispatcher import ChannelProvider, NotificationResult, NotificationChannel
from sqlalchemy import select

logger = logging.getLogger(__name__)
settings = get_settings()


class TwilioSMSProvider(ChannelProvider):
    """Twilio SMS provider.

    Uses the Twilio API for sending SMS messages.
    """

    def __init__(
        self,
        account_sid: str = None,
        auth_token: str = None,
        from_number: str = None,
    ):
        """Initialize Twilio provider.

        Args:
            account_sid: Twilio account SID.
            auth_token: Twilio auth token.
            from_number: Twilio phone number to send from.
        """
        self.account_sid = account_sid or getattr(settings, 'twilio_account_sid', '')
        self.auth_token = auth_token or getattr(settings, 'twilio_auth_token', '')
        self.from_number = from_number or getattr(settings, 'twilio_from_number', '')
        self._client = None

    @property
    def client(self):
        """Lazy-load Twilio client."""
        if self._client is None and self.account_sid and self.auth_token:
            try:
                from twilio.rest import Client
                self._client = Client(self.account_sid, self.auth_token)
            except ImportError:
                logger.warning("twilio package not installed")
        return self._client

    async def send(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send an SMS via Twilio.

        Args:
            user_id: The user's ID.
            title: Message title (prepended to body).
            body: Message body.
            data: Optional additional data.

        Returns:
            NotificationResult.
        """
        if not self.client:
            return NotificationResult(
                channel=NotificationChannel.SMS,
                success=False,
                error="Twilio not configured",
            )

        # Get user's phone number from preferences
        phone_number = await self._get_user_phone(user_id)
        if not phone_number:
            return NotificationResult(
                channel=NotificationChannel.SMS,
                success=False,
                error="User phone number not found",
            )

        try:
            # Combine title and body for SMS
            message_text = f"{title}\n\n{body}"

            # Truncate if too long (SMS limit is 1600 chars with Twilio)
            if len(message_text) > 1500:
                message_text = message_text[:1497] + "..."

            # Send SMS
            message = self.client.messages.create(
                body=message_text,
                from_=self.from_number,
                to=phone_number,
            )

            logger.info(f"SMS sent to {phone_number}: {message.sid}")

            return NotificationResult(
                channel=NotificationChannel.SMS,
                success=True,
                message_id=message.sid,
            )

        except Exception as e:
            logger.error(f"Twilio error sending to {phone_number}: {e}")
            return NotificationResult(
                channel=NotificationChannel.SMS,
                success=False,
                error=str(e),
            )

    async def _get_user_phone(self, user_id: uuid.UUID) -> Optional[str]:
        """Get user's phone number from preferences.

        Args:
            user_id: The user's ID.

        Returns:
            Phone number or None.
        """
        async with get_async_session() as session:
            # Check user preferences for phone number
            result = await session.execute(
                select(UserPreference)
                .where(
                    UserPreference.user_id == user_id,
                    UserPreference.category == "contact",
                    UserPreference.key == "phone_number",
                )
            )
            pref = result.scalar_one_or_none()

            if pref and pref.value:
                phone = pref.value.get("number") if isinstance(pref.value, dict) else pref.value
                return phone

            return None

    async def send_verification(
        self,
        phone_number: str,
        code: str,
    ) -> NotificationResult:
        """Send a verification code via SMS.

        Args:
            phone_number: The phone number to verify.
            code: The verification code.

        Returns:
            NotificationResult.
        """
        if not self.client:
            return NotificationResult(
                channel=NotificationChannel.SMS,
                success=False,
                error="Twilio not configured",
            )

        try:
            message_text = f"Your AI Task Manager verification code is: {code}\n\nThis code expires in 10 minutes."

            message = self.client.messages.create(
                body=message_text,
                from_=self.from_number,
                to=phone_number,
            )

            logger.info(f"Verification SMS sent to {phone_number}: {message.sid}")

            return NotificationResult(
                channel=NotificationChannel.SMS,
                success=True,
                message_id=message.sid,
            )

        except Exception as e:
            logger.error(f"Twilio verification error: {e}")
            return NotificationResult(
                channel=NotificationChannel.SMS,
                success=False,
                error=str(e),
            )
