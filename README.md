# Sway Backend

Backend service for Sway chat application.

## Features

- FastAPI backend with PostgreSQL database
- Chat functionality with AI-powered responses
- Multi-layered processing approach:
  - Layer 1: Conversation analysis
  - Layer 2: Prompt selection
  - Layer 3: Response processing
- WebSocket support for streaming responses
- Docker and docker-compose setup for easy deployment

## Prerequisites

- Docker and docker-compose
- Python 3.10+
- Poetry (for local development)

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```
# Database settings
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=sway
POSTGRES_HOST=db
POSTGRES_PORT=5432

# API settings
API_HOST=0.0.0.0
API_PORT=8000

# OpenRouter API settings
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_API_ENDPOINT=https://openrouter.ai/api/v1/chat/completions
OPENROUTER_MODEL_NAME=anthropic/claude-3.7-sonnet
```

Replace `your_openrouter_api_key` with your actual OpenRouter API key.

## Running with Docker

1. Build and start the containers:

```bash
docker-compose up -d
```

2. Run database migrations:

```bash
docker-compose exec api alembic upgrade head
```

3. Access the API at http://localhost:8000

## Local Development

1. Install dependencies:

```bash
poetry install
```

2. Set up the database:

```bash
# Start PostgreSQL
docker-compose up -d db

# Run migrations
poetry run alembic upgrade head
```

3. Run the development server:

```bash
poetry run uvicorn app.main:app --reload
```

## API Documentation

Once the server is running, you can access the API documentation at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
sway-backend/
├── alembic/                  # Database migrations
├── app/
│   ├── api/                  # API endpoints
│   ├── core/                 # Core functionality
│   ├── db/                   # Database models and session
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic schemas
│   ├── services/             # Business logic
│   └── main.py               # FastAPI application
├── docker/                   # Docker configuration
├── .env                      # Environment variables
├── alembic.ini               # Alembic configuration
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile                # Docker configuration
├── poetry.lock               # Poetry lock file
├── pyproject.toml            # Poetry configuration
└── README.md                 # This file
```
