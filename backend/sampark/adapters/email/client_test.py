import asyncio
from email.message import Message
import pytest
from typing import Tuple
from unittest.mock import AsyncMock, MagicMock

from pytest_mock import MockerFixture

from sampark.adapters.email.client import EmailClient, EmailMonitor


@pytest.fixture
def email_client() -> EmailClient:
    """Fixture for EmailClient instance."""
    return EmailClient(
        imap_server="imap.example.com",
        imap_port=993,
        smtp_server="smtp.example.com",
        smtp_port=587,
        username="test@example.com",
        password="password",
    )


@pytest.fixture
def mock_imap(mocker: MockerFixture) -> Tuple[MagicMock, MagicMock]:
    """Fixture for mocked IMAP connection."""
    mock_imap = mocker.patch("imaplib.IMAP4_SSL")
    mock_instance = mock_imap.return_value
    mock_instance.state = "SELECTED"
    return mock_imap, mock_instance


@pytest.fixture
def mock_smtp(mocker: MockerFixture) -> MagicMock:
    """Fixture for mocked SMTP connection."""
    mock_smtp = mocker.patch("aiosmtplib.SMTP")
    mock_instance = mock_smtp.return_value
    mock_instance.connect = AsyncMock()
    mock_instance.login = AsyncMock()
    mock_instance.send_message = AsyncMock()
    mock_instance.quit = AsyncMock()
    # Return success for send_message
    mock_instance.send_message.return_value = {}
    return mock_smtp


@pytest.fixture
def email_monitor() -> EmailMonitor:
    """Fixture for EmailMonitor instance."""
    email_client = EmailClient(
        imap_server="imap.example.com",
        imap_port=993,
        smtp_server="smtp.example.com",
        smtp_port=587,
        username="test@example.com",
        password="password",
    )
    return EmailMonitor(email_client=email_client, check_interval=1)


def test_connect_imap(email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock]) -> None:
    """Test connecting to an IMAP server."""
    # Get the mock instance from the tuple
    _, mock_instance = mock_imap

    # Call the connect method
    email_client._connect_imap()  # type: ignore # Protected member access is acceptable in tests

    # Verify that the expected methods were called
    mock_instance.assert_called_once_with("imap.example.com", 993)
    mock_instance.login.assert_called_once_with("test@example.com", "password")
    mock_instance.select.assert_called_once_with("INBOX")


def test_disconnect_imap(email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock]) -> None:
    """Test disconnecting from an IMAP server."""
    # Set up the IMAP connection
    _, mock_instance = mock_imap
    email_client._imap = mock_instance  # type: ignore # Protected member access is acceptable in tests

    # Call the disconnect method
    email_client._disconnect_imap()  # type: ignore # Protected member access is acceptable in tests

    # Verify that the expected methods were called
    mock_instance.close.assert_called_once()
    mock_instance.logout.assert_called_once()
    assert email_client._imap is None  # type: ignore # Protected member access is acceptable in tests


def test_extract_thread_id_from_references(email_client: EmailClient) -> None:
    """Test extracting thread ID from References header."""
    # Create a test message with References header
    test_msg = Message()
    test_msg["References"] = "<thread-123@example.com> <msg-456@example.com>"

    # Extract the thread ID
    thread_id = email_client._extract_thread_id(test_msg)  # type: ignore # Protected member access is acceptable in tests

    # Verify that it extracted the first message ID
    assert thread_id == "thread-123@example.com"


def test_extract_thread_id_from_in_reply_to(email_client: EmailClient) -> None:
    """Test extracting thread ID from In-Reply-To header."""
    # Create a test message with In-Reply-To header
    test_msg = Message()
    test_msg["In-Reply-To"] = "<thread-123@example.com>"

    # Extract the thread ID
    thread_id = email_client._extract_thread_id(test_msg)  # type: ignore # Protected member access is acceptable in tests

    # Verify that it extracted the message ID
    assert thread_id == "thread-123@example.com"


def test_extract_thread_id_fallback(email_client: EmailClient) -> None:
    """Test thread ID fallback to subject + sender."""
    # Create a test message with no References or In-Reply-To
    test_msg = Message()
    test_msg["Subject"] = "Test Subject"
    test_msg["From"] = "sender@example.com"

    # Extract the thread ID
    thread_id = email_client._extract_thread_id(test_msg)  # type: ignore # Protected member access is acceptable in tests

    # Verify that it created an ID from subject and sender
    assert thread_id == "Test Subject_sender@example.com"


def test_check_new_emails(
    email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock], mocker: MockerFixture
) -> None:
    """Test checking for new emails."""
    # Set up the IMAP connection
    _, mock_instance = mock_imap
    mock_instance.search.return_value = ("OK", [b"1 2 3"])
    mock_instance.fetch.return_value = (
        "OK",
        [(b"1", b"test-email-data"), (b"FETCH", b"")],
    )

    # Mock the parse email method
    mocker.patch.object(
        email_client,
        "_parse_email",
        return_value={
            "message_id": "msg-123",
            "subject": "Test Email",
            "sender": "sender@example.com",
        },
    )

    # Check for new emails
    emails = email_client.check_new_emails()

    # Verify the results
    assert len(emails) == 1
    assert emails[0]["message_id"] == "msg-123"

    # Verify that search was called with UNSEEN
    mock_instance.search.assert_called_once_with(None, "UNSEEN")


@pytest.mark.asyncio
async def test_send_email(email_client: EmailClient, mock_smtp: MagicMock) -> None:
    """Test sending an email."""
    # Reset the mock to clear any previous calls
    mock_smtp.reset_mock()

    # Setup AsyncMock for the actual SMTP instance
    mock_instance = mock_smtp.return_value

    # Send an email
    success, message_id = await email_client.send_email(
        recipients="recipient@example.com",
        subject="Test Subject",
        body_text="This is a test email.",
    )

    # Verify results
    assert mock_smtp.called
    assert mock_instance.connect.called
    assert mock_instance.login.called
    assert mock_instance.send_message.called
    assert mock_instance.quit.called
    assert success is True
    assert message_id != ""


def test_register_callback(email_monitor: EmailMonitor) -> None:
    """Test registering callbacks."""
    # Create a mock callback
    callback = AsyncMock()

    # Register the callback
    email_monitor.register_callback(callback)

    # Verify the callback was registered
    assert callback in email_monitor._new_email_callbacks  # type: ignore # Protected member access is acceptable in tests


@pytest.mark.asyncio
async def test_check_emails(email_monitor: EmailMonitor) -> None:
    """Test checking for new emails in the monitor."""
    # Create a mock for the email client
    mock_email_client = MagicMock()
    mock_email_client.check_new_emails.return_value = [{"message_id": "msg-123@example.com", "subject": "Test Email"}]

    # Replace the real email client with our mock
    email_monitor.email_client = mock_email_client

    # Register a mock callback
    callback = AsyncMock()
    email_monitor.register_callback(callback)

    # Start monitoring
    email_monitor.start()
    await asyncio.sleep(2)
    await email_monitor.stop()

    # Verify the callback was called with the email data
    assert mock_email_client.check_new_emails.called
    callback.assert_called_with({"message_id": "msg-123@example.com", "subject": "Test Email"})


def test_parse_email_plain_text(email_client: EmailClient) -> None:
    """Test parsing a plain text email."""
    # Create a test email
    raw_email = (
        b"From: sender@example.com\r\n"
        b"To: recipient1@example.com, recipient2@example.com\r\n"
        b"Cc: cc1@example.com, cc2@example.com\r\n"
        b"Subject: Test Subject\r\n"
        b"Message-ID: <msg-123@example.com>\r\n"
        b"Content-Type: text/plain\r\n\r\n"
        b"This is a test email."
    )

    # Parse the email
    result = email_client._parse_email(raw_email)  # type: ignore # Protected member access is acceptable in tests

    # Verify the parsed data
    assert result["message_id"] == "msg-123@example.com"
    assert result["subject"] == "Test Subject"
    assert result["sender"] == "sender@example.com"
    assert "recipient1@example.com" in result["recipients"]
    assert "recipient2@example.com" in result["recipients"]
    assert "cc1@example.com" in result["cc"]
    assert "cc2@example.com" in result["cc"]
    assert result["body_text"] == "This is a test email."
    assert result["body_html"] == ""


def test_parse_email_multipart(email_client: EmailClient) -> None:
    """Test parsing a multipart email with text and HTML parts."""
    # Create a test multipart email
    raw_email = (
        b"From: sender@example.com\r\n"
        b"To: recipient@example.com\r\n"
        b"Subject: Test Multipart\r\n"
        b"Message-ID: <msg-456@example.com>\r\n"
        b'Content-Type: multipart/alternative; boundary="boundary"\r\n\r\n'
        b"--boundary\r\n"
        b"Content-Type: text/plain\r\n\r\n"
        b"This is plain text\r\n"
        b"--boundary\r\n"
        b"Content-Type: text/html\r\n\r\n"
        b"<p>This is HTML</p>\r\n"
        b"--boundary--\r\n"
    )

    # Parse the email
    result = email_client._parse_email(raw_email)  # type: ignore # Protected member access is acceptable in tests

    # Verify the parsed data
    assert result["message_id"] == "msg-456@example.com"
    assert result["subject"] == "Test Multipart"
    assert result["body_text"] == "This is plain text"
    assert result["body_html"] == "<p>This is HTML</p>"


@pytest.mark.asyncio
async def test_send_email_with_optional_parameters(email_client: EmailClient, mock_smtp: MagicMock) -> None:
    """Test sending an email with all optional parameters."""
    # Reset the mock
    mock_smtp.reset_mock()

    # Send an email with all optional parameters
    success, message_id = await email_client.send_email(
        recipients=["recipient1@example.com", "recipient2@example.com"],
        subject="Test Subject",
        body_text="This is a test email.",
        body_html="<p>This is a test email.</p>",
        cc=["cc1@example.com", "cc2@example.com"],
        in_reply_to="original-msg-id",
        references="original-thread-id",
    )

    # Verify SMTP client was used correctly
    mock_instance = mock_smtp.return_value
    assert mock_instance.send_message.called
    assert success is True
    assert message_id != ""

    # Verify the message structure
    call_args = mock_instance.send_message.call_args[0]
    sent_message = call_args[0]
    assert sent_message["Subject"] == "Test Subject"
    assert "recipient1@example.com" in sent_message["To"]
    assert "recipient2@example.com" in sent_message["To"]
    assert "cc1@example.com" in sent_message["Cc"]
    assert "cc2@example.com" in sent_message["Cc"]
    assert sent_message["In-Reply-To"] == "<original-msg-id>"
    # The References header appends the in-reply-to value to the existing references
    assert "original-thread-id" in sent_message["References"]
    assert "<original-msg-id>" in sent_message["References"]
