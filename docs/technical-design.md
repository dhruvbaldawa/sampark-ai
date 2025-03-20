# Technical Design: Sampark-AI

## Architecture Overview

### Technology Stack
- **Programming Language**: Python 3.12+
- **Dependency Management**: Poetry
- **AI Integration**: Pydantic AI
- **Database**: SQLite with SQLAlchemy ORM
- **Web Framework**: FastAPI
- **Email Handling**: High-level Python email package

### System Components
1. **Email Service Adapter**
   - Handles IMAP/SMTP connections
   - Implements email threading logic
   - Manages attachments and multipart messages
   - Provides email metadata extraction

2. **Task Understanding Module**
   - Pydantic AI integration for NLU
   - Task classification system
   - Context extraction engine
   - Intent recognition system

3. **Workflow Engine**
   - Orchestrates the entire process flow
   - Implements state machine for task progression
   - Coordinates tool usage based on task requirements
   - Handles transitions between workflow states
   - Manages error recovery and retry mechanisms

4. **Tools Framework**
   - Pluggable architecture for extensibility
   - Standard interface for all tools
   - Authentication handlers for external services
   - Result normalization and validation

5. **Event-Driven Communication System**
   - Publisher-subscriber architecture
   - Channel-based messaging
   - Communication adapters (Email, Chat, API)
   - Event routing and filtering

6. **Database Layer**
   - SQLite file-based persistence
   - SQLAlchemy ORM for data access
   - Schema migrations with Alembic
   - Historical data management
   - Performance metrics collection

7. **API Layer**
   - FastAPI endpoints for monitoring
   - Swagger documentation
   - Authentication middleware
   - Rate limiting implementation

8. **Communication Manager**
   - Response template system
   - Context-aware reply generation
   - Status update formatting
   - Natural language generation

## Project Structure

```
sampark-ai/
├── docs/                       # Documentation folder
│   ├── high_level_overview.md  # High-level project description
│   ├── technical_design.md     # Technical architecture and best practices
│   └── milestones.md           # Project milestones
├── backend/                    # Source code
│   ├── sampark/                # Main package
│   │   ├── adapters/           # Communication adapters
│   │   │   ├── email/          # Email adapter
│   │   │   │   ├── client.py
│   │   │   │   ├── client_test.py
│   │   │   │   └── ...
│   │   │   ├── chat/           # Chat adapter
│   │   │   ├── api/            # API adapter
│   │   │   └── events/         # Event system
│   │   ├── workflows/          # Workflow engine and state management
│   │   ├── tools/              # Tools required for the agent to accomplish tasks
│   │   │   ├── base.py         # Base tool interface
│   │   │   ├── web_search.py   # Web search capabilities
│   │   │   ├── calculator.py   # Calculation capabilities
│   │   │   └── ...             # Other tool implementations
│   │   ├── db/                 # Database interactions
│   │   │   ├── models.py       # SQLAlchemy models
│   │   │   ├── session.py      # Database session management
│   │   │   └── migrations/     # Alembic migrations
│   │   ├── api/                # FastAPI web endpoints
│   │   └── utils/              # Shared utilities
│   ├── tests/
│   │   ├── unit/               # Unit tests
│   │   ├── integration/        # Integration tests
│   │   └── e2e/                # End-to-end tests
├── pyproject.toml              # Poetry configuration
└── README.md                   # Project overview
```

## Data Flow
1. Input received via any communication channel → Appropriate Communication Adapter processes and normalizes the content
2. Communication adapter publishes an event with the normalized content
3. Task Understanding subscribes to new content events → Extracts requirements and objectives
4. Workflow Engine initializes appropriate workflow based on task classification
5. Database stores the workflow state and initializes tracking
6. Workflow Engine orchestrates the process, utilizing tools as needed and transitioning through states
7. Communication Manager subscribes to workflow state events and sends updates through the original communication channel
8. Database continuously updates with workflow state changes
9. Upon completion, final response event triggers Communication Manager to send response through original channel

## Integration Points
- Communication Adapters (Email, Chat, API)
- Event System (Internal pub/sub)
- Pydantic AI / LLM Provider API
- External APIs via tools framework
- SQLite Database
- Monitoring and Alerting Systems
