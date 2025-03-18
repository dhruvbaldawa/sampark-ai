# Sampark-AI

An intelligent LLM-powered agent system that receives tasks via email, processes them autonomously, and maintains communication through the original email thread.

## Project Overview

Sampark-AI acts as an AI-powered assistant that:
1. Monitors an email inbox for incoming tasks
2. Acknowledges receipt of tasks by replying to the email thread
3. Uses LLM capabilities to understand the task requirements
4. Creates a structured plan to complete the task
5. Executes the plan methodically
6. Communicates progress and results through the same email thread

For more detailed information about the project:
- [High-level Overview](docs/high_level_overview.md)
- [Technical Design](docs/technical_design.md)
- [Project Milestones](docs/milestones.md)

## Setup Instructions

### Prerequisites

- Python 3.12+
- Poetry for dependency management

### Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd sampark-ai
   ```

2. Install dependencies using Poetry:
   ```bash
   poetry install
   ```

3. Create a `.env` file based on the provided example:
   ```bash
   cp .env.example .env
   ```

4. Update the `.env` file with your email credentials and settings:
   ```
   IMAP_SERVER=your-imap-server.com
   IMAP_PORT=993
   SMTP_SERVER=your-smtp-server.com
   SMTP_PORT=587
   EMAIL_USERNAME=your-email@example.com
   EMAIL_PASSWORD=your-email-password
   CHECK_INTERVAL_SECONDS=60
   ```

### Running the Application

To start the application, run:

```bash
poetry run python -m backend.sampark
```

The application will:
1. Initialize the SQLite database
2. Connect to the specified email account
3. Start monitoring for new emails
4. Process incoming emails and reply to them

## Development

### Project Structure

```
sampark-ai/
├── docs/                      # Documentation
├── backend/                   # Source code
│   └── sampark/
│       ├── adapters/          # Communication adapters
│       │   └── email/         # Email adapter
│       ├── db/                # Database models and configuration
│       └── utils/             # Utility functions
├── pyproject.toml             # Poetry configuration
└── README.md                  # Project overview
```

### Running Tests

To run tests:

```bash
poetry run pytest
```

## Contributing

1. Follow PEP 8 style guidelines
2. Use type hints throughout the codebase
3. Place unit tests next to source files with naming convention `file_test.py`
4. Maintain documentation as the project evolves

## Features

- Email monitoring and task extraction
- LLM-powered task understanding with Pydantic AI
- Automatic planning and step breakdown
- Methodical task execution with progress tracking
- Email-based communication throughout task lifecycle
- Complete persistence of all activity in MongoDB
- FastAPI dashboard for monitoring and management

## Technology Stack

- Python 3.12+
- Poetry for dependency management
- Pydantic AI for LLM interactions
- MongoDB for data persistence
- FastAPI for web interface
- Email monitoring and communication libraries

## License

This project is licensed under the MIT License - see the LICENSE file for details.
