from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ulid import ULID

from sampark.db.database import Base


class EmailThread(Base):
    """Model representing an email thread."""

    __tablename__ = "email_threads"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=lambda: str(ULID()))
    thread_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    # Relationship with EmailMessage
    messages: Mapped[List["EmailMessage"]] = relationship(
        "EmailMessage", back_populates="thread", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"EmailThread(id={self.id}, thread_id={self.thread_id}, subject={self.subject})"


class EmailMessage(Base):
    """Model representing an individual email message within a thread."""

    __tablename__ = "email_messages"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=lambda: str(ULID()))
    message_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    thread_id: Mapped[str] = mapped_column(String(36), ForeignKey("email_threads.id"), index=True)
    sender: Mapped[str] = mapped_column(String(255))
    recipients: Mapped[str] = mapped_column(String(1024))  # Comma-separated list of recipients
    cc: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)  # Comma-separated list of CC recipients
    subject: Mapped[str] = mapped_column(String(255))
    body_text: Mapped[str] = mapped_column(Text)
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    in_reply_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    references: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated message IDs
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    is_sent_by_system: Mapped[bool] = mapped_column(default=False)  # Whether this message was sent by our system

    # Relationship with EmailThread
    thread: Mapped["EmailThread"] = relationship("EmailThread", back_populates="messages")

    def __repr__(self) -> str:
        return f"EmailMessage(id={self.id}, message_id={self.message_id}, subject={self.subject})"
