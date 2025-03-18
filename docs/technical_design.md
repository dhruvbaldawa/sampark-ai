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

2. **Task Processing Pipeline**
   - Pydantic AI integration for NLU
   - Task classification system
   - Context extraction engine
   - Intent recognition system

3. **Planning System**
   - Pydantic AI-powered plan generation
   - Plan validation mechanism
   - Step sequencing algorithm
   - Dependency management

4. **Execution Engine**
   - Step executor framework
   - Progress tracking system
   - Error handling and recovery
   - Resource management

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
│   │   ├── workflows/          # Agents and workflow implementations for planning and execution cycle
│   │   ├── tools/              # Tools required for the agent to accomplish tasks
│   │   ├── db/                 # NoSQL database interactions
│   │   ├── api/                # FastAPI web endpoints
│   │   └── utils/              # Shared utilities
│   ├── tests/
│   │   └── e2e/                # End-to-end tests
├── pyproject.toml              # Poetry configuration
└── README.md                   # Project overview
```

## Data Flow
1. Input received via any communication channel → Appropriate Communication Adapter processes and normalizes the content
2. Communication adapter publishes an event with the normalized content
3. Task Understanding subscribes to new content events → Extracts requirements and constraints
4. Planning System creates execution roadmap with discrete steps
5. Database stores the plan and initializes tracking
6. Execution Engine processes each step sequentially, publishing progress events
7. Communication Manager subscribes to progress events and sends updates through the original communication channel
8. Database continuously updates with execution progress
9. Upon completion, final response event triggers Communication Manager to send response through original channel

## Database Schema Design
- **Conversations Table**: Stores conversation metadata and relationships across channels
- **Messages Table**: Individual messages with content and metadata
- **Tasks Table**: Extracted tasks with requirements and context
- **Plans Table**: Generated step-by-step plans
- **Executions Table**: Execution status and results for each step
- **Metrics Table**: Performance and operational metrics

## Integration Points
- Communication Adapters (Email, Chat, API)
- Event System (Internal pub/sub)
- Pydantic AI / LLM Provider API
- External APIs for task execution
- SQLite Database
- Monitoring and Alerting Systems

## Testing Strategy
- **Unit Tests**: Located next to source files with naming pattern `file_test.py`
- **Integration Tests**: In dedicated directory testing component interactions
- **End-to-End Tests**: Complete workflow tests in dedicated directory
- All components must maintain 80%+ test coverage

## Best Practices

### Python-Specific Practices
- Type hints for all functions and classes
- Dataclasses and Pydantic models for data validation
- Async/await for I/O-bound operations
- Context managers for resource management
- Exception handling with specific exception types

### Communication-Agnostic Workflow Design
- Workflows must never directly interact with communication channels
- All user interactions must go through the event system
- Communication details should be encapsulated in adapter modules
- Adapters are responsible for translating between domain events and channel-specific formats
- Event payloads should contain all necessary context but remain transport-agnostic
- Use callback interfaces rather than direct method calls for inter-component communication

### Software Design Principles
- **SOLID Principles**
  - Single Responsibility: Each component has one reason to change
  - Open/Closed: Open for extension, closed for modification
  - Liskov Substitution: Subtypes must be substitutable for base types
  - Interface Segregation: Clients shouldn't depend on unused interfaces
  - Dependency Inversion: Depend on abstractions, not implementations

- **Clean Architecture**
  - Clear separation of concerns
  - Domain-driven design
  - Use of interfaces for decoupling
  - Inversion of control

### Development Practices
- Test-Driven Development with pytest
- Continuous Integration/Continuous Deployment
- Code Reviews
- Version Control Best Practices

### Error Handling
- Graceful failure modes
- Comprehensive logging with structlog
- Retry mechanisms with exponential backoff
- Circuit breakers for external dependencies

### Security Considerations
- Email content encryption
- Secure API key management
- Input validation and sanitization
- Rate limiting
- Access control

### Scalability Approach
- Horizontal scaling of execution engine
- Stateless processing where possible
- Message queue for managing execution load
- Database sharding for large volumes

### Monitoring and Maintenance
- Health check endpoints
- Performance metrics dashboards
- Error rate tracking
- Response time monitoring
- Resource usage alerts
