"""
Factory for creating EmailMessage models for testing.
"""

import random
import string
from datetime import datetime
from typing import Any, List, Optional, Union

import ulid

from sampark.db.models import EmailMessage


class EmailMessageFactory:
    """Factory for creating EmailMessage instances for testing."""

    @staticmethod
    def create(
        id: Optional[str] = None,
        message_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        sender: Optional[str] = None,
        recipients: Optional[Union[str, List[str]]] = None,
        cc: Optional[Union[str, List[str]]] = None,
        subject: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
        received_at: Optional[datetime] = None,
        is_sent_by_system: Optional[bool] = None,
        **kwargs: Any,
    ) -> EmailMessage:
        """
        Create an EmailMessage instance with sensible defaults.

        Args:
            id: The ID of the message (defaults to ULID)
            message_id: The message ID (defaults to random string)
            thread_id: The thread ID (required)
            sender: The sender email (defaults to random email)
            recipients: The recipients (defaults to random email)
            cc: The CC recipients (defaults to None)
            subject: The subject (defaults to random subject)
            body_text: The text body (defaults to random text)
            body_html: The HTML body (defaults to None)
            in_reply_to: The message ID this is in reply to (defaults to None)
            references: The message references (defaults to None)
            received_at: The received timestamp (defaults to now)
            is_sent_by_system: Whether the message was sent by the system (defaults to False)
            **kwargs: Additional attributes to set

        Returns:
            An EmailMessage instance
        """
        now = datetime.now()

        # Generate random values if not provided
        if sender is None:
            sender = f"sender{random.randint(1, 100)}@example.com"

        if recipients is None:
            recipients = f"recipient{random.randint(1, 100)}@example.com"
        elif isinstance(recipients, list):
            recipients = ", ".join(recipients)

        if cc is not None and isinstance(cc, list):
            cc = ", ".join(cc)

        if subject is None:
            subject = f"Test Subject {random.randint(1000, 9999)}"

        if body_text is None:
            body_text = f"This is a test email body {random.randint(1000, 9999)}"

        if message_id is None:
            rand_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
            message_id = f"msg-{rand_str}@example.com"

        # Create the message
        message = EmailMessage(
            id=id or str(ulid.ULID()),
            message_id=message_id,
            thread_id=thread_id,  # This is required
            sender=sender,
            recipients=recipients,
            cc=cc,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            in_reply_to=in_reply_to,
            references=references,
            received_at=received_at or now,
            is_sent_by_system=is_sent_by_system if is_sent_by_system is not None else False,
            **kwargs,
        )

        return message

    @classmethod
    def create_batch(cls, count: int, **kwargs: Any) -> List[EmailMessage]:
        """Create multiple EmailMessage instances."""
        return [cls.create(**kwargs) for _ in range(count)]
