import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from sampark.adapters.email.client import EmailClient, EmailMonitor, EmailDataDict
from sampark.adapters.email.service import EmailService
from sampark.db.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def process_email_callback(email_service: EmailService, email_data: EmailDataDict) -> None:
    """
    Callback function to process new emails.

    Args:
        email_service: Email service instance
        email_data: Data for a new email
    """
    logger.info(f"Processing new email: {email_data['subject']} from {email_data['sender']}")
    message = await email_service.process_new_email(email_data)

    if message:
        # Send an automated reply
        logger.info(f"Sending acknowledgment reply to {message.message_id}")

        reply_text = (
            f"Hello {email_data['sender']},\n\n"
            f"Thank you for your email. I've received your message and will process it soon.\n\n"
            f"Best regards,\nSampark-AI"
        )

        reply_html = (
            f"<p>Hello {email_data['sender']},</p>"
            f"<p>Thank you for your email. I've received your message and will process it soon.</p>"
            f"<p>Best regards,<br>Sampark-AI</p>"
        )

        success, _ = await email_service.reply_to_email(
            message_id=message.message_id,
            body_text=reply_text,
            body_html=reply_html,
        )

        if success:
            logger.info("Sent acknowledgment reply successfully")
        else:
            logger.error("Failed to send acknowledgment reply")
    else:
        logger.error("Failed to process email")


async def main() -> None:
    """Main application entry point."""
    try:
        # Load environment variables
        load_dotenv()

        # Check for required environment variables
        required_env_vars = [
            "IMAP_SERVER",
            "IMAP_PORT",
            "SMTP_SERVER",
            "SMTP_PORT",
            "EMAIL_USERNAME",
            "EMAIL_PASSWORD",
            "DB_PATH",
        ]

        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            logger.error("Please set these variables in a .env file or in the environment")
            return

        # Initialize the database
        logger.info("Initializing database...")
        await init_db()

        # Create email client
        email_client = EmailClient(
            imap_server=os.getenv("IMAP_SERVER", ""),
            imap_port=int(os.getenv("IMAP_PORT", "993")),
            smtp_server=os.getenv("SMTP_SERVER", ""),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            username=os.getenv("EMAIL_USERNAME", ""),
            password=os.getenv("EMAIL_PASSWORD", ""),
        )

        # Create email service
        email_service = EmailService(email_client=email_client)

        # Create and configure email monitor
        check_interval = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
        email_monitor = EmailMonitor(email_client=email_client, check_interval=check_interval)

        # Register callback to process new emails
        async def callback_wrapper(email_data: EmailDataDict) -> None:
            await process_email_callback(email_service, email_data)

        email_monitor.register_callback(callback_wrapper)

        # Start monitoring for emails
        logger.info(f"Starting email monitoring (checking every {check_interval} seconds)...")
        email_monitor.start()

        # Keep the application running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            # Stop the email monitor
            await email_monitor.stop()

    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        raise


if __name__ == "__main__":
    # Run the main application
    asyncio.run(main())
