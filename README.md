# AI Meeting Operations Bot (Python)

A production-ready Python application that implements an AI-powered Meeting Operations Bot integrating Zoom Webhooks, Slack Bot, OpenAI, Microsoft Graph, and Jira REST API.

## Features

- 📹 **Zoom Integration**: Receives webhooks for meeting recordings and transcript completion
- 🤖 **AI-Powered Summarization**: Uses OpenAI GPT-4 to generate meeting summaries and extract action items
- 💬 **Slack Bot**: Posts formatted summaries with interactive elements
- 📅 **Microsoft Graph**: Schedules follow-up meetings in Outlook/Teams
- 🎫 **Jira Integration**: Automatically creates tickets for action items
- ⚡ **Background Processing**: Async queue system for reliable processing
- 🔒 **Security**: Webhook signature verification, encrypted token storage

## Architecture

```
app/
├── config.py           # Pydantic settings configuration
├── main.py             # FastAPI application factory
├── models/
│   └── types.py        # Pydantic data models
├── services/
│   ├── zoom.py         # Zoom API service
│   ├── llm.py          # OpenAI LLM service
│   ├── slack.py        # Slack messaging service
│   ├── outlook.py      # Microsoft Graph service
│   ├── jira.py         # Jira API service
│   ├── meeting.py      # Meeting orchestration
│   └── queue.py        # Background job queue
├── repositories/
│   ├── idempotency.py  # Idempotency tracking
│   ├── storage.py      # Transcript storage
│   ├── jira_ticket.py  # Ticket deduplication
│   └── user_mapping.py # User identity mapping
├── middlewares/
│   ├── zoom_auth.py    # Zoom signature verification
│   ├── slack_auth.py   # Slack signature verification
│   ├── request.py      # Request logging
│   └── error.py        # Error handling
├── routes/
│   ├── zoom.py         # Zoom webhook endpoints
│   ├── slack.py        # Slack interaction endpoints
│   ├── health.py       # Health check endpoints
│   └── admin.py        # Admin management endpoints
└── utils/
    ├── logger.py       # Structured logging
    ├── retry.py        # Retry decorators
    └── encryption.py   # AES-256-GCM encryption
```

## Prerequisites

- Python 3.11+
- Poetry (recommended) or pip
- Zoom Server-to-Server OAuth App
- Slack Bot App with appropriate scopes
- OpenAI API key
- Microsoft Entra ID (Azure AD) App Registration
- Jira Cloud account with API token

## Quick Start

### 1. Clone and Install Dependencies

```bash
cd ai-meeting-bot-python

# Using Poetry (recommended)
poetry install

# Or using pip
pip install -e .
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Run the Application

```bash
# Development mode
poetry run python run.py

# Or with uvicorn directly
poetry run uvicorn app.main:app --reload --port 3000

# Or with Docker
docker-compose up --build
```

## API Endpoints

### Health

- `GET /api/health` - Basic health check
- `GET /api/health/live` - Liveness probe
- `GET /api/health/ready` - Readiness probe
- `GET /api/health/detailed` - Detailed health with service status

### Webhooks

- `POST /api/webhooks/zoom` - Zoom webhook receiver
- `POST /api/slack/events` - Slack event subscriptions
- `POST /api/slack/interactions` - Slack interactive components
- `POST /api/slack/commands` - Slack slash commands

### OAuth (User Authorization)

- `GET /api/oauth/zoom/callback` - Zoom OAuth callback
- `GET /api/oauth/microsoft/callback` - Microsoft OAuth callback
- `GET /api/oauth/jira/callback` - Jira OAuth callback

### Admin

- `POST /api/admin/user-mappings` - Create user mapping
- `GET /api/admin/user-mappings` - List user mappings
- `GET /api/admin/queue/stats` - Queue statistics
- `GET /api/admin/meetings/{id}/tickets` - Meeting tickets

## User Authorization Flow

Instead of requiring admin-configured API tokens, this bot uses OAuth to let each user authorize their own accounts:

### How It Works

1. **Invite the Bot**: Add `@MeetingBot` to your Slack channel
2. **Mention the Bot**: Type `@MeetingBot setup` or just `@MeetingBot`
3. **Click Authorization Links**: The bot will show buttons to connect:
   - 🎥 **Zoom** - Access your meeting recordings
   - 📅 **Microsoft 365** - Schedule follow-up meetings
   - 📋 **Jira** - Create tickets for action items
4. **Authorize**: Click each button and log in to authorize
5. **Done!**: Your tokens are securely stored and the bot can now process your meetings

### Slack Commands

- `@MeetingBot setup` - Show authorization links for all services
- `@MeetingBot status` - Check which services are connected
- `@MeetingBot disconnect` - Disconnect a service
- `@MeetingBot help` - Show help message

### Setting Up OAuth Apps

#### Zoom OAuth App

1. Go to [Zoom App Marketplace](https://marketplace.zoom.us/)
2. Create an **OAuth** app (not Server-to-Server)
3. Set redirect URL: `https://your-app.com/api/oauth/zoom/callback`
4. Add scopes: `recording:read`, `meeting:read`, `user:read`
5. Copy Client ID and Client Secret to `.env`

#### Microsoft OAuth App

1. Go to [Azure Portal](https://portal.azure.com) → App Registrations
2. Create new registration
3. Add redirect URI: `https://your-app.com/api/oauth/microsoft/callback`
4. Add API permissions: `Calendars.ReadWrite`, `User.Read`, `offline_access`
5. Create client secret
6. Copy Client ID, Tenant ID, and Secret to `.env`

#### Jira OAuth App

1. Go to [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/)
2. Create a new OAuth 2.0 app
3. Set callback URL: `https://your-app.com/api/oauth/jira/callback`
4. Add scopes: `read:jira-work`, `write:jira-work`, `read:jira-user`
5. Copy Client ID and Client Secret to `.env`

## Configuration

### Zoom Server-to-Server OAuth

1. Go to [Zoom App Marketplace](https://marketplace.zoom.us/)
2. Create a Server-to-Server OAuth app
3. Add scopes: `recording:read`, `meeting:read`
4. Configure webhook with events: `recording.completed`, `recording.transcript_completed`

### Slack App

1. Create app at [api.slack.com](https://api.slack.com/apps)
2. Enable Socket Mode and Events API
3. Required scopes:
   - `chat:write`, `chat:write.public`
   - `im:write`, `im:history`
   - `users:read`, `users:read.email`
4. Enable Interactivity

### Microsoft Graph

1. Register app in [Azure Portal](https://portal.azure.com)
2. Add API permissions: `Calendars.ReadWrite`, `User.Read.All`
3. Create client secret

### Jira

1. Generate API token at [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Use your Atlassian email and token for authentication

## Development

### Running Tests

```bash
poetry run pytest
```

### Code Formatting

```bash
poetry run black app/
poetry run isort app/
poetry run ruff check app/
```

### Type Checking

```bash
poetry run mypy app/
```

## Deployment

### Docker

```bash
docker build -t ai-meeting-bot-python .
docker run -p 3000:3000 --env-file .env ai-meeting-bot-python
```

### Docker Compose

```bash
docker-compose up -d
```

### Kubernetes

Deploy using the provided manifests:

```bash
kubectl apply -f k8s/
```

## Security Considerations

- All webhook endpoints verify signatures
- Tokens are encrypted at rest using AES-256-GCM
- Sensitive data is redacted from logs
- CORS is configured for allowed origins only
- Rate limiting recommended for production

## License

MIT License
