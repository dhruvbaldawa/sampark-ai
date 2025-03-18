import logging
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from sampark.adapters.email.client import EmailClient
from sampark.db.database import get_db_session
from sampark.db.models import EmailThread, EmailMessage

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for handling email-related operations.
    """

    def __init__(self, email_client: EmailClient) -> None:
        """
        Initialize the email service.

        Args:
            email_client: The email client to use for sending and receiving emails
        """
        self.email_client = email_client

    async def _get_thread_by_thread_id(self, db_session: AsyncSession, thread_id: str) -> Optional[EmailThread]:
        """Get a thread by its thread ID."""
        try:
            query = select(EmailThread).where(EmailThread.thread_id == thread_id)
            result = await db_session.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error fetching thread by thread_id: {str(e)}")
            return None

    async def _get_message_by_message_id(self, db_session: AsyncSession, message_id: str) -> Optional[EmailMessage]:
        """Get a message by its message ID."""
        try:
            query = select(EmailMessage).where(EmailMessage.message_id == message_id)
            result = await db_session.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error fetching message by message_id: {str(e)}")
            return None

    async def _create_email_thread(self, db_session: AsyncSession, thread_id: str, subject: str) -> Optional[EmailThread]:
        """Create a new email thread."""
        try:
            thread = EmailThread(
                thread_id=thread_id,
                subject=subject,
            )
            db_session.add(thread)
            await db_session.flush()
            return thread
        except SQLAlchemyError as e:
            logger.error(f"Error creating email thread: {str(e)}")
            return None

    async def _save_email_message(self, db_session: AsyncSession, message_data: Dict[str, Any], thread_id: str, is_sent_by_system: bool = False) -> Optional[EmailMessage]:
        """Create and save an email message."""
        try:
            message = EmailMessage(
                thread_id=thread_id,
                message_id=message_data["message_id"],
                sender=message_data["sender"],
                recipients=', '.join(message_data["recipients"]) if isinstance(message_data["recipients"], list) else message_data["recipients"],
                cc=', '.join(message_data.get("cc", [])) if isinstance(message_data.get("cc", []), list) else message_data.get("cc", ""),
                subject=message_data["subject"],
                body_text=message_data["body_text"],
                body_html=message_data.get("body_html", ""),
                in_reply_to=message_data.get("in_reply_to"),
                references=message_data.get("references"),
                is_sent_by_system=is_sent_by_system,
            )
            db_session.add(message)
            await db_session.flush()
            return message
        except SQLAlchemyError as e:
            logger.error(f"Error saving email message: {str(e)}")
            return None

    async def process_new_email(self, email_data: Dict[str, Any], db_session: Optional[AsyncSession] = None) -> Optional[EmailMessage]:
        """
        Process a new email.

        Args:
            email_data: The email data from the email client
            db_session: Optional database session for dependency injection in tests

        Returns:
            The created email message, or None if there was an error
        """
        session_context = None
        try:
            # Allow session injection for testing
            if db_session is None:
                session_context = get_db_session()
                db_session = await session_context.__aenter__()

            # Check if thread exists
            thread = await self._get_thread_by_thread_id(db_session, email_data["thread_id"])

            # If thread doesn't exist, create it
            if not thread:
                thread = await self._create_email_thread(
                    db_session,
                    email_data["thread_id"],
                    email_data["subject"]
                )
                if not thread:
                    raise ValueError("Failed to create thread")

            # Create email message
            message = await self._save_email_message(
                db_session,
                email_data,
                thread.id
            )

            if not message:
                raise ValueError("Failed to save message")

            # Only commit if we created the session
            if session_context:
                await db_session.commit()
            return message
        except Exception as e:
            logger.error(f"Error processing new email: {str(e)}")
            # Only rollback if we created the session
            if session_context:
                await db_session.rollback()
            return None
        finally:
            # Only close if we created the session
            if session_context:
                await session_context.__aexit__(None, None, None)

    async def reply_to_email(
        self,
        message_id: str,
        body_text: str,
        body_html: Optional[str] = None,
        db_session: Optional[AsyncSession] = None
    ) -> Tuple[bool, Optional[EmailMessage]]:
        """
        Reply to an email.

        Args:
            message_id: The ID of the message to reply to
            body_text: The plain text body of the reply
            body_html: The HTML body of the reply (optional)
            db_session: Optional database session for dependency injection in tests

        Returns:
            A tuple of (success, message) where success is True if the reply was sent,
            and message is the created email message (or None if there was an error)
        """
        session_context = None
        try:
            # Allow session injection for testing
            if db_session is None:
                session_context = get_db_session()
                db_session = await session_context.__aenter__()

            # Get the original message
            original_message = await self._get_message_by_message_id(db_session, message_id)
            if not original_message:
                logger.error(f"Could not find message with ID {message_id}")
                return False, None

            # Get the thread
            thread = await self._get_thread_by_thread_id(db_session, original_message.thread_id)
            if not thread:
                logger.error(f"Could not find thread for message {message_id}")
                return False, None

            # Determine recipients and prepare email for sending
            recipients, subject, email_refs = self._prepare_reply_data(original_message)

            # Send the email
            success, reply_message_id = await self.email_client.send_email(
                recipients=recipients,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                in_reply_to=original_message.message_id,
                references=email_refs,
            )

            if not success:
                logger.error("Failed to send reply email")
                return False, None

            # Create message data for saving
            message_data = {
                "message_id": reply_message_id,
                "sender": self.email_client.username,
                "recipients": recipients,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html or "",
                "in_reply_to": original_message.message_id,
                "references": email_refs,
            }

            # Save the message
            reply_message = await self._save_email_message(
                db_session,
                message_data,
                thread.id,
                is_sent_by_system=True,
            )

            if not reply_message:
                logger.error("Failed to save reply message to database")
                return True, None  # Email was sent but not saved

            # Only commit if we created the session
            if session_context:
                await db_session.commit()
            return True, reply_message
        except Exception as e:
            logger.error(f"Error replying to email: {str(e)}")
            # Only rollback if we created the session
            if session_context:
                await db_session.rollback()
            return False, None
        finally:
            # Only close if we created the session
            if session_context:
                await session_context.__aexit__(None, None, None)

    def _prepare_reply_data(self, original_message: EmailMessage) -> Tuple[List[str], str, str]:
        """
        Prepare data needed for replying to an email.

        Args:
            original_message: The original message to reply to

        Returns:
            Tuple of (recipients, subject, references)
        """
        # Determine recipients (original sender + all recipients except us)
        recipients = [original_message.sender]

        # Add original recipients unless they're us
        original_recipients = [r.strip() for r in original_message.recipients.split(",") if r.strip()]
        for recipient in original_recipients:
            if recipient != self.email_client.username and recipient not in recipients:
                recipients.append(recipient)

        # Create subject with "Re: " prefix if not already there
        subject = original_message.subject
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        # Use existing references or create new ones
        references = original_message.references or original_message.message_id

        return recipients, subject, references

    async def get_thread_messages(self, thread_id: str, db_session: Optional[AsyncSession] = None) -> List[EmailMessage]:
        """
        Get all messages in a thread.

        Args:
            thread_id: The thread ID
            db_session: Optional database session for dependency injection in tests

        Returns:
            A list of email messages in the thread, ordered by received date
        """
        session_context = None
        try:
            # Allow session injection for testing
            if db_session is None:
                session_context = get_db_session()
                db_session = await session_context.__aenter__()

            # Join with threads to get messages by thread_id (not thread.id)
            query = (
                select(EmailMessage)
                .join(EmailThread, EmailThread.id == EmailMessage.thread_id)
                .where(EmailThread.thread_id == thread_id)
                .order_by(EmailMessage.received_at)
            )

            result = await db_session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting thread messages: {str(e)}")
            return []
        finally:
            # Only close if we created the session
            if session_context:
                await session_context.__aexit__(None, None, None)

    async def get_recent_threads(self, limit: int = 10, db_session: Optional[AsyncSession] = None) -> List[EmailThread]:
        """
        Get recent email threads.

        Args:
            limit: The maximum number of threads to return
            db_session: Optional database session for dependency injection in tests

        Returns:
            A list of recent email threads, ordered by last update
        """
        session_context = None
        try:
            # Allow session injection for testing
            if db_session is None:
                session_context = get_db_session()
                db_session = await session_context.__aenter__()

            query = (
                select(EmailThread)
                .order_by(EmailThread.updated_at.desc())
                .limit(limit)
                .offset(0)
            )

            result = await db_session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting recent threads: {str(e)}")
            return []
        finally:
            # Only close if we created the session
            if session_context:
                await session_context.__aexit__(None, None, None)
