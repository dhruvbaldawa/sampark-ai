import asyncio
import email
import imaplib
import logging
import re
import time
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, parseaddr
from typing import Any, Dict, List, Optional, Tuple, Union

import aiosmtplib
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class EmailClient:
    """
    Client to handle IMAP and SMTP connections for receiving and sending emails.
    """

    def __init__(
        self,
        imap_server: str,
        imap_port: int,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        mailbox: str = "INBOX",
    ) -> None:
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self._imap: Optional[imaplib.IMAP4_SSL] = None

    def _connect_imap(self) -> None:
        """Connect to the IMAP server and select the mailbox."""
        if self._imap is not None and self._imap.state != "LOGOUT":
            return

        try:
            self._imap = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self._imap.login(self.username, self.password)
            self._imap.select(self.mailbox)
            logger.info("Connected to IMAP server %s", self.imap_server)
        except Exception as e:
            logger.error("Failed to connect to IMAP server: %s", str(e))
            raise

    def _disconnect_imap(self) -> None:
        """Disconnect from the IMAP server."""
        if self._imap is not None:
            try:
                if self._imap.state != "LOGOUT":
                    self._imap.close()
                    self._imap.logout()
                    logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.error("Error during IMAP disconnect: %s", str(e))
            finally:
                self._imap = None

    def _parse_email(self, raw_email: bytes) -> Dict[str, Any]:
        """
        Parse raw email data into a structured dictionary.

        Args:
            raw_email: Raw email data from IMAP server

        Returns:
            Dictionary containing parsed email fields
        """
        try:
            msg = email.message_from_bytes(raw_email)

            # Extract basic headers
            email_data = {
                "message_id": msg.get("Message-ID", "").strip("<>"),
                "in_reply_to": msg.get("In-Reply-To", "").strip("<>"),
                "references": msg.get("References", ""),
                "subject": msg.get("Subject", ""),
                "date": msg.get("Date", ""),
                "sender": parseaddr(msg.get("From", ""))[1],
                "recipients": [parseaddr(to)[1] for to in msg.get("To", "").split(",") if to],
                "cc": [parseaddr(cc)[1] for cc in msg.get("Cc", "").split(",") if cc],
            }

            # Extract thread ID from References or generate from subject
            email_data["thread_id"] = self._extract_thread_id(msg)

            # Extract body
            email_data["body_text"] = ""
            email_data["body_html"] = ""

            # Find the body parts - simplified approach
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))

                    # Skip attachments
                    if "attachment" in content_disposition:
                        continue

                    payload = part.get_payload(decode=True)
                    if payload is None:
                        continue

                    try:
                        charset = part.get_content_charset("utf-8")
                        decoded_payload = payload.decode(charset)
                    except UnicodeDecodeError:
                        # Fallback to latin-1 if UTF-8 fails
                        decoded_payload = payload.decode("latin-1")

                    if content_type == "text/plain":
                        email_data["body_text"] = decoded_payload
                    elif content_type == "text/html":
                        email_data["body_html"] = decoded_payload
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    try:
                        charset = msg.get_content_charset("utf-8")
                        decoded_payload = payload.decode(charset)
                    except UnicodeDecodeError:
                        # Fallback to latin-1 if UTF-8 fails
                        decoded_payload = payload.decode("latin-1")

                    if msg.get_content_type() == "text/plain":
                        email_data["body_text"] = decoded_payload
                    elif msg.get_content_type() == "text/html":
                        email_data["body_html"] = decoded_payload

            return email_data
        except Exception as e:
            logger.error("Error parsing email: %s", str(e))
            raise

    def _extract_thread_id(self, msg: Message) -> str:
        """
        Extract a thread ID from an email message.

        Args:
            msg: Email message

        Returns:
            Thread ID string
        """
        # First check References header for thread ID
        references = msg.get("References", "")
        if references:
            # Use the first message ID in references as thread ID
            message_ids = re.findall(r'<([^<>]+)>', references)
            if message_ids:
                return message_ids[0]

        # If no References, try In-Reply-To
        in_reply_to = msg.get("In-Reply-To", "")
        if in_reply_to:
            message_id = re.search(r'<([^<>]+)>', in_reply_to)
            if message_id:
                return message_id.group(1)

        # If no References or In-Reply-To, use subject + sender as thread ID
        subject = msg.get("Subject", "")
        # Remove any Re: or Fwd: prefixes from subject for thread ID consistency
        clean_subject = re.sub(r'(?i)^(re|fwd)(\[\d+\])?:\s*', '', subject)
        if not clean_subject:
            clean_subject = "No Subject"

        # Create a thread ID from cleaned subject and sender
        from_addr = parseaddr(msg.get("From", ""))[1]
        return f"{clean_subject}_{from_addr}"

    def check_new_emails(self) -> List[Dict[str, Any]]:
        """
        Check for new unseen emails in the mailbox.

        Returns:
            List of parsed email messages
        """
        try:
            self._connect_imap()

            # Search for all unseen emails
            result, message_ids = self._imap.search(None, "UNSEEN")
            if result != "OK":
                logger.error("Failed to search for unseen emails")
                return []

            message_id_list = message_ids[0].split()
            if not message_id_list:
                return []

            emails = []
            for message_id in message_id_list:
                result, data = self._imap.fetch(message_id, "(RFC822)")
                if result != "OK":
                    logger.error("Failed to fetch email with ID %s", message_id)
                    continue

                raw_email = data[0][1]
                email_data = self._parse_email(raw_email)
                emails.append(email_data)

            return emails
        except Exception as e:
            logger.error("Error checking for new emails: %s", str(e))
            return []
        finally:
            self._disconnect_imap()

    async def send_email(
        self,
        recipients: Union[str, List[str]],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc: Optional[Union[str, List[str]]] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Send an email via SMTP.

        Args:
            recipients: Email recipient(s)
            subject: Email subject
            body_text: Plain text email body
            body_html: HTML email body (optional)
            cc: Carbon copy recipient(s) (optional)
            in_reply_to: Message ID this email is replying to (optional)
            references: Thread message ID references (optional)

        Returns:
            Tuple of (success, message_id)
        """
        # Create a multipart message
        msg = MIMEMultipart("alternative")

        # Add recipients
        if isinstance(recipients, str):
            recipients = [recipients]
        msg["To"] = ", ".join(recipients)

        # Add CC if provided
        if cc:
            if isinstance(cc, str):
                cc = [cc]
            msg["Cc"] = ", ".join(cc)
        else:
            cc = []

        msg["From"] = self.username
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)

        # Generate a message ID
        msg_id = make_msgid(domain=self.username.split("@")[1])
        msg["Message-ID"] = msg_id

        # Add In-Reply-To and References headers for threading
        if in_reply_to:
            msg["In-Reply-To"] = f"<{in_reply_to}>"

            # Update References with in_reply_to if not already in references
            if references:
                if in_reply_to not in references:
                    msg["References"] = f"{references} <{in_reply_to}>"
                else:
                    msg["References"] = references
            else:
                msg["References"] = f"<{in_reply_to}>"
        elif references:
            msg["References"] = references

        # Add text part
        msg.attach(MIMEText(body_text, "plain"))

        # Add HTML part if provided
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        # Send the email
        try:
            return await self._send_smtp(msg, recipients + cc)
        except Exception as e:
            logger.error("Failed to send email: %s", str(e))
            return False, ""

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
    )
    async def _send_smtp(self, msg: MIMEMultipart, recipients: List[str]) -> Tuple[bool, str]:
        """
        Send an email using SMTP with retry logic.

        Args:
            msg: Email message to send
            recipients: List of recipients

        Returns:
            Tuple of (success, message_id)
        """
        client = aiosmtplib.SMTP(hostname=self.smtp_server, port=self.smtp_port, use_tls=True)

        try:
            await client.connect()
            await client.login(self.username, self.password)
            await client.send_message(msg, self.username, recipients)
            message_id = msg["Message-ID"].strip("<>")
            return True, message_id
        except Exception as e:
            logger.error("SMTP error: %s", str(e))
            raise
        finally:
            try:
                await client.quit()
            except Exception:
                pass


class EmailMonitor:
    """
    Monitors an email inbox for new messages and processes them.
    """

    def __init__(
        self,
        email_client: EmailClient,
        check_interval: int = 60,
    ) -> None:
        self.email_client = email_client
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._new_email_callbacks: List[callable] = []

    def register_callback(self, callback: callable) -> None:
        """
        Register a callback function to be called when new emails are received.

        Args:
            callback: Function to call with the new email data
        """
        self._new_email_callbacks.append(callback)

    async def _check_emails(self) -> None:
        """Check for new emails and process them."""
        while self._running:
            try:
                new_emails = self.email_client.check_new_emails()
                if new_emails:
                    logger.info("Found %d new emails", len(new_emails))
                    for email_data in new_emails:
                        for callback in self._new_email_callbacks:
                            await callback(email_data)

                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error("Error in email monitoring: %s", str(e))
                # Sleep before retrying to avoid rapid retries on persistent errors
                await asyncio.sleep(self.check_interval)

    def start(self) -> None:
        """Start the email monitoring process."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._check_emails())
        logger.info("Email monitoring started")

    async def stop(self) -> None:
        """Stop the email monitoring process."""
        if not self._running:
            return

        self._running = False
        if self._task:
            await asyncio.wait_for(self._task, timeout=None)
            self._task = None

        logger.info("Email monitoring stopped")
