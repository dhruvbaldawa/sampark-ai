import json
import logging
from typing import Dict, List, Optional, Tuple, Any, Union, cast

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
        self.Session = get_db_session

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

    async def _create_email_thread(
        self, db_session: AsyncSession, thread_id: str, subject: str, initial_participants: Optional[List[str]] = None
    ) -> Optional[EmailThread]:
        """Create a new email thread."""
        try:
            # Initialize with empty list if none provided
            participants = initial_participants if initial_participants is not None else []

            # Serialize participants to JSON string
            serialized_participants = json.dumps(participants)

            thread = EmailThread(
                thread_id=thread_id,
                subject=subject,
                participants=serialized_participants,
            )
            db_session.add(thread)
            await db_session.flush()
            return thread
        except SQLAlchemyError as e:
            logger.error(f"Error creating email thread: {str(e)}")
            return None

    # Helper method to get and update participants
    def _get_participants(self, thread: EmailThread) -> List[str]:
        """Get the list of participants from a thread."""
        participants_str = getattr(thread, "participants", "[]")
        try:
            return json.loads(participants_str)
        except (json.JSONDecodeError, TypeError):
            return []

    async def _update_participants(
        self, db_session: AsyncSession, thread: EmailThread, new_participants: List[str]
    ) -> None:
        """Update the participants list for a thread."""
        serialized = json.dumps(list(set(new_participants)))
        thread.participants = serialized
        db_session.add(thread)
        await db_session.commit()

    async def _save_email_message(
        self, db_session: AsyncSession, message_data: Dict[str, Any], thread_id: str, is_sent_by_system: bool = False
    ) -> Optional[EmailMessage]:
        """Create and save an email message."""
        try:
            # Get recipients as a string, properly handling the case when it's already a string
            recipients_raw = message_data["recipients"]
            recipients_str = (
                ", ".join(cast(List[str], recipients_raw)) if isinstance(recipients_raw, list) else str(recipients_raw)
            )

            # Get CC as a string, handling the case when it's empty or already a string
            cc_raw = message_data.get("cc", [])
            cc_str = ", ".join(cast(List[str], cc_raw)) if isinstance(cc_raw, list) else str(cc_raw or "")

            message = EmailMessage(
                thread_id=thread_id,
                message_id=message_data["message_id"],
                sender=message_data["sender"],
                recipients=recipients_str,
                cc=cc_str,
                subject=message_data["subject"],
                body_text=message_data.get("body_text", ""),
                body_html=message_data.get("body_html", ""),
                in_reply_to=message_data.get("in_reply_to", ""),
                references=message_data.get("references", ""),
                is_sent_by_system=is_sent_by_system,
            )
            db_session.add(message)
            await db_session.commit()
            await db_session.refresh(message)
            return message
        except SQLAlchemyError as e:
            logger.error(f"Error saving email message: {str(e)}")
            await db_session.rollback()
            return None

    async def process_new_email(
        self, email_data: Dict[str, Any], db_session: Optional[AsyncSession] = None
    ) -> Optional[EmailMessage]:
        """
        Process a new email, saving it to the database.

        Args:
            email_data: Data for the new email
            db_session: Optional database session

        Returns:
            The created EmailMessage or None if there was an error
        """
        session_context = None
        try:
            # Create a session if one wasn't provided
            if db_session is None:
                session_context = self.Session()
                db_session = await session_context.__aenter__()

            # Check if this message already exists in the database
            existing_message = await self._get_message_by_message_id(db_session, email_data["message_id"])
            if existing_message:
                logger.info(f"Message with ID {email_data['message_id']} already exists, skipping processing")
                return None

            # Get or create the thread
            thread = await self._get_thread_by_thread_id(db_session, email_data["thread_id"])
            if not thread:
                logger.info(f"Creating new thread for email with thread_id: {email_data['thread_id']}")
                thread = await self._create_email_thread(
                    db_session=db_session,
                    thread_id=email_data["thread_id"],
                    subject=email_data["subject"],
                )
                if not thread:
                    logger.error(f"Failed to create thread with thread_id: {email_data['thread_id']}")
                    return None

                # Commit the thread creation to ensure it's persisted
                if session_context:  # Only commit if we created the session
                    await db_session.commit()

            # Add participants to the thread if needed
            all_participants = self._get_participants(thread)
            participants_set = set(all_participants)

            # Add sender
            sender = str(email_data["sender"])
            if sender:
                participants_set.add(sender)

            # Add recipients
            recipients_raw: Union[List[Optional[str]], str, None] = email_data.get("recipients", [])
            if isinstance(recipients_raw, list):
                for item in recipients_raw:
                    recipient_str: str = str(item) if item is not None else ""
                    if recipient_str:
                        participants_set.add(recipient_str)
            elif isinstance(recipients_raw, str) and recipients_raw:
                participants_set.add(recipients_raw)

            # Update participants if they've changed
            if set(all_participants) != participants_set:
                await self._update_participants(db_session, thread, list(participants_set))
                # No need to commit here as _update_participants already commits

            # Save the message
            message = await self._save_email_message(
                db_session=db_session,
                message_data=email_data,
                thread_id=thread.id,
            )

            # Explicitly commit the message creation if we created the session
            if session_context and message:
                await db_session.commit()

            return message
        except Exception as e:
            logger.error(f"Error processing new email: {str(e)}")
            # Only rollback if we created the session and it's valid
            if session_context and db_session:
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
        db_session: Optional[AsyncSession] = None,
    ) -> Tuple[bool, Optional[EmailMessage]]:
        """
        Reply to an email.

        Args:
            message_id: The ID of the message to reply to
            body_text: Plain text reply body
            body_html: HTML reply body (optional)
            db_session: Optional database session

        Returns:
            Tuple of (success, created message)
        """
        session_context = None
        try:
            # Create a session if one wasn't provided
            if db_session is None:
                session_context = self.Session()
                db_session = await session_context.__aenter__()

            # Get the original message
            original_message = await self._get_message_by_message_id(db_session, message_id)
            if not original_message:
                logger.error(f"Original message {message_id} not found")
                return False, None

            # Prepare the reply data
            recipients, subject, references = self._prepare_reply_data(original_message)

            # Send the reply
            success, reply_id = await self.email_client.send_email(
                recipients=recipients,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                in_reply_to=original_message.message_id,
                references=references,
            )

            if not success:
                logger.error("Failed to send reply email")
                return False, None

            # Save the sent message
            reply_data = {
                "message_id": reply_id,
                "in_reply_to": original_message.message_id,
                "references": references,
                "subject": subject,
                "sender": self.email_client.username,
                "recipients": recipients,
                "body_text": body_text,
                "body_html": body_html or "",
            }

            reply_message = await self._save_email_message(
                db_session=db_session,
                message_data=reply_data,
                thread_id=original_message.thread_id,
                is_sent_by_system=True,
            )

            # Commit again to ensure the reply message is persisted
            await db_session.commit()

            return True, reply_message
        except Exception as e:
            logger.error(f"Error replying to email: {e}")
            import traceback; traceback.print_exc()
            # Only rollback if we created the session and it's valid
            if session_context and db_session:
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

    async def get_thread_messages(
        self, thread_id: str, db_session: Optional[AsyncSession] = None
    ) -> List[EmailMessage]:
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
                session_context = self.Session()
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
                session_context = self.Session()
                db_session = await session_context.__aenter__()

            query = select(EmailThread).order_by(EmailThread.updated_at.desc()).limit(limit).offset(0)

            result = await db_session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting recent threads: {str(e)}")
            return []
        finally:
            # Only close if we created the session
            if session_context:
                await session_context.__aexit__(None, None, None)
