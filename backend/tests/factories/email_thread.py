"""
Factory for creating EmailThread models for testing.
"""
import random
from datetime import datetime
from typing import Any, List, Optional

import ulid

from sampark.db.models import EmailThread


class EmailThreadFactory:
    """Factory for creating EmailThread instances for testing."""

    @staticmethod
    def create(
        id: Optional[str] = None,
        thread_id: Optional[str] = None,
        subject: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        **kwargs: Any,
    ) -> EmailThread:
        """
        Create an EmailThread instance with sensible defaults.

        Args:
            id: The ID of the thread (defaults to ULID)
            thread_id: The thread ID (defaults to random string)
            subject: The subject of the thread (defaults to random subject)
            created_at: The creation timestamp (defaults to now)
            updated_at: The update timestamp (defaults to now)
            **kwargs: Additional attributes to set

        Returns:
            An EmailThread instance
        """
        now = datetime.now()

        # Generate a random subject if not provided
        if subject is None:
            subject = f"Test Subject {random.randint(1000, 9999)}"

        # Generate a random thread_id if not provided
        if thread_id is None:
            thread_id = f"{subject}_{random.randint(1000, 9999)}"

        # Create the thread
        thread = EmailThread(
            id=id or str(ulid.ULID()),
            thread_id=thread_id,
            subject=subject,
            created_at=created_at or now,
            updated_at=updated_at or now,
            **kwargs,
        )

        return thread

    @classmethod
    def create_batch(cls, count: int, **kwargs: Any) -> List[EmailThread]:
        """Create multiple EmailThread instances."""
        return [cls.create(**kwargs) for _ in range(count)]
