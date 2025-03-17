# Sampark-AI

An intelligent LLM-powered agent that receives tasks via email, processes them autonomously, and maintains communication through the original email thread.

## Project Documentation

- [High-Level Overview](docs/high_level_overview.md)
- [Technical Design](docs/technical_design.md)
- [Milestones](docs/milestones.md)

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

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/sampark-ai.git
cd sampark-ai
```

2. Install Poetry (if not already installed):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

3. Install dependencies:
```bash
poetry install
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Start MongoDB (using Docker):
```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

6. Run development server:
```bash
poetry run uvicorn backend.sampark.api.main:app --reload
```

## Development

- Run tests: `poetry run pytest`
- Format code: `poetry run ruff format .`
- Check typing: `poetry run pyright`
- Run linter: `poetry run ruff check backend/`

## Project Structure

```
sampark-ai/
├── docs/                       # Documentation folder
│   ├── high_level_overview.md  # High-level project description
│   ├── technical_design.md     # Technical architecture and best practices
│   └── milestones.md           # Project milestones
├── backend/                    # Source code
│   ├── sampark/                # Main package
│   │   ├── email_service/      # Email monitoring and communication
│   │   │   ├── client.py
│   │   │   ├── client_test.py  # Unit test next to source file
│   │   │   └── ...
│   │   ├── task_processor/     # Task understanding and extraction
│   │   ├── planning/           # LLM-based planning system
│   │   ├── execution/          # Step execution engine
│   │   ├── database/           # NoSQL database interactions
│   │   ├── api/                # FastAPI web endpoints
│   │   └── utils/              # Shared utilities
│   ├── tests/
│   │   └── e2e/                # End-to-end tests
├── pyproject.toml              # Poetry configuration
└── README.md                   # Project overview
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
