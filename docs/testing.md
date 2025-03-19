# Testing Environment Setup

This document outlines how to set up a testing environment for Sampark-AI, including a local IMAP server for email testing.

## Local IMAP Server Setup with Greenmail

[Greenmail](https://greenmail-mail-test.github.io/greenmail/) is a lightweight, in-memory email server implementation that's perfect for testing applications that interact with email servers.

### Prerequisites

- Java Runtime Environment (JRE) 8 or newer
- Docker (alternative method)

### Method 1: Using Docker

1. Pull the Greenmail Docker image:
   ```bash
   docker pull greenmail/standalone:latest
   ```

2. Run the Greenmail container:
   ```bash
   docker run -d --name greenmail \
     -p 3025:3025 -p 3110:3110 -p 3143:3143 \
     -p 3465:3465 -p 3993:3993 -p 3995:3995 \
     greenmail/standalone:latest
   ```

   This will start Greenmail with the following services:
   - SMTP: Port 3025
   - POP3: Port 3110
   - IMAP: Port 3143
   - SMTPS: Port 3465
   - IMAPS: Port 3993
   - POP3S: Port 3995

### Method 2: Using JAR File

1. Download the latest Greenmail standalone JAR from the [Greenmail download page](https://greenmail-mail-test.github.io/greenmail/#download).

2. Run Greenmail:
   ```bash
   java -Dgreenmail.setup.test.all -Dgreenmail.users=test:password@localhost -jar greenmail-standalone-2.1.3.jar
   ```

   This command starts Greenmail with all services and creates a test user with username "test" and password "password".

## Default Credentials

Greenmail automatically accepts any username/password combination by default. For testing you can use:

- Username: `test@localhost`
- Password: `password`

You can also configure specific users as shown in the command above.

## Testing with the IMAP Server

### Environment configuration for Sampark-AI

Update your `.env` file with the following settings for local testing:

```
IMAP_SERVER=localhost
IMAP_PORT=3993
EMAIL_USERNAME=test
EMAIL_PASSWORD=password
SMTP_SERVER=localhost
SMTP_PORT=3025
```

### Sending Test Emails

#### Method 1: Using Command Line (with swaks)

[Swaks](https://github.com/jetmore/swaks) (Swiss Army Knife for SMTP) is a versatile command-line tool for testing SMTP.

1. Install swaks:
   ```bash
   # On Ubuntu/Debian
   sudo apt-get install swaks

   # On macOS with Homebrew
   brew install swaks
   ```

2. Send a test email:
   ```bash
   swaks --to test@localhost --from sender@example.com \
     --server localhost:3025 \
     --header "Subject: Test Email" \
     --body "This is a test email for Sampark-AI."
   ```

#### Method 2: Using Python

You can also use Python to send test emails to your local SMTP server:

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Email details
sender = "sender@example.com"
recipient = "test@localhost"
subject = "Test Email from Python"
body = "This is a test email for Sampark-AI sent from Python."

# Create message
message = MIMEMultipart()
message["From"] = sender
message["To"] = recipient
message["Subject"] = subject
message.attach(MIMEText(body, "plain"))

# Send email
with smtplib.SMTP("localhost", 3025) as server:
    server.sendmail(sender, recipient, message.as_string())
    print("Test email sent successfully!")
```

### Verifying Emails with IMAP Client

You can verify received emails using a Python IMAP client:

```python
import imaplib
import email

# Connect to IMAP server
mail = imaplib.IMAP4("localhost", 3143)
mail.login("test@localhost", "password")
mail.select("inbox")

# Search for all emails
status, data = mail.search(None, "ALL")
mail_ids = data[0].split()

# Fetch the latest email
if mail_ids:
    latest_email_id = mail_ids[-1]
    status, data = mail.fetch(latest_email_id, "(RFC822)")
    raw_email = data[0][1]

    # Parse email content
    msg = email.message_from_bytes(raw_email)
    print(f"From: {msg['From']}")
    print(f"Subject: {msg['Subject']}")

    # Print email body
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                print(part.get_payload(decode=True).decode())
    else:
        print(msg.get_payload(decode=True).decode())

mail.close()
mail.logout()
```

## Integration with Sampark-AI Tests

Configure your test cases to use these local server settings when running automated tests. This ensures that your tests don't depend on external email services and can run reliably in any environment.

For more information about Greenmail configuration options, refer to the [official documentation](https://greenmail-mail-test.github.io/greenmail/).
