# ConcurrentAI Chat Engine API

A RESTful API that enables concurrent math-focused chat conversations with an AI agent. Built as a technical assessment, it demonstrates robust async handling, clean architecture, and engineering best practices. The API allows users to maintain multiple independent conversations, process real-time math calculations, and maintain conversation history - all powered by Google's Gemini LLM model.

## Requirements

- Python 3.12+
- Poetry (Python package manager)

## Development Process

This project was developed in a single intensive coding session, which is why it's being committed as a complete implementation rather than through incremental commits. However, here's the logical progression of how the project was built:

1. Initial Setup (First logical milestone)

   - Project structure setup with Poetry
   - Core dependencies configuration
   - Basic FastAPI application skeleton

2. Core Features (Second logical milestone)

   - Basic conversation management
   - In-memory repository implementation
   - Initial LLM service integration
   - Basic math processing capabilities

3. Advanced Features (Third logical milestone)

   - Enhanced math processing with context awareness
   - Rate limiting implementation
   - Request queuing for concurrent handling
   - Conversation state management

4. Production Readiness (Fourth logical milestone)

   - Comprehensive error handling
   - Logging and monitoring setup
   - OpenTelemetry integration
   - API documentation

5. Testing & Documentation (Final milestone)
   - Unit and integration tests
   - Performance testing
   - README and API documentation
   - Example usage scripts

Note: While this represents the logical development flow, the actual implementation was done in a rapid development session. In a production environment, these would typically be separate commits with proper version control practices.

## Tech Stack & Features

### Core Technologies

- FastAPI - Async web framework for building the API
- Google Gemini - Primary LLM for chat responses
- Poetry - Dependency and virtual environment management
- Pydantic - Data validation and settings management
- pytest - Testing framework
- structlog - Structured logging
- OpenTelemetry - Observability and tracing

### Key Features & Implementation

1. **Math Operations**

   - Direct calculation engine for basic operations
   - Context-aware calculations (e.g., "multiply that by 5")
   - Fallback to Gemini for complex queries
   - Support for informal math language ("double this", "take half")

2. **Rate Limiting**

   - Sliding window rate limiter
   - Per-endpoint and per-IP limiting
   - Configurable limits and windows

3. **Request Queuing**

   - Async request queue for handling concurrent requests
   - Prevents server overload
   - Ensures request ordering

4. **Conversation Management**
   - In-memory storage with Repository pattern
   - Full conversation history
   - Pagination support

## Setup Instructions

### Windows (PowerShell)

1. Install Python 3.12:
   Download from https://www.python.org/downloads/
   Make sure to check "Add Python to PATH" during installation

2. Install Poetry:
   Open PowerShell and run:
   (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

3. Clone and setup:
   git clone <repository-url>
   cd KonkoAI_Assessment
   poetry install

4. Set Gemini API key (Optional - a default key is provided):
   $env:GEMINI_API_KEY="your-api-key-here"

   Note: If you don't set an API key, the application will use a default key that has no cost/usage limits.

5. Run the server:
   poetry run uvicorn konko_ai_chat.api.app:app --reload

### macOS/Linux

1. Install Python 3.12:

   For macOS with Homebrew:
   brew install python@3.12

   For Linux:
   sudo apt update
   sudo apt install python3.12

2. Install Poetry:
   curl -sSL https://install.python-poetry.org | python3 -

3. Clone and setup:
   git clone <repository-url>
   cd KonkoAI_Assessment
   poetry install

4. Set Gemini API key (Optional - a default key is provided):
   export GEMINI_API_KEY="your-api-key-here"

   Note: If you don't set an API key, the application will use a default key that has no cost/usage limits.

5. Run the server:
   poetry run uvicorn konko_ai_chat.api.app:app --reload

## API Usage

### Create a Conversation

Send a POST request to http://localhost:8000/conversations

### Send a Message

Send a POST request to http://localhost:8000/conversations/{conversation_id}/messages
Include a JSON body with your message content

### List Messages in a Conversation

Send a GET request to http://localhost:8000/conversations/{conversation_id}/messages

### List All Conversations

Send a GET request to http://localhost:8000/conversations

## Interactive Testing (Windows PowerShell)

1.  Create a new conversation and save the ID:
    $response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/conversations"
   $conversationId = $response.id
    Write-Host "Conversation ID: $conversationId"

2.  Send a message and get response:
    $body = @{content = "What's 25 times 4?"} | ConvertTo-Json

    
    $response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/conversations/$conversationId/messages" -ContentType "application/json" -Body
     $body
   Write-Host "Response: $($response.content)"

4.  Get conversation history:
    $messages = Invoke-RestMethod -Method Get -Uri "http://localhost:8000/conversations/$conversationId/messages"
    $messages | ForEach-Object { Write-Host "$($_.role): $($\_.content)"}
      

5.  Try complex math operations:

    # Initial calculation

    $body = @{
    content = "Start with 100"
    } | ConvertTo-Json

    Invoke-RestMethod -Method Post -Uri "http://localhost:8000/conversations/$conversationId/messages" -ContentType "application/json" -Body $body

    # Follow-up operations

    $operations = @(
    "double that",
    "add 50 to this",
    "multiply that by 3",
    "take half of this"
    )

    foreach ($op in $operations) {
    $body = @{
    content = $op
    } | ConvertTo-Json

        $response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/conversations/$conversationId/messages" -ContentType "application/json" -Body $body
        Write-Host "Operation: $op -> Result: $($response.content)"

    }

## Complete API Reference

### Conversations

Create Conversation

- Endpoint: POST /conversations
- Returns: New conversation object with ID containing:
  - id: uuid
  - created_at: timestamp
  - messages: []

List Conversations

- Endpoint: GET /conversations
- Optional parameters:
  - limit: Number of conversations to return (default=10)
  - offset: Number of conversations to skip (default=0)
- Returns: List of conversations with their last message

Get Conversation

- Endpoint: GET /conversations/{conversation_id}
- Returns: Conversation details with all messages

### Messages

Send Message

- Endpoint: POST /conversations/{conversation_id}/messages
- Body should contain: { "content": "your message here" }
- Returns: Created message object with AI response

List Messages

- Endpoint: GET /conversations/{conversation_id}/messages
- Optional parameters:
  - limit: Number of messages to return (default=100)
  - offset: Number of messages to skip (default=0)
- Returns: List of messages in the conversation

### Rate Limiting

All endpoints are rate-limited:

- 100 requests per minute per IP address
- Rate limits applied per endpoint
- Headers returned:
  - X-RateLimit-Limit: Maximum requests allowed
  - X-RateLimit-Remaining: Remaining requests
  - X-RateLimit-Reset: Time until limit resets

### Error Responses

Standard HTTP status codes:

- 200 OK: Success
- 400 Bad Request: Invalid input
- 404 Not Found: Resource not found
- 429 Too Many Requests: Rate limit exceeded
- 500 Internal Server Error: Server error

Error responses include a detail message explaining what went wrong.

## Example Math Operations

The API supports various ways to express mathematical operations:

1. Direct calculations:

   - What's 103 times 4439?
   - Divide 1000 by 4
   - Add 150 to 275

2. Context-aware operations:

   - Start with 100
   - Multiply that by 5
   - Add 50 to this
   - Take half of that

3. Informal language:
   - Double this number
   - Triple that
   - Cut this in half
   - Add another hundred
   - Take away 30

## Testing

Run all tests:
For Windows PowerShell:
poetry run pytest -v

For macOS/Linux:
poetry run pytest -v

Run specific test files:
poetry run pytest tests/test_api.py -v
poetry run pytest tests/test_complex_math.py -v

## Implementation Details

### Rate Limiting

- Uses sliding window algorithm
- Default: 100 requests per minute per IP
- Configurable via environment variables

### Request Queue

- Async queue with configurable size
- FIFO processing of requests
- Automatic overflow protection

### Math Processing

1. Direct Calculation Engine

   - Pattern matching for operations
   - Context tracking for references
   - Support for word-to-number conversion

2. Gemini Integration
   - Fallback for complex queries
   - Structured prompt engineering
   - Error handling with graceful degradation

### Concurrency and Parallelism

1. Async Request Handling

   - FastAPI's async endpoints for non-blocking I/O
   - Efficient handling of multiple concurrent connections
   - Asynchronous database operations

2. Conversation Isolation

   - Each conversation maintains its own state
   - Multiple users can chat simultaneously
   - No cross-conversation interference

3. Resource Management

   - Request queuing prevents server overload
   - Rate limiting ensures fair resource distribution
   - Singleton LLM service for efficient API key usage

4. Thread Safety
   - In-memory repository with thread-safe operations
   - Atomic conversation updates
   - Synchronized access to shared resources

### Testing Strategy

- Unit tests for core functionality
- Integration tests for API endpoints
- Performance tests for concurrency
- Complex math tests for edge cases
