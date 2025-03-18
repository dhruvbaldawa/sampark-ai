import pytest
from datetime import datetime
from sqlalchemy import select, func
from unittest.mock import AsyncMock, MagicMock, patch

from sampark.adapters.email.client import EmailClient
from sampark.adapters.email.service import EmailService
from sampark.db.models import EmailThread, EmailMessage
from tests.factories.email_thread import EmailThreadFactory
from tests.factories.email_message import EmailMessageFactory


@pytest.fixture
def email_client():
    """Create a mock email client."""
    client = MagicMock(spec=EmailClient)
    client.username = "test@example.com"
    return client


@pytest.fixture
def email_service(email_client):
    """Create an email service with a mock client."""
    return EmailService(email_client=email_client)


@pytest.fixture
def mock_email_thread():
    """Create a mock email thread."""
    return EmailThread(
        id="thread-uuid",
        thread_id="existing-thread-id",
        subject="Test Subject",
    )


@pytest.fixture
def mock_email_message():
    """Create a mock email message."""
    return EmailMessage(
        id="msg-uuid",
        message_id="original-msg-id",
        thread_id="thread-uuid",
        sender="sender@example.com",
        recipients="recipient@example.com, test@example.com",
        cc="cc@example.com",
        subject="Original Subject",
        body_text="Original message",
        in_reply_to=None,
        references=None,
    )


@pytest.fixture
def sample_email_data():
    """Create sample email data."""
    return {
        "message_id": "msg-123@example.com",
        "thread_id": "existing-thread-id",
        "subject": "Test Subject",
        "sender": "sender@example.com",
        "recipients": ["recipient@example.com"],
        "body_text": "This is a test email.",
        "body_html": "<p>This is a test email.</p>",
        "in_reply_to": None,
        "references": None,
    }


@pytest.mark.asyncio
async def test_process_new_email_existing_thread(email_service, db_session, sample_email_data):
    """Test processing a new email with an existing thread."""
    # Given
    # Create a thread in the database
    thread = EmailThreadFactory.create(
        thread_id=sample_email_data["thread_id"],
        subject=sample_email_data["subject"]
    )
    db_session.add(thread)
    await db_session.flush()

    # When
    result = await email_service.process_new_email(sample_email_data, db_session)

    # Then
    assert result is not None
    assert result.message_id == sample_email_data["message_id"]
    assert result.thread_id == thread.id
    assert result.sender == sample_email_data["sender"]
    assert result.body_text == sample_email_data["body_text"]
    assert result.is_sent_by_system is False

    # Verify the message was added to the database
    query = select(func.count()).select_from(EmailMessage).where(
        EmailMessage.message_id == sample_email_data["message_id"]
    )
    result = await db_session.execute(query)
    count = result.scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_process_new_email_new_thread(email_service, db_session, sample_email_data):
    """Test processing a new email with a new thread."""
    # Given: No existing thread in the database

    # When
    result = await email_service.process_new_email(sample_email_data, db_session)

    # Then
    assert result is not None
    assert result.message_id == sample_email_data["message_id"]
    assert result.sender == sample_email_data["sender"]
    assert result.body_text == sample_email_data["body_text"]
    assert result.is_sent_by_system is False

    # Verify both a thread and a message were added to the database
    thread_query = select(func.count()).select_from(EmailThread).where(
        EmailThread.thread_id == sample_email_data["thread_id"]
    )
    thread_result = await db_session.execute(thread_query)
    thread_count = thread_result.scalar_one()
    assert thread_count == 1

    message_query = select(func.count()).select_from(EmailMessage).where(
        EmailMessage.message_id == sample_email_data["message_id"]
    )
    message_result = await db_session.execute(message_query)
    message_count = message_result.scalar_one()
    assert message_count == 1


@pytest.mark.asyncio
async def test_reply_to_email(email_service, db_session):
    """Test replying to an email."""
    # Given
    # Create a thread in the database
    thread = EmailThreadFactory.create(
        thread_id="test-thread-id",
        subject="Original Subject"
    )
    db_session.add(thread)
    await db_session.flush()

    # Create a message in the database - note that we're using thread.thread_id, not thread.id
    message = EmailMessageFactory.create(
        thread_id=thread.thread_id,  # This should be thread.thread_id, not thread.id
        message_id="original-msg-id",
        sender="sender@example.com",
        recipients="recipient@example.com, test@example.com",
        subject="Original Subject",
        body_text="Original message"
    )
    db_session.add(message)
    await db_session.flush()

    # Create another query to retrieve the message to verify it's stored correctly
    query = select(EmailMessage).where(EmailMessage.message_id == "original-msg-id")
    result = await db_session.execute(query)
    stored_message = result.scalar_one_or_none()
    assert stored_message is not None, "Message was not stored correctly"

    # Configure email_client.send_email to return success
    email_service.email_client.send_email = AsyncMock()
    email_service.email_client.send_email.return_value = (True, "reply-msg-id")

    # When
    success, reply_message = await email_service.reply_to_email(
        message_id="original-msg-id",
        body_text="Reply message",
        body_html="<p>Reply message</p>",
        db_session=db_session,
    )

    # Then
    assert success is True, f"Failed to reply to email, check logs for details"
    assert reply_message is not None
    assert reply_message.message_id == "reply-msg-id"
    assert reply_message.in_reply_to == "original-msg-id"
    assert reply_message.is_sent_by_system is True

    # Verify the email client's send_email method was called correctly
    email_service.email_client.send_email.assert_called_once()
    call_args = email_service.email_client.send_email.call_args[1]
    assert "sender@example.com" in call_args["recipients"]
    assert call_args["subject"] == "Re: Original Subject"
    assert call_args["body_text"] == "Reply message"

    # Verify a new message was added to the database
    query = select(func.count()).select_from(EmailMessage).where(
        EmailMessage.message_id == "reply-msg-id"
    )
    result = await db_session.execute(query)
    count = result.scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_get_thread_messages(email_service, db_session):
    """Test getting all messages in a thread."""
    # Given
    # Create a thread in the database
    thread = EmailThreadFactory.create(thread_id="test-thread-id")
    db_session.add(thread)
    await db_session.flush()

    # Create messages in the database
    message1 = EmailMessageFactory.create(
        thread_id=thread.id,
        received_at=datetime(2023, 1, 1)
    )
    message2 = EmailMessageFactory.create(
        thread_id=thread.id,
        received_at=datetime(2023, 1, 2)
    )
    db_session.add(message1)
    db_session.add(message2)
    await db_session.flush()

    # When
    messages = await email_service.get_thread_messages("test-thread-id", db_session)

    # Then
    assert len(messages) == 2
    assert messages[0].id == message1.id  # First one should be older (2023-01-01)
    assert messages[1].id == message2.id  # Second one should be newer (2023-01-02)


@pytest.mark.asyncio
async def test_get_recent_threads(email_service, db_session):
    """Test getting recent threads."""
    # Given
    # Create threads in the database with different updated_at times
    thread1 = EmailThreadFactory.create(
        updated_at=datetime(2023, 1, 1)
    )
    thread2 = EmailThreadFactory.create(
        updated_at=datetime(2023, 1, 2)
    )
    db_session.add(thread1)
    db_session.add(thread2)
    await db_session.flush()

    # When
    threads = await email_service.get_recent_threads(limit=2, db_session=db_session)

    # Then
    assert len(threads) == 2
    assert threads[0].id == thread2.id  # Most recent first (2023-01-02)
    assert threads[1].id == thread1.id  # Oldest last (2023-01-01)
