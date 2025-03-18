import asyncio
from email.message import Message
from email.mime.multipart import MIMEMultipart
import imaplib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_mock import MockerFixture

from sampark.adapters.email.client import EmailClient, EmailMonitor


@pytest.fixture
def email_client():
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
def mock_imap(mocker):
    """Fixture for mocked IMAP connection."""
    mock_imap = mocker.patch("imaplib.IMAP4_SSL")
    mock_instance = mock_imap.return_value
    mock_instance.state = "SELECTED"
    return mock_imap, mock_instance


@pytest.fixture
def mock_smtp(mocker):
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
def email_monitor():
    """Fixture for EmailMonitor instance."""
    email_client = MagicMock()
    return EmailMonitor(
        email_client=email_client,
        check_interval=1,  # Short interval for tests
    )


def test_connect_imap(email_client, mock_imap):
    """Test connecting to IMAP server."""
    # Given
    mock_imap, mock_instance = mock_imap

    # When
    email_client._connect_imap()

    # Then
    mock_imap.assert_called_once_with("imap.example.com", 993)
    mock_instance.login.assert_called_once_with("test@example.com", "password")
    mock_instance.select.assert_called_once_with("INBOX")


def test_disconnect_imap(email_client, mock_imap):
    """Test disconnecting from IMAP server."""
    # Given
    _, mock_instance = mock_imap
    email_client._imap = mock_instance

    # When
    email_client._disconnect_imap()

    # Then
    mock_instance.close.assert_called_once()
    mock_instance.logout.assert_called_once()
    assert email_client._imap is None


def test_extract_thread_id_from_references(email_client):
    """Test extracting thread ID from References header."""
    # Given
    msg = Message()
    msg["References"] = "<thread-123@example.com> <msg-456@example.com>"

    # When
    thread_id = email_client._extract_thread_id(msg)

    # Then
    assert thread_id == "thread-123@example.com"


def test_extract_thread_id_from_in_reply_to(email_client):
    """Test extracting thread ID from In-Reply-To header when References is missing."""
    # Given
    msg = Message()
    msg["In-Reply-To"] = "<thread-123@example.com>"

    # When
    thread_id = email_client._extract_thread_id(msg)

    # Then
    assert thread_id == "thread-123@example.com"


def test_extract_thread_id_fallback(email_client):
    """Test thread ID fallback when References and In-Reply-To are missing."""
    # Given
    msg = Message()
    msg["Subject"] = "Test Subject"
    msg["From"] = "sender@example.com"

    # When
    thread_id = email_client._extract_thread_id(msg)

    # Then
    assert thread_id == "Test Subject_sender@example.com"


def test_check_new_emails(email_client, mock_imap, mocker):
    """Test checking for new emails."""
    # Given
    _, mock_instance = mock_imap
    mock_instance.search.return_value = ("OK", [b"1"])  # Only return one message ID

    # Create sample email data
    raw_email = (
        b'From: sender@example.com\r\n'
        b'To: recipient@example.com\r\n'
        b'Subject: Test Subject\r\n'
        b'Message-ID: <msg-123@example.com>\r\n'
        b'Content-Type: text/plain\r\n\r\n'
        b'This is a test email.'
    )

    mock_instance.fetch.return_value = ("OK", [(b'1', raw_email)])

    # Mock parse_email method
    mock_parse = mocker.patch.object(email_client, '_parse_email')
    mock_parse.return_value = {
        "message_id": "msg-123@example.com",
        "subject": "Test Subject",
        "thread_id": "Test Subject_sender@example.com",
        "body_text": "This is a test email.",
    }

    # When
    emails = email_client.check_new_emails()

    # Then
    assert len(emails) == 1
    assert emails[0]["message_id"] == "msg-123@example.com"
    mock_instance.search.assert_called_once_with(None, "UNSEEN")


@pytest.mark.asyncio
async def test_send_email(email_client, mock_smtp):
    """Test sending an email."""
    # Given
    # Reset the mock to clear any previous calls
    mock_smtp.reset_mock()

    # Setup AsyncMock for the actual SMTP instance
    mock_instance = mock_smtp.return_value

    # When
    success, message_id = await email_client.send_email(
        recipients="recipient@example.com",
        subject="Test Subject",
        body_text="This is a test email.",
    )

    # Then
    mock_smtp.assert_called_once()
    assert mock_instance.connect.called
    assert mock_instance.login.called
    assert mock_instance.send_message.called
    assert mock_instance.quit.called
    assert success is True
    assert message_id != ""


def test_register_callback(email_monitor):
    """Test registering callbacks."""
    # Given
    callback = AsyncMock()

    # When
    email_monitor.register_callback(callback)

    # Then
    assert callback in email_monitor._new_email_callbacks


@pytest.mark.asyncio
async def test_check_emails(email_monitor):
    """Test checking for new emails in the monitor."""
    # Given
    email_monitor.email_client.check_new_emails.return_value = [
        {"message_id": "msg-123@example.com", "subject": "Test Email"}
    ]
    callback = AsyncMock()
    email_monitor.register_callback(callback)

    # When
    email_monitor.start()
    await asyncio.sleep(2)
    await email_monitor.stop()

    # Then
    assert email_monitor.email_client.check_new_emails.called
    callback.assert_called_with(
        {"message_id": "msg-123@example.com", "subject": "Test Email"}
    )


def test_parse_email_plain_text(email_client):
    """Test parsing a plain text email."""
    # Given
    raw_email = (
        b'From: sender@example.com\r\n'
        b'To: recipient1@example.com, recipient2@example.com\r\n'
        b'Cc: cc1@example.com, cc2@example.com\r\n'
        b'Subject: Test Subject\r\n'
        b'Message-ID: <msg-123@example.com>\r\n'
        b'Content-Type: text/plain\r\n\r\n'
        b'This is a test email.'
    )

    # When
    result = email_client._parse_email(raw_email)

    # Then
    assert result["message_id"] == "msg-123@example.com"
    assert result["subject"] == "Test Subject"
    assert result["sender"] == "sender@example.com"
    assert "recipient1@example.com" in result["recipients"]
    assert "recipient2@example.com" in result["recipients"]
    assert "cc1@example.com" in result["cc"]
    assert "cc2@example.com" in result["cc"]
    assert result["body_text"] == "This is a test email."
    assert result["body_html"] == ""


def test_parse_email_multipart(email_client):
    """Test parsing a multipart email with text and HTML parts."""
    # Given
    raw_email = (
        b'From: sender@example.com\r\n'
        b'To: recipient@example.com\r\n'
        b'Subject: Test Multipart\r\n'
        b'Message-ID: <msg-456@example.com>\r\n'
        b'Content-Type: multipart/alternative; boundary="boundary"\r\n\r\n'
        b'--boundary\r\n'
        b'Content-Type: text/plain\r\n\r\n'
        b'This is plain text\r\n'
        b'--boundary\r\n'
        b'Content-Type: text/html\r\n\r\n'
        b'<p>This is HTML</p>\r\n'
        b'--boundary--\r\n'
    )

    # When
    result = email_client._parse_email(raw_email)

    # Then
    assert result["message_id"] == "msg-456@example.com"
    assert result["subject"] == "Test Multipart"
    assert result["body_text"] == "This is plain text"
    assert result["body_html"] == "<p>This is HTML</p>"


@pytest.mark.asyncio
async def test_send_email_with_optional_parameters(email_client, mock_smtp):
    """Test sending an email with all optional parameters."""
    # Given
    mock_smtp.reset_mock()

    # When
    success, message_id = await email_client.send_email(
        recipients=["recipient1@example.com", "recipient2@example.com"],
        subject="Test Subject",
        body_text="This is a test email.",
        body_html="<p>This is a test email.</p>",
        cc=["cc1@example.com", "cc2@example.com"],
        in_reply_to="original-msg-id",
        references="original-thread-id"
    )

    # Then
    mock_instance = mock_smtp.return_value
    assert mock_instance.send_message.called
    assert success is True
    assert message_id != ""

    # Check that the message was constructed correctly by examining the call
    # args of send_message method
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
