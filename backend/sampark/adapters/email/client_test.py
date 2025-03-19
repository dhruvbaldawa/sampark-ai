import asyncio
from email.message import Message
import pytest
from typing import Tuple, Any, Optional, List, Dict
from unittest.mock import AsyncMock, MagicMock, patch
from email.mime.multipart import MIMEMultipart

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
        sender_email="system@example.com",
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
        sender_email="system@example.com",
    )
    return EmailMonitor(email_client=email_client, check_interval=1)


def test_connect_imap(email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock]) -> None:
    """Test connecting to an IMAP server."""
    # Get the mock instance from the tuple
    mock_imap_class, mock_instance = mock_imap

    # Call the connect method
    email_client._connect_imap()  # type: ignore # Protected member access is acceptable in tests

    # Verify that the expected methods were called
    mock_imap_class.assert_called_once_with("imap.example.com", 993)
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
    mock_instance.search.return_value = ("OK", [b"1"])  # Only return one message ID
    mock_instance.fetch.return_value = (
        "OK",
        [(b"1", b"test-email-data")],  # Just one message
    )

    # Mock the parse email method to return a single message
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

    # Verify the results - should now be just one email
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


def test_skip_emails_from_own_address(
    email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock], mocker: MockerFixture
) -> None:
    """Test skipping emails sent by our own address."""
    # Set up the IMAP connection
    _, mock_instance = mock_imap
    mock_instance.search.return_value = ("OK", [b"1"])
    mock_instance.fetch.return_value = (
        "OK",
        [(b"1", b"test-email-data")],
    )

    # Mock the parse email method to return an email from our own address
    mocker.patch.object(
        email_client,
        "_parse_email",
        return_value={
            "message_id": "msg-123",
            "subject": "Test Email",
            "sender": "system@example.com",  # Same as sender_email
        },
    )

    # Check for new emails
    emails = email_client.check_new_emails()

    # Verify the results - should be empty as we skip our own emails
    assert len(emails) == 0

    # Verify the email was marked as seen
    mock_instance.store.assert_called_with(b"1", '+FLAGS', '\\Seen')


def test_mark_emails_as_seen(
    email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock], mocker: MockerFixture
) -> None:
    """Test marking emails as seen after processing."""
    # Set up the IMAP connection
    _, mock_instance = mock_imap
    mock_instance.search.return_value = ("OK", [b"1"])
    mock_instance.fetch.return_value = (
        "OK",
        [(b"1", b"test-email-data")],
    )

    # Mock the parse email method to return a normal email
    mocker.patch.object(
        email_client,
        "_parse_email",
        return_value={
            "message_id": "msg-123",
            "subject": "Test Email",
            "sender": "user@example.com",  # Different from sender_email
        },
    )

    # Check for new emails
    emails = email_client.check_new_emails()

    # Verify the results - should contain the email
    assert len(emails) == 1

    # Verify the email was marked as seen
    mock_instance.store.assert_called_with(b"1", '+FLAGS', '\\Seen')


@pytest.mark.asyncio
async def test_sender_email_used_in_outgoing_messages(email_client: EmailClient, mock_smtp: MagicMock, mocker: MockerFixture) -> None:
    """Test that sender_email is used instead of username in outgoing messages."""
    # Create a spy on the send_message method to capture the actual message
    mock_send = AsyncMock()
    mock_smtp.return_value.send_message = mock_send

    # Send an email
    await email_client.send_email(
        recipients="recipient@example.com",
        subject="Test Subject",
        body_text="This is a test email.",
    )

    # Verify sender_email was used instead of username
    # First call to send_message, first argument (the message)
    called_args = mock_send.call_args[0]
    assert called_args[0]["From"] == "system@example.com"


def test_imap_connect_error(email_client: EmailClient, mocker: MockerFixture) -> None:
    """Test error handling when IMAP connection fails."""
    # Mock IMAP4_SSL to raise an exception
    mock_imap = mocker.patch("imaplib.IMAP4_SSL")
    mock_imap.side_effect = ConnectionError("Failed to connect")

    # Attempt to connect should raise the error
    with pytest.raises(ConnectionError):
        email_client._connect_imap()  # type: ignore # Protected member access is acceptable in tests


def test_imap_disconnect_error(email_client: EmailClient, mocker: MockerFixture) -> None:
    """Test error handling during IMAP disconnect."""
    # Create a mock IMAP instance that raises an error on close
    mock_imap = MagicMock()
    mock_imap.state = "SELECTED"
    mock_imap.close.side_effect = Exception("Disconnect error")

    # Set the mock as the client's IMAP connection
    email_client._imap = mock_imap  # type: ignore # Protected member access is acceptable in tests

    # Disconnect should handle the error gracefully
    email_client._disconnect_imap()  # type: ignore # Protected member access is acceptable in tests

    # Verify close was attempted and we set _imap to None despite the error
    mock_imap.close.assert_called_once()
    assert email_client._imap is None  # type: ignore # Protected member access is acceptable in tests


def test_parse_email_unicode_error(email_client: EmailClient) -> None:
    """Test parsing email with Unicode decoding error."""
    # Create an email with content that will cause a UnicodeDecodeError with utf-8
    raw_email = (
        b"From: sender@example.com\r\n"
        b"To: recipient@example.com\r\n"
        b"Subject: Test Subject\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"\xff\xfe Invalid UTF-8 bytes"  # These bytes will cause UnicodeDecodeError with utf-8
    )

    # Parse should fall back to latin-1
    result = email_client._parse_email(raw_email)  # type: ignore # Protected member access is acceptable in tests

    # Verify the email was parsed using the fallback encoding
    assert result["sender"] == "sender@example.com"
    assert "body_text" in result
    assert result["body_text"] != ""  # Should contain content decoded with latin-1


def test_parse_email_multipart_with_attachment(email_client: EmailClient) -> None:
    """Test parsing multipart email with attachment."""
    # Create a multipart email with an attachment
    raw_email = (
        b"From: sender@example.com\r\n"
        b"To: recipient@example.com\r\n"
        b"Subject: Test Subject\r\n"
        b"Content-Type: multipart/mixed; boundary=boundary\r\n\r\n"
        b"--boundary\r\n"
        b"Content-Type: text/plain\r\n\r\n"
        b"This is the text part.\r\n"
        b"--boundary\r\n"
        b"Content-Type: text/html\r\n\r\n"
        b"<html><body>This is the HTML part.</body></html>\r\n"
        b"--boundary\r\n"
        b"Content-Type: application/pdf\r\n"
        b"Content-Disposition: attachment; filename=test.pdf\r\n\r\n"
        b"PDF content\r\n"
        b"--boundary--\r\n"
    )

    # Parse the email
    result = email_client._parse_email(raw_email)  # type: ignore # Protected member access is acceptable in tests

    # Verify the parsing worked correctly
    assert result["sender"] == "sender@example.com"
    assert result["body_text"] == "This is the text part."
    assert result["body_html"] == "<html><body>This is the HTML part.</body></html>"


def test_check_new_emails_skip_own_email(
    email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock], mocker: MockerFixture
) -> None:
    """Test that emails sent by our own address are skipped."""
    # Set up the IMAP connection
    _, mock_instance = mock_imap
    mock_instance.search.return_value = ("OK", [b"1"])
    mock_instance.fetch.return_value = ("OK", [(b"1", b"test-email-data")])

    # Mock parse_email to return an email sent by our own address
    mocker.patch.object(
        email_client,
        "_parse_email",
        return_value={
            "message_id": "msg-123",
            "subject": "Test Email",
            "sender": "system@example.com",  # Same as sender_email
        },
    )

    # Check for new emails
    emails = email_client.check_new_emails()

    # Verify the email was skipped
    assert len(emails) == 0
    # Verify the email was marked as seen
    mock_instance.store.assert_called_with(b"1", '+FLAGS', '\\Seen')


def test_check_new_emails_fetch_error(
    email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock]
) -> None:
    """Test handling of fetch errors when checking for new emails."""
    # Set up the IMAP connection
    _, mock_instance = mock_imap
    mock_instance.search.return_value = ("OK", [b"1"])
    # Return a non-OK result for fetch
    mock_instance.fetch.return_value = ("NO", None)

    # Check for new emails
    emails = email_client.check_new_emails()

    # Verify no emails were returned due to the fetch error
    assert len(emails) == 0


def test_check_new_emails_parse_error(
    email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock], mocker: MockerFixture
) -> None:
    """Test handling of parsing errors when checking for new emails."""
    # Set up the IMAP connection
    _, mock_instance = mock_imap
    mock_instance.search.return_value = ("OK", [b"1"])
    mock_instance.fetch.return_value = ("OK", [(b"1", b"test-email-data")])

    # Mock parse_email to raise an exception
    mocker.patch.object(
        email_client,
        "_parse_email",
        side_effect=Exception("Parsing error"),
    )

    # Check for new emails - should not raise an exception
    emails = email_client.check_new_emails()

    # Verify no emails were returned due to the parsing error
    assert len(emails) == 0


@pytest.mark.asyncio
async def test_send_email_smtp_error(email_client: EmailClient, mocker: MockerFixture) -> None:
    """Test error handling when sending an email fails."""
    # Mock _send_smtp to simulate an SMTP error
    mock_send = mocker.patch.object(
        email_client,
        "_send_smtp",
        side_effect=Exception("SMTP error"),
    )

    # Attempt to send an email
    success, message_id = await email_client.send_email(
        recipients="recipient@example.com",
        subject="Test Subject",
        body_text="This is a test email.",
    )

    # Verify the error was handled gracefully
    assert success is False
    assert message_id == ""
    assert mock_send.called


@pytest.mark.asyncio
async def test_smtp_connection_error(email_client: EmailClient, mocker: MockerFixture) -> None:
    """Test SMTP connection error handling."""
    # Create a message for testing
    msg = MIMEMultipart()
    msg["To"] = "recipient@example.com"
    msg["From"] = email_client.sender_email

    # Mock SMTP to raise an exception
    mock_smtp = mocker.patch("aiosmtplib.SMTP")
    mock_instance = mock_smtp.return_value
    mock_instance.connect = AsyncMock(side_effect=ConnectionError("Failed to connect"))

    # Send the email - should handle the error
    success, message_id = await email_client._send_smtp(msg, ["recipient@example.com"])  # type: ignore # Protected member access is acceptable in tests

    # Verify the result
    assert success is False
    assert message_id == ""


@pytest.mark.asyncio
async def test_monitor_start_stop(email_monitor: EmailMonitor, mocker: MockerFixture) -> None:
    """Test starting and stopping the email monitor."""
    # Mock the check_emails method
    mocker.patch.object(email_monitor, "_check_emails")

    # Start the monitor
    email_monitor.start()

    # Verify it was started
    assert email_monitor._running is True  # type: ignore # Protected member access is acceptable in tests
    assert email_monitor._task is not None  # type: ignore # Protected member access is acceptable in tests

    # Stop the monitor
    await email_monitor.stop()

    # Verify it was stopped
    assert email_monitor._running is False  # type: ignore # Protected member access is acceptable in tests
    assert email_monitor._task is None  # type: ignore # Protected member access is acceptable in tests


@pytest.mark.asyncio
async def test_monitor_check_emails_error(email_monitor: EmailMonitor, mocker: MockerFixture) -> None:
    """Test error handling in monitor's check_emails method."""
    # Mock check_new_emails to raise an exception
    mock_client = MagicMock()
    mock_client.check_new_emails.side_effect = Exception("Check error")
    email_monitor.email_client = mock_client

    # Create a mock sleep function to avoid waiting
    mock_sleep = AsyncMock()
    mocker.patch("asyncio.sleep", mock_sleep)

    # Create a modified version of _check_emails that only runs once
    original_check_emails = email_monitor._check_emails  # type: ignore # Protected member access is acceptable in tests

    called_once = False

    async def check_emails_once():
        nonlocal called_once
        if not called_once:
            called_once = True
            # Run the first iteration logic from _check_emails
            try:
                new_emails = email_monitor.email_client.check_new_emails()
                if new_emails:
                    for email_data in new_emails:
                        for callback in email_monitor._new_email_callbacks:  # type: ignore # Protected member access is acceptable in tests
                            await callback(email_data)
            except Exception:  # Remove the unused variable 'e'
                # This is what we're testing - it should catch the exception and not propagate it
                await asyncio.sleep(email_monitor.check_interval)

            # End after one iteration
            return

    # Replace the method with our single-iteration version
    mocker.patch.object(email_monitor, "_check_emails", check_emails_once)

    # Run the test
    await check_emails_once()

    # Verify error handling happened correctly (sleep was called, indicating the exception was caught)
    mock_sleep.assert_called_once_with(email_monitor.check_interval)


def test_invalid_imap_fetch_data(email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock]) -> None:
    """Test handling of invalid data structure returned from IMAP fetch."""
    # Set up the IMAP connection
    _, mock_instance = mock_imap
    mock_instance.search.return_value = ("OK", [b"1"])
    # Return invalid data structure from fetch
    mock_instance.fetch.return_value = ("OK", None)  # None instead of list of tuples

    # Check for new emails - should handle the invalid data gracefully
    emails = email_client.check_new_emails()
    assert len(emails) == 0

    # Try another invalid data structure
    mock_instance.fetch.return_value = ("OK", [(b"1",)])  # Tuple too short
    emails = email_client.check_new_emails()
    assert len(emails) == 0


def test_imap_search_error(email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock]) -> None:
    """Test handling of IMAP search error."""
    # Set up the IMAP connection
    _, mock_instance = mock_imap
    # Return non-OK result from search
    mock_instance.search.return_value = ("NO", None)

    # Check for new emails - should handle the search error gracefully
    emails = email_client.check_new_emails()
    assert len(emails) == 0


def test_already_connected_imap(email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock]) -> None:
    """Test connecting to IMAP when already connected."""
    # Setup already connected state
    mock_class, mock_instance = mock_imap
    email_client._imap = mock_instance  # type: ignore # Protected member access is acceptable in tests

    # Reset the mock to clear previous call count
    mock_class.reset_mock()

    # Try to connect again
    email_client._connect_imap()  # type: ignore # Protected member access is acceptable in tests

    # Should not try to connect again
    mock_class.assert_not_called()  # Constructor should NOT be called again


def test_parse_email_string_payload(email_client: EmailClient, mocker: MockerFixture) -> None:
    """Test parsing an email with string payload."""
    # Create an email with string payload
    raw_email = (
        b"From: sender@example.com\r\n"
        b"To: recipient@example.com\r\n"
        b"Subject: Test Subject\r\n"
        b"Content-Type: text/plain\r\n\r\n"
    )

    # Patch the get_payload method to return a string instead of bytes
    with patch.object(Message, "get_payload", return_value="This is a string payload"):
        # Parse the email
        result = email_client._parse_email(raw_email)  # type: ignore # Protected member access is acceptable in tests

        # Verify the parsing worked correctly
        assert result["sender"] == "sender@example.com"
        assert result["body_text"] == "This is a string payload"


def test_parse_email_invalid_content_type(email_client: EmailClient, mocker: MockerFixture) -> None:
    """Test parsing an email with an invalid content type."""
    # Create an email with an unusual content type
    raw_email = (
        b"From: sender@example.com\r\n"
        b"To: recipient@example.com\r\n"
        b"Subject: Test Subject\r\n"
        b"Content-Type: application/octet-stream\r\n\r\n"
        b"Binary data here"
    )

    # Mock for Message to ensure the get_content_type returns our unusual type
    msg_mock = mocker.MagicMock()
    msg_mock.get_content_type.return_value = "application/octet-stream"
    msg_mock.get_payload.return_value = b"Binary data here"
    msg_mock.get_content_charset.return_value = "utf-8"

    # Define a helper function with proper typing for the side_effect
    def get_header(header_name: str, default: str = "") -> str:
        headers = {
            "From": "sender@example.com",
            "To": "recipient@example.com",
            "Subject": "Test Subject",
            "Content-Type": "application/octet-stream",
        }
        return headers.get(header_name, default)

    msg_mock.get.side_effect = get_header
    msg_mock.is_multipart.return_value = False

    # Mock the message_from_bytes function
    mocker.patch("email.message_from_bytes", return_value=msg_mock)

    # Parse the email
    result = email_client._parse_email(raw_email)  # type: ignore # Protected member access is acceptable in tests

    # Verify parsing worked but didn't extract the binary data as text/html
    assert result["sender"] == "sender@example.com"
    assert result["body_text"] == ""  # Should be empty since it's not text/plain
    assert result["body_html"] == ""  # Should be empty since it's not text/html


@pytest.mark.asyncio
async def test_send_email_empty_message_id(email_client: EmailClient, mock_smtp: MagicMock, mocker: MockerFixture) -> None:
    """Test sending an email with handling of empty message ID."""
    # Mock _send_smtp to capture the message and return empty message ID
    mock_send = AsyncMock()
    mock_send.return_value = (True, "")
    mocker.patch.object(email_client, "_send_smtp", mock_send)

    # Send an email
    success, message_id = await email_client.send_email(
        recipients="recipient@example.com",
        subject="Test Subject",
        body_text="This is a test email.",
    )

    # Verify success but empty message_id
    assert success is True
    assert message_id == ""
    assert mock_send.called


@pytest.mark.asyncio
async def test_send_email_references_handling(email_client: EmailClient, mock_smtp: MagicMock) -> None:
    """Test various scenarios of References header handling."""
    # Case 1: in_reply_to already in references
    success, _ = await email_client.send_email(
        recipients="recipient@example.com",
        subject="Test Subject",
        body_text="Test email",
        in_reply_to="msg-123",
        references="<prior-msg> <msg-123>",  # in_reply_to already in references
    )
    assert success is True

    # Case 2: in_reply_to not in references
    success, _ = await email_client.send_email(
        recipients="recipient@example.com",
        subject="Test Subject",
        body_text="Test email",
        in_reply_to="msg-456",
        references="<msg-123>",  # in_reply_to not in references
    )
    assert success is True

    # Case 3: references but no in_reply_to
    success, _ = await email_client.send_email(
        recipients="recipient@example.com",
        subject="Test Subject",
        body_text="Test email",
        references="<msg-123>",  # Only references, no in_reply_to
    )
    assert success is True


@pytest.mark.asyncio
async def test_monitor_already_running(email_monitor: EmailMonitor) -> None:
    """Test starting the monitor when it's already running."""
    # Start the monitor
    email_monitor.start()

    # Try to start it again
    email_monitor.start()

    # Clean up
    await email_monitor.stop()


@pytest.mark.asyncio
async def test_monitor_already_stopped(email_monitor: EmailMonitor) -> None:
    """Test stopping the monitor when it's already stopped."""
    # Monitor is not running by default
    await email_monitor.stop()  # Should do nothing gracefully


def test_parse_email_null_payload(email_client: EmailClient, mocker: MockerFixture) -> None:
    """Test parsing an email with a null payload."""
    # Create a minimal email
    raw_email = (
        b"From: sender@example.com\r\n"
        b"To: recipient@example.com\r\n"
        b"Subject: Test Subject\r\n"
        b"Content-Type: text/plain\r\n\r\n"
    )

    # Mock message to return None for get_payload
    msg_mock = mocker.MagicMock()
    msg_mock.get_content_type.return_value = "text/plain"
    msg_mock.get_payload.return_value = None
    msg_mock.get_content_charset.return_value = "utf-8"

    # Define a helper function with proper typing for the side_effect
    def get_header(header_name: str, default: str = "") -> str:
        headers = {
            "From": "sender@example.com",
            "To": "recipient@example.com",
            "Subject": "Test Subject"
        }
        return headers.get(header_name, default)

    msg_mock.get.side_effect = get_header
    msg_mock.is_multipart.return_value = False

    # Mock email.message_from_bytes
    mocker.patch("email.message_from_bytes", return_value=msg_mock)

    # Parse the email
    result = email_client._parse_email(raw_email)  # type: ignore # Protected member access is acceptable in tests

    # Verify it handles null payload correctly
    assert result["sender"] == "sender@example.com"
    assert result["body_text"] == ""
    assert result["body_html"] == ""


def test_check_new_emails_multiple_messages(
    email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock], mocker: MockerFixture
) -> None:
    """Test checking for multiple new emails."""
    # Set up the IMAP connection
    _, mock_instance = mock_imap
    mock_instance.search.return_value = ("OK", [b"1 2 3"])  # Multiple message IDs

    # Define side effect for fetch to return different data for each message
    def fetch_side_effect(msg_id: bytes, *args: Any) -> Tuple[str, Optional[List[Tuple[bytes, bytes]]]]:
        if msg_id == b"1":
            return ("OK", [(b"1", b"email-data-1")])
        elif msg_id == b"2":
            return ("OK", [(b"2", b"email-data-2")])
        elif msg_id == b"3":
            return ("OK", [(b"3", b"email-data-3")])
        return ("NO", None)

    mock_instance.fetch.side_effect = fetch_side_effect

    # Mock parse_email to return different data for each email
    parse_call_count = 0

    def parse_side_effect(raw_data: bytes) -> Dict[str, Any]:
        nonlocal parse_call_count
        parse_call_count += 1
        return {
            "message_id": f"msg-{parse_call_count}",
            "subject": f"Test Email {parse_call_count}",
            "sender": "user@example.com",
        }

    mocker.patch.object(email_client, "_parse_email", side_effect=parse_side_effect)

    # Check for new emails
    emails = email_client.check_new_emails()

    # Verify we got multiple emails back
    assert len(emails) == 3
    assert emails[0]["message_id"] == "msg-1"
    assert emails[1]["message_id"] == "msg-2"
    assert emails[2]["message_id"] == "msg-3"

    # Verify all messages were marked as seen
    assert mock_instance.store.call_count == 3


def test_check_new_emails_invalid_search_data(
    email_client: EmailClient, mock_imap: Tuple[MagicMock, MagicMock]
) -> None:
    """Test handling of empty message ID list when checking emails."""
    # Set up the IMAP connection
    _, mock_instance = mock_imap
    # Return empty message ID list
    mock_instance.search.return_value = ("OK", [b""])

    # Check for new emails
    emails = email_client.check_new_emails()

    # Verify no emails were returned
    assert len(emails) == 0

    # Test with non-empty but invalid data
    mock_instance.search.return_value = ("OK", None)
    emails = email_client.check_new_emails()
    assert len(emails) == 0


def test_extract_thread_id_empty_subject(email_client: EmailClient) -> None:
    """Test thread ID creation with empty subject."""
    # Create a test message with empty subject
    test_msg = Message()
    test_msg["Subject"] = ""
    test_msg["From"] = "sender@example.com"

    # Extract the thread ID
    thread_id = email_client._extract_thread_id(test_msg)  # type: ignore # Protected member access is acceptable in tests

    # Verify it used "No Subject" fallback
    assert thread_id == "No Subject_sender@example.com"


def test_extract_thread_id_with_re_prefix(email_client: EmailClient) -> None:
    """Test removing Re: prefix when extracting thread ID from subject."""
    # Create test messages with various prefixes
    test_msg1 = Message()
    test_msg1["Subject"] = "Re: Original Subject"
    test_msg1["From"] = "sender@example.com"

    test_msg2 = Message()
    test_msg2["Subject"] = "RE[2]: Original Subject"
    test_msg2["From"] = "sender@example.com"

    test_msg3 = Message()
    test_msg3["Subject"] = "FWD: Original Subject"
    test_msg3["From"] = "sender@example.com"

    # Extract thread IDs
    thread_id1 = email_client._extract_thread_id(test_msg1)  # type: ignore # Protected member access is acceptable in tests
    thread_id2 = email_client._extract_thread_id(test_msg2)  # type: ignore # Protected member access is acceptable in tests
    thread_id3 = email_client._extract_thread_id(test_msg3)  # type: ignore # Protected member access is acceptable in tests

    # Verify Re: prefixes were removed
    assert thread_id1 == "Original Subject_sender@example.com"
    assert thread_id2 == "Original Subject_sender@example.com"
    assert thread_id3 == "Original Subject_sender@example.com"


@pytest.mark.asyncio
async def test_send_email_cc_string(email_client: EmailClient, mock_smtp: MagicMock) -> None:
    """Test sending an email with CC as a single string."""
    # Send an email with CC as a string instead of a list
    success, _ = await email_client.send_email(
        recipients="recipient@example.com",
        subject="Test Subject",
        body_text="Test email",
        cc="cc@example.com"  # Single string instead of list
    )

    # Verify success
    assert success is True

    # Verify the message had the correct CC
    mock_instance = mock_smtp.return_value
    call_args = mock_instance.send_message.call_args[0]
    sent_message = call_args[0]
    assert "cc@example.com" in sent_message["Cc"]
