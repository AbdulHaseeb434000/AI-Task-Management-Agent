"""Email Notification Providers.

Provides SMTP and SendGrid email providers.
"""

import logging
import smtplib
import ssl
import uuid
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any

from config.settings import get_settings
from src.database.orm import User
from src.database.connection import get_async_session
from src.reminders.dispatcher import ChannelProvider, NotificationResult, NotificationChannel

logger = logging.getLogger(__name__)
settings = get_settings()


class SMTPEmailProvider(ChannelProvider):
    """SMTP-based email provider.

    Supports standard SMTP servers like Gmail, Outlook, custom SMTP.
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        use_tls: bool = True,
        from_email: str = None,
        from_name: str = "AI Task Manager",
    ):
        """Initialize SMTP provider.

        Args:
            host: SMTP server host.
            port: SMTP server port.
            username: SMTP username.
            password: SMTP password.
            use_tls: Use TLS encryption.
            from_email: Sender email address.
            from_name: Sender display name.
        """
        self.host = host or getattr(settings, 'smtp_host', 'localhost')
        self.port = port or getattr(settings, 'smtp_port', 587)
        self.username = username or getattr(settings, 'smtp_username', '')
        self.password = password or getattr(settings, 'smtp_password', '')
        self.use_tls = use_tls
        self.from_email = from_email or getattr(settings, 'smtp_from_email', 'noreply@example.com')
        self.from_name = from_name

    async def send(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send an email via SMTP.

        Args:
            user_id: The user's ID.
            title: Email subject.
            body: Email body.
            data: Optional additional data (e.g., html_body, attachments).

        Returns:
            NotificationResult.
        """
        # Get user email
        async with get_async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                return NotificationResult(
                    channel=NotificationChannel.EMAIL,
                    success=False,
                    error="User not found",
                )
            to_email = user.email
            to_name = user.name

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = title
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = f"{to_name} <{to_email}>"

            # Plain text body
            text_part = MIMEText(body, "plain")
            msg.attach(text_part)

            # HTML body if provided
            html_body = data.get("html_body") if data else None
            if html_body:
                html_part = MIMEText(html_body, "html")
                msg.attach(html_part)
            else:
                # Generate simple HTML from plain text
                simple_html = f"""
                <html>
                <body>
                    <h2>{title}</h2>
                    <p>{body.replace(chr(10), '<br>')}</p>
                </body>
                </html>
                """
                html_part = MIMEText(simple_html, "html")
                msg.attach(html_part)

            # Send email
            context = ssl.create_default_context()

            if self.use_tls:
                with smtplib.SMTP(self.host, self.port) as server:
                    server.starttls(context=context)
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.sendmail(self.from_email, to_email, msg.as_string())
            else:
                with smtplib.SMTP_SSL(self.host, self.port, context=context) as server:
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.sendmail(self.from_email, to_email, msg.as_string())

            message_id = f"smtp_{datetime.utcnow().timestamp()}"
            logger.info(f"Email sent to {to_email}: {title}")

            return NotificationResult(
                channel=NotificationChannel.EMAIL,
                success=True,
                message_id=message_id,
            )

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email to {to_email}: {e}")
            return NotificationResult(
                channel=NotificationChannel.EMAIL,
                success=False,
                error=str(e),
            )
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {e}")
            return NotificationResult(
                channel=NotificationChannel.EMAIL,
                success=False,
                error=str(e),
            )


class SendGridEmailProvider(ChannelProvider):
    """SendGrid email provider.

    Uses the SendGrid API for sending emails.
    """

    def __init__(
        self,
        api_key: str = None,
        from_email: str = None,
        from_name: str = "AI Task Manager",
    ):
        """Initialize SendGrid provider.

        Args:
            api_key: SendGrid API key.
            from_email: Sender email address.
            from_name: Sender display name.
        """
        self.api_key = api_key or getattr(settings, 'sendgrid_api_key', '')
        self.from_email = from_email or getattr(settings, 'sendgrid_from_email', 'noreply@example.com')
        self.from_name = from_name
        self._client = None

    @property
    def client(self):
        """Lazy-load SendGrid client."""
        if self._client is None and self.api_key:
            try:
                from sendgrid import SendGridAPIClient
                self._client = SendGridAPIClient(self.api_key)
            except ImportError:
                logger.warning("sendgrid package not installed")
        return self._client

    async def send(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send an email via SendGrid.

        Args:
            user_id: The user's ID.
            title: Email subject.
            body: Email body.
            data: Optional additional data.

        Returns:
            NotificationResult.
        """
        if not self.client:
            return NotificationResult(
                channel=NotificationChannel.EMAIL,
                success=False,
                error="SendGrid not configured",
            )

        # Get user email
        async with get_async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                return NotificationResult(
                    channel=NotificationChannel.EMAIL,
                    success=False,
                    error="User not found",
                )
            to_email = user.email

        try:
            from sendgrid.helpers.mail import Mail, Email, To, Content

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=title,
            )

            # Add plain text content
            message.add_content(Content("text/plain", body))

            # Add HTML content if provided
            html_body = data.get("html_body") if data else None
            if html_body:
                message.add_content(Content("text/html", html_body))

            # Send
            response = self.client.send(message)

            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"SendGrid email sent to {to_email}: {title}")
                return NotificationResult(
                    channel=NotificationChannel.EMAIL,
                    success=True,
                    message_id=response.headers.get("X-Message-Id", str(datetime.utcnow().timestamp())),
                )
            else:
                return NotificationResult(
                    channel=NotificationChannel.EMAIL,
                    success=False,
                    error=f"SendGrid returned status {response.status_code}",
                )

        except Exception as e:
            logger.error(f"SendGrid error: {e}")
            return NotificationResult(
                channel=NotificationChannel.EMAIL,
                success=False,
                error=str(e),
            )
