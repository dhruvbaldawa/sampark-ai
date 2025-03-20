# Milestone 2: Task Understanding with Pydantic AI

## Overview
Milestone 2 focuses on implementing task understanding capabilities using Pydantic AI. This milestone will enable the system to extract structured information from incoming emails and trigger appropriate workflows with unique codenames. Each workflow will maintain its own internal state as it progresses and can be interacted with through multiple channels.

## Objectives
- Integrate Pydantic AI for natural language understanding
- Extract contextual information from email content
- Determine appropriate workflow type based on email content
- Design workflow state management system
- Create decoupled workflow runs independent of communication channels
- Acknowledge emails with basic understanding

## Implementation Plan

### 1. Pydantic AI Integration (Day 1, Morning)
- [ ] Set up Pydantic AI client with proper environment variables
- [ ] Create a service wrapper for Pydantic AI interactions
- [ ] Implement error handling and retry logic for AI requests
- [ ] Add unit tests for the Pydantic AI service

### 2. Workflow Models & Architecture (Day 1, Afternoon)
- [ ] Design workflow codename system (using colors, galaxies, or A-Z theme)
- [ ] Define Pydantic models for workflow runs and states
- [ ] Create workflow state machine architecture
- [ ] Implement SQLAlchemy models for workflow runs
- [ ] Design communication-agnostic association pattern
- [ ] Create database migrations for new tables
- [ ] Write unit tests for workflow models

### 3. Email Content Parsing (Day 2, Morning)
- [ ] Develop prompt engineering for workflow determination
- [ ] Implement parsing logic for different email formats
- [ ] Create preprocessing pipeline for email content
- [ ] Handle attachments and references in email content
- [ ] Add unit tests for content parsing

### 4. Workflow Type Selection (Day 2, Afternoon)
- [ ] Implement workflow selection logic
- [ ] Create taxonomy of supported workflow types
- [ ] Develop initial workflow state generation
- [ ] Implement workflow status management
- [ ] Add confidence scoring for workflow selection
- [ ] Write tests for workflow selection functionality

### 5. Integration & Response Generation (Day 2, Late Afternoon)
- [ ] Connect workflow system to email adapter via communication association
- [ ] Implement basic acknowledgment email generation
- [ ] Create database storage flow for workflow runs
- [ ] Add end-to-end tests for the complete flow
- [ ] Document the workflow system components

## Technical Components

### Pydantic Models
```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union, Generic, TypeVar
from datetime import datetime
from enum import Enum

class WorkflowCodename(str, Enum):
    # Example codenames using colors
    AMBER = "amber"
    BLUE = "blue"
    CRIMSON = "crimson"
    DELTA = "delta"
    EMERALD = "emerald"
    # Add more as needed

class WorkflowStatus(str, Enum):
    RUNNING = "running"
    AWAITING_FEEDBACK = "awaiting_feedback"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# State type variable for generic workflow states
T = TypeVar('T')

# Base workflow state with common fields
class BaseWorkflowState(BaseModel, Generic[T]):
    """Base state with fields common to all workflows"""
    current_step: str
    step_history: List[str] = []
    conversation_history: List[Dict[str, Any]] = []

    # Workflow-specific state data
    data: T

# Example of a specific workflow state
class AmberWorkflowState(BaseModel):
    """Specific state data for Amber workflow"""
    research_topics: List[str] = []
    collected_information: Dict[str, Any] = {}
    draft_response: Optional[str] = None

# Example of another workflow state
class BlueWorkflowState(BaseModel):
    """Specific state data for Blue workflow"""
    calculation_results: Dict[str, float] = {}
    data_sources: List[str] = []
    verification_status: str = "pending"

# Complete workflow state for Amber workflow
class AmberState(BaseWorkflowState[AmberWorkflowState]):
    pass

# Complete workflow state for Blue workflow
class BlueState(BaseWorkflowState[BlueWorkflowState]):
    pass

class WorkflowRunInfo(BaseModel):
    """Information about a workflow run"""
    id: str
    codename: WorkflowCodename
    status: WorkflowStatus
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    current_state: BaseWorkflowState
    created_at: datetime
    updated_at: datetime
```

### Database Schema Changes
```python
# SQLAlchemy models to be added to db/models.py
import sqlalchemy as sa
from sqlalchemy.ext.mutable import MutableDict
import json

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True)
    codename = Column(String, nullable=False)
    status = Column(String, nullable=False, default="running")  # Used to track if workflow is running
    confidence_score = Column(Float, nullable=False)
    current_step = Column(String, nullable=False)
    step_history = Column(Text, default="[]")
    conversation_history = Column(Text, default="[]")
    state_data = Column(Text, nullable=False)  # JSON representation of the state
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    communications = relationship("CommunicationWorkflow", back_populates="workflow_run")

    @property
    def step_history_list(self):
        return json.loads(self.step_history)

    @step_history_list.setter
    def step_history_list(self, value):
        self.step_history = json.dumps(value)

    @property
    def conversation_history_list(self):
        return json.loads(self.conversation_history)

    @conversation_history_list.setter
    def conversation_history_list(self, value):
        self.conversation_history = json.dumps(value)

    def get_typed_state(self):
        """
        Convert the raw state_data into a strongly-typed state object
        based on the workflow codename
        """
        state_dict = json.loads(self.state_data)

        if self.codename == "amber":
            return AmberState.parse_obj(state_dict)
        elif self.codename == "blue":
            return BlueState.parse_obj(state_dict)
        # Add more workflow types as needed
        else:
            raise ValueError(f"Unknown workflow codename: {self.codename}")

    def set_typed_state(self, state):
        """
        Convert a strongly-typed state object into JSON for storage
        """
        self.state_data = state.json()

    def update_status(self, status):
        """
        Update the workflow status
        """
        self.status = status
        self.updated_at = datetime.utcnow()

# Generic association table between any communication channel and workflows
class CommunicationWorkflow(Base):
    __tablename__ = "communication_workflows"

    id = Column(Integer, primary_key=True)
    channel_type = Column(String, nullable=False)  # 'email_thread', 'api_call', 'ui_interaction', etc.
    channel_id = Column(String, nullable=False)    # ID of the specific communication entity
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    workflow_run = relationship("WorkflowRun", back_populates="communications")

    # Enforce uniqueness - one communication entity can only be associated with one workflow
    __table_args__ = (
        UniqueConstraint('channel_type', 'channel_id', name='unique_communication_channel'),
    )
```

## Workflow System Design

### Decoupled Architecture
- Workflows exist independently of communication channels
- Any communication channel (email, API, UI) can trigger and interact with workflows
- Communication channels are associated with workflows through a generic association table
- The association table stores channel type and ID for complete flexibility

### Workflow State Management
Each workflow type has its own strongly-typed state structure:
1. Common fields shared across all workflows (current step, history, etc.)
2. Workflow-specific state data that varies by workflow type
3. New state fields can be added in the future with default values

### Workflow Status Tracking
The system tracks the status of each workflow run:
1. **Running**: Workflow is actively processing (ensures only one instance runs at a time)
2. **Awaiting Feedback**: Workflow is waiting for user input
3. **Completed**: Workflow has finished successfully
4. **Failed**: Workflow encountered an error
5. **Cancelled**: Workflow was manually stopped

### State Transitions
To transition to the next state, the system will:
1. Check if the workflow is in a valid state for transition (not completed or failed)
2. Retrieve the current workflow run from the database
3. Convert raw JSON state to the strongly-typed state object for that workflow
4. Process new inputs using the typed state and Pydantic AI
5. Generate a new state based on the AI's response
6. Update the workflow run with the new state and status
7. Execute any actions required by the new state

## Integration Points
- Connect with Email Adapter from Milestone 1 via communication association
- Prepare for integration with Workflow Engine in Milestone 3
- Update database schema and migration scripts
- Design interfaces for workflow state transitions
- Add API endpoints for non-email workflow interactions

## Testing Strategy
- Unit tests for individual components
- Integration tests for the email parsing pipeline
- Workflow state transition tests
- Status management tests
- End-to-end tests simulating interactions from different communication channels
- Validation tests for the extracted information

## Success Criteria
- System can successfully determine appropriate workflow types from emails
- Workflows are properly decoupled from communication channels
- Each workflow maintains its own strongly-typed state
- System ensures only one workflow instance runs at a time using status
- System tracks workflow status accurately
- System can retrieve, update, and transition between states
- System acknowledges emails with understanding of the extracted information
- All tests pass with at least 90% code coverage
- Documentation is updated to reflect the new functionality

## Considerations
- Design for future expansion of workflow types
- Enable easy addition of new workflow codenames and state types
- Handle edge cases such as ambiguous email content
- Consider multi-language support for future iterations
- Handle future state changes through default values in Pydantic models
- Design for extensibility to support new communication channels
- Prepare for workflow trigger queuing to be implemented in Milestone 4 (when a new trigger arrives while workflow is running, it should be queued for execution after the current run completes)
