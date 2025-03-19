import pytest
from unittest.mock import AsyncMock, MagicMock
import logging
from typing import Dict, Any, cast
from pytest import LogCaptureFixture

from sampark.__main__ import process_email_callback
from sampark.adapters.email.service import EmailService
from sampark.db.models import EmailMessage


@pytest.fixture
def email_data() -> Dict[str, Any]:
    """Create sample email data for testing."""
    return {
        "message_id": "test-msg-123@example.com",
        "thread_id": "thread-123@example.com",
        "subject": "Test Email",
        "sender": "sender@example.com",
        "recipients": ["recipient@example.com"],
        "cc": ["cc@example.com"],
        "body_text": "This is a test email.",
        "body_html": "<p>This is a test email.</p>",
        "date": "2023-03-15T10:00:00Z",
    }


@pytest.fixture
def mock_email_service() -> MagicMock:
    """Create a mock email service for testing."""
    email_service = MagicMock(spec=EmailService)

    # Create session class with async context manager
    session_class = MagicMock()

    # Mock the Session context manager
    mock_session = AsyncMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

    # Configure the session class to return the context manager
    session_class.return_value = mock_session_ctx

    # Attach the session class to the email service
    email_service.Session = session_class

    # Store the mock session for assertions
    email_service.mock_session = mock_session

    return email_service


@pytest.mark.asyncio
async def test_process_email_callback_success(
    mock_email_service: MagicMock, email_data: Dict[str, Any], caplog: LogCaptureFixture
) -> None:
    """Test successful processing of an email callback."""
    # Configure the logger to capture logs
    caplog.set_level(logging.INFO)

    # Mock the process_new_email method to return a message
    mock_message = MagicMock(spec=EmailMessage)
    mock_message.message_id = email_data["message_id"]
    mock_email_service.process_new_email = AsyncMock(return_value=mock_message)

    # Mock the reply_to_email method to return success
    mock_email_service.reply_to_email = AsyncMock(return_value=(True, MagicMock()))

    # Call the function
    await process_email_callback(cast(EmailService, mock_email_service), email_data)

    # Verify process_new_email was called with the right arguments
    mock_email_service.process_new_email.assert_called_once_with(
        email_data, db_session=mock_email_service.mock_session
    )

    # Verify reply_to_email was called
    mock_email_service.reply_to_email.assert_called_once()

    # Verify the session was committed at least once
    assert mock_email_service.mock_session.commit.called

    # Verify appropriate logs were written
    assert f"Processing new email: {email_data['subject']} from {email_data['sender']}" in caplog.text
    assert f"Sending acknowledgment reply to {email_data['message_id']}" in caplog.text
    assert "Sent acknowledgment reply successfully" in caplog.text


@pytest.mark.asyncio
async def test_process_email_callback_no_message(
    mock_email_service: MagicMock, email_data: Dict[str, Any], caplog: LogCaptureFixture
) -> None:
    """Test email callback when process_new_email returns None (skipped or already processed)."""
    # Configure the logger to capture logs
    caplog.set_level(logging.INFO)

    # Mock the process_new_email method to return None (no message created)
    mock_email_service.process_new_email = AsyncMock(return_value=None)

    # Call the function
    await process_email_callback(cast(EmailService, mock_email_service), email_data)

    # Verify process_new_email was called
    mock_email_service.process_new_email.assert_called_once_with(
        email_data, db_session=mock_email_service.mock_session
    )

    # Verify reply_to_email was not called
    assert not mock_email_service.reply_to_email.called

    # Verify the session was committed
    mock_email_service.mock_session.commit.assert_called_once()

    # Verify appropriate logs were written
    assert f"Processing new email: {email_data['subject']} from {email_data['sender']}" in caplog.text
    assert "Failed to process email, or message already processed" in caplog.text


@pytest.mark.asyncio
async def test_process_email_callback_exception(
    mock_email_service: MagicMock, email_data: Dict[str, Any], caplog: LogCaptureFixture
) -> None:
    """Test error handling in the email callback function."""
    # Configure the logger to capture logs
    caplog.set_level(logging.ERROR)

    # Mock the process_new_email method to raise an exception
    mock_email_service.process_new_email = AsyncMock(side_effect=Exception("Test error"))

    # Call the function
    await process_email_callback(cast(EmailService, mock_email_service), email_data)

    # Verify the session was rolled back
    mock_email_service.mock_session.rollback.assert_called_once()

    # Verify the exception was logged
    assert "Error in process_email_callback: Test error" in caplog.text


@pytest.mark.asyncio
async def test_process_email_callback_reply_failure(
    mock_email_service: MagicMock, email_data: Dict[str, Any], caplog: LogCaptureFixture
) -> None:
    """Test handling of reply failure in the email callback function."""
    # Configure the logger to capture logs
    caplog.set_level(logging.ERROR)

    # Mock the process_new_email method to return a message
    mock_message = MagicMock(spec=EmailMessage)
    mock_message.message_id = email_data["message_id"]
    mock_email_service.process_new_email = AsyncMock(return_value=mock_message)

    # Mock the reply_to_email method to return failure
    mock_email_service.reply_to_email = AsyncMock(return_value=(False, None))

    # Call the function
    await process_email_callback(cast(EmailService, mock_email_service), email_data)

    # Verify process_new_email was called
    mock_email_service.process_new_email.assert_called_once()

    # Verify reply_to_email was called
    mock_email_service.reply_to_email.assert_called_once()

    # Verify the session was committed at least once
    assert mock_email_service.mock_session.commit.called

    # Verify the failure was logged
    assert "Failed to send acknowledgment reply" in caplog.text
