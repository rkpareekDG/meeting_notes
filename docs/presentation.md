# AI Meeting Operations Bot
## Intelligent Meeting Automation Platform

---

# 📋 Table of Contents

1. **Overview** - What is this bot?
2. **Key Features** - What can it do?
3. **Architecture** - How is it built?
4. **OAuth Flow** - How users connect
5. **Meeting Processing Flow** - End-to-end workflow
6. **Technical Stack** - Technologies used
7. **Setup Guide** - How to deploy
8. **Demo Scenarios** - Real-world examples

---

# 🎯 Overview

## The Problem

- 😩 **Manual Meeting Notes** - Hours spent documenting meetings
- 📝 **Lost Action Items** - Important tasks fall through cracks  
- 🔄 **No Follow-up** - Meetings end without scheduled next steps
- 📊 **Scattered Information** - Notes in different tools

## The Solution

**AI Meeting Bot** automatically:
- ✅ Processes Zoom recordings
- ✅ Generates AI summaries
- ✅ Extracts action items
- ✅ Creates Jira tickets
- ✅ Schedules follow-up meetings

---

# ✨ Key Features

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI MEETING BOT                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🎥 ZOOM INTEGRATION                                            │
│  • Auto-capture meeting recordings                               │
│  • Process transcripts automatically                             │
│                                                                  │
│  🤖 AI-POWERED ANALYSIS                                         │
│  • GPT-4 meeting summarization                                   │
│  • Smart action item extraction                                  │
│  • Participant identification                                    │
│                                                                  │
│  💬 SLACK NOTIFICATIONS                                         │
│  • Rich formatted summaries                                      │
│  • Interactive buttons                                           │
│  • Real-time updates                                             │
│                                                                  │
│  📋 JIRA INTEGRATION                                            │
│  • One-click ticket creation                                     │
│  • Auto-populate details                                         │
│  • Link to meeting context                                       │
│                                                                  │
│  📅 OUTLOOK CALENDAR                                            │
│  • Schedule follow-ups                                           │
│  • Auto-invite participants                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 🏗️ System Architecture

```
                              ┌─────────────────┐
                              │   SLACK BOT     │
                              │   Interface     │
                              └────────┬────────┘
                                       │
                                       ▼
┌──────────────┐            ┌─────────────────────┐            ┌──────────────┐
│              │            │                     │            │              │
│  ZOOM        │───────────▶│    FASTAPI          │◀───────────│  USERS       │
│  Webhooks    │            │    SERVER           │   OAuth    │  (Slack)     │
│              │            │                     │            │              │
└──────────────┘            └─────────────────────┘            └──────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
             ┌───────────┐      ┌───────────┐      ┌───────────┐
             │  OpenAI   │      │  Jira     │      │  Outlook  │
             │  GPT-4    │      │  Cloud    │      │  Calendar │
             └───────────┘      └───────────┘      └───────────┘
```

---

# 🔐 OAuth Authorization Flow

## Why OAuth?
- **No shared passwords** - Users login with their own accounts
- **Scoped access** - Only request permissions needed
- **Revocable** - Users can disconnect anytime
- **Secure** - Industry standard (RFC 6749)

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER AUTHORIZATION FLOW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  STEP 1: User mentions @MeetingBot in Slack                     │
│          ↓                                                       │
│  STEP 2: Bot shows "Connect Zoom", "Connect Outlook" buttons    │
│          ↓                                                       │
│  STEP 3: User clicks button → Redirected to provider login      │
│          ↓                                                       │
│  STEP 4: User logs in and authorizes                            │
│          ↓                                                       │
│  STEP 5: Provider redirects back with auth code                 │
│          ↓                                                       │
│  STEP 6: Bot exchanges code for access token                    │
│          ↓                                                       │
│  STEP 7: Token stored encrypted → User is connected! ✅         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 🔄 OAuth Sequence Diagram

```
┌──────┐          ┌──────────┐          ┌──────────┐          ┌──────────┐
│ User │          │  Slack   │          │   Bot    │          │  Zoom    │
└──┬───┘          └────┬─────┘          └────┬─────┘          └────┬─────┘
   │                   │                     │                     │
   │  @MeetingBot      │                     │                     │
   │──────────────────▶│                     │                     │
   │                   │  Event: app_mention │                     │
   │                   │────────────────────▶│                     │
   │                   │                     │                     │
   │                   │  Show Connect       │                     │
   │                   │◀────────────────────│                     │
   │                   │  Buttons            │                     │
   │                   │                     │                     │
   │  Click "Connect   │                     │                     │
   │  Zoom" button     │                     │                     │
   │───────────────────┼─────────────────────┼────────────────────▶│
   │                   │                     │                     │
   │                   │                     │      Login Page     │
   │◀──────────────────┼─────────────────────┼─────────────────────│
   │                   │                     │                     │
   │  Enter credentials│                     │                     │
   │──────────────────────────────────────────────────────────────▶│
   │                   │                     │                     │
   │                   │                     │  Callback + Code    │
   │                   │                     │◀────────────────────│
   │                   │                     │                     │
   │                   │                     │  Exchange for Token │
   │                   │                     │────────────────────▶│
   │                   │                     │                     │
   │                   │                     │  Access Token       │
   │                   │                     │◀────────────────────│
   │                   │                     │                     │
   │                   │  "Connected! ✅"    │                     │
   │◀──────────────────┼─────────────────────│                     │
   │                   │                     │                     │
```

---

# 📹 Meeting Processing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                 END-TO-END MEETING FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐                                                │
│  │ 1. MEETING  │  User hosts Zoom meeting                       │
│  │    ENDS     │  Recording is processed by Zoom                │
│  └──────┬──────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────┐                                                │
│  │ 2. WEBHOOK  │  Zoom sends recording.completed event          │
│  │    RECEIVED │  Bot validates signature & queues job          │
│  └──────┬──────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────┐                                                │
│  │ 3. DOWNLOAD │  Bot downloads transcript using                │
│  │    CONTENT  │  user's OAuth token                            │
│  └──────┬──────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────┐                                                │
│  │ 4. AI       │  GPT-4 analyzes transcript:                    │
│  │    ANALYSIS │  • Summary • Action Items • Participants       │
│  └──────┬──────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────┐                                                │
│  │ 5. SLACK    │  Rich message posted to channel:               │
│  │    NOTIFY   │  • Summary card • Action buttons               │
│  └──────┬──────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────┐                                                │
│  │ 6. USER     │  • Create Jira tickets                         │
│  │    ACTIONS  │  • Schedule follow-up meeting                  │
│  └─────────────┘                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 💬 Slack Message Example

```
┌─────────────────────────────────────────────────────────────────┐
│  🤖 Meeting Bot                                          2:35 PM│
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📋 Meeting Summary                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                     │
│                                                                  │
│  📅 Sprint Planning - Q1 2026                                   │
│  🕐 Duration: 45 minutes                                         │
│  👥 Participants: John, Sarah, Mike, Lisa                       │
│                                                                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                     │
│                                                                  │
│  📝 Summary                                                      │
│  The team discussed Q1 priorities, reviewed the backlog,        │
│  and assigned story points. Key focus areas include the         │
│  new authentication system and mobile app improvements.         │
│                                                                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━            │
│                                                                  │
│  🎯 Action Items                                                 │
│                                                                  │
│  1. @John - Complete API documentation by Friday                │
│     └─ [Create Jira Ticket]                                     │
│                                                                  │
│  2. @Sarah - Review security requirements                       │
│     └─ [Create Jira Ticket]                                     │
│                                                                  │
│  3. @Mike - Set up staging environment                          │
│     └─ [Create Jira Ticket]                                     │
│                                                                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━            │
│                                                                  │
│  ┌──────────────────┐  ┌────────────────────┐                   │
│  │ 📋 Create All    │  │ 📅 Schedule        │                   │
│  │    Tickets       │  │    Follow-up       │                   │
│  └──────────────────┘  └────────────────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 🎫 Jira Ticket Creation

## When user clicks "Create Jira Ticket":

```
┌─────────────────────────────────────────────────────────────────┐
│                        JIRA TICKET                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Project:     MEET                                               │
│  Type:        Task                                               │
│  Priority:    Medium                                             │
│                                                                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                     │
│                                                                  │
│  Summary:                                                        │
│  Complete API documentation by Friday                            │
│                                                                  │
│  Description:                                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Action item from meeting: Sprint Planning - Q1 2026     │    │
│  │                                                         │    │
│  │ **Context:**                                            │    │
│  │ The team discussed the need for comprehensive API       │    │
│  │ documentation to support the new authentication system. │    │
│  │                                                         │    │
│  │ **Original action item:**                               │    │
│  │ Complete API documentation by Friday                    │    │
│  │                                                         │    │
│  │ **Assigned to:** John                                   │    │
│  │ **Meeting date:** March 3, 2026                         │    │
│  │                                                         │    │
│  │ ---                                                     │    │
│  │ 🤖 Created by AI Meeting Bot                            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Assignee:    John Smith                                         │
│  Reporter:    Meeting Bot                                        │
│  Labels:      meeting-action-item, auto-created                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 📅 Follow-up Meeting Scheduling

## When user clicks "Schedule Follow-up":

```
┌─────────────────────────────────────────────────────────────────┐
│                  OUTLOOK CALENDAR EVENT                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📅 Follow-up: Sprint Planning - Q1 2026                        │
│                                                                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                     │
│                                                                  │
│  🕐 When:      Next Monday, 2:00 PM - 2:30 PM                   │
│  📍 Where:     Zoom Meeting (auto-generated)                    │
│  👥 Attendees: John, Sarah, Mike, Lisa                          │
│                                                                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                     │
│                                                                  │
│  📝 Agenda:                                                      │
│                                                                  │
│  Follow-up meeting for "Sprint Planning - Q1 2026"              │
│                                                                  │
│  **Previous Action Items to Review:**                            │
│  • Complete API documentation - @John                            │
│  • Review security requirements - @Sarah                         │
│  • Set up staging environment - @Mike                            │
│                                                                  │
│  **Meeting Notes:**                                              │
│  [Link to Slack summary]                                         │
│                                                                  │
│  ---                                                             │
│  🤖 Scheduled by AI Meeting Bot                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 🛠️ Technical Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    TECHNOLOGY STACK                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  BACKEND                          INTEGRATIONS                   │
│  ━━━━━━━━━━━━━━━━━━━━━           ━━━━━━━━━━━━━━━━━              │
│  🐍 Python 3.11+                  📹 Zoom API                   │
│  ⚡ FastAPI                       💬 Slack API                  │
│  📦 Pydantic 2.x                  🤖 OpenAI GPT-4               │
│  🔄 HTTPX (async HTTP)            📅 Microsoft Graph            │
│  📝 Structlog                     📋 Jira REST API              │
│                                                                  │
│  SECURITY                         INFRASTRUCTURE                 │
│  ━━━━━━━━━━━━━━━━━━━━━           ━━━━━━━━━━━━━━━━━              │
│  🔐 OAuth 2.0                     🐳 Docker                     │
│  🔒 AES-256-GCM encryption        ☸️ Kubernetes ready           │
│  ✅ Webhook signature verify       📊 Health checks             │
│  🛡️ CSRF protection (state)       ♻️ Auto-retry with backoff   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 📁 Project Structure

```
ai-meeting-bot-python/
│
├── app/
│   ├── main.py              # FastAPI application factory
│   ├── config.py            # Pydantic settings
│   │
│   ├── models/
│   │   ├── types.py         # Data models (Meeting, ActionItem, etc.)
│   │   └── oauth.py         # OAuth token models
│   │
│   ├── services/
│   │   ├── zoom.py          # Zoom API client
│   │   ├── slack.py         # Slack messaging
│   │   ├── slack_bot.py     # Bot interaction handler
│   │   ├── llm.py           # OpenAI GPT-4 integration
│   │   ├── outlook.py       # Microsoft Graph client
│   │   ├── jira.py          # Jira API client
│   │   ├── oauth.py         # OAuth flow handler
│   │   ├── meeting.py       # Meeting orchestration
│   │   └── queue.py         # Background job queue
│   │
│   ├── repositories/
│   │   ├── oauth.py         # Token storage
│   │   ├── storage.py       # Transcript storage
│   │   └── idempotency.py   # Duplicate prevention
│   │
│   ├── routes/
│   │   ├── zoom.py          # /api/webhooks/zoom
│   │   ├── slack.py         # /api/slack/events
│   │   ├── oauth.py         # /api/oauth/{provider}/callback
│   │   └── health.py        # /api/health
│   │
│   ├── middlewares/
│   │   ├── zoom_auth.py     # Webhook signature verification
│   │   ├── slack_auth.py    # Slack signature verification
│   │   └── error.py         # Global error handling
│   │
│   └── utils/
│       ├── encryption.py    # AES-256 token encryption
│       ├── logger.py        # Structured logging
│       └── retry.py         # Retry decorators
│
├── .env.example             # Environment template
├── Dockerfile               # Container image
├── docker-compose.yml       # Local development
└── pyproject.toml           # Dependencies
```

---

# 🚀 Quick Start Guide

## Step 1: Clone & Install

```bash
git clone <repository>
cd ai-meeting-bot-python

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .
```

## Step 2: Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

## Step 3: Start ngrok (for local development)

```bash
ngrok http 3000
# Copy the https URL
```

## Step 4: Run the Server

```bash
python run.py
# Server starts at http://localhost:3000
```

## Step 5: Test in Slack

```
@MeetingBot setup
```

---

# 📊 Demo Scenario 1: First-Time Setup

```
┌─────────────────────────────────────────────────────────────────┐
│                    SCENARIO: NEW USER SETUP                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  USER                          BOT                               │
│  ━━━━━━━━━━━━━━━━━━━━━        ━━━━━━━━━━━━━━━━━━━━━             │
│                                                                  │
│  @MeetingBot hi! ──────────▶                                    │
│                                                                  │
│                             ◀──────── 👋 Hi! I'm your AI        │
│                                       Meeting Assistant.         │
│                                                                  │
│                                       Connect your accounts:     │
│                                       [🎥 Zoom] [📅 Outlook]    │
│                                       [📋 Jira]                 │
│                                                                  │
│  *clicks Zoom button* ─────▶                                    │
│                                                                  │
│  *logs into Zoom* ─────────▶                                    │
│                                                                  │
│                             ◀──────── ✅ Zoom connected!        │
│                                                                  │
│  @MeetingBot status ───────▶                                    │
│                                                                  │
│                             ◀──────── 📊 Your Status:           │
│                                       ✅ Zoom - Connected        │
│                                       ❌ Outlook - Not connected │
│                                       ❌ Jira - Not connected    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 📊 Demo Scenario 2: Meeting Processed

```
┌─────────────────────────────────────────────────────────────────┐
│              SCENARIO: AUTOMATIC MEETING PROCESSING              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TIMELINE                                                        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━              │
│                                                                  │
│  2:00 PM  │ Team meeting starts on Zoom                         │
│           │                                                      │
│  2:45 PM  │ Meeting ends, Zoom processes recording               │
│           │                                                      │
│  2:47 PM  │ Zoom sends webhook to bot                            │
│           │ Bot downloads transcript                             │
│           │                                                      │
│  2:48 PM  │ GPT-4 analyzes transcript                            │
│           │ Extracts 5 action items                              │
│           │                                                      │
│  2:49 PM  │ Summary posted to #engineering channel               │
│           │                                                      │
│           │  ┌────────────────────────────────┐                  │
│           │  │ 📋 Meeting Summary             │                  │
│           │  │                                │                  │
│           │  │ Sprint Planning Q1 2026        │                  │
│           │  │ 45 min • 4 participants        │                  │
│           │  │                                │                  │
│           │  │ 🎯 5 Action Items extracted    │                  │
│           │  │                                │                  │
│           │  │ [Create Tickets] [Follow-up]  │                  │
│           │  └────────────────────────────────┘                  │
│           │                                                      │
│  2:50 PM  │ User clicks "Create All Tickets"                     │
│           │ 5 Jira tickets created automatically                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 📊 Demo Scenario 3: Jira Ticket Creation

```
┌─────────────────────────────────────────────────────────────────┐
│              SCENARIO: ONE-CLICK TICKET CREATION                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  USER                          SYSTEM                            │
│  ━━━━━━━━━━━━━━━━━━━━━        ━━━━━━━━━━━━━━━━━━━━━             │
│                                                                  │
│  *sees meeting summary*                                          │
│                                                                  │
│  *clicks "Create Jira        Bot creates ticket:                │
│   Ticket" for action #1* ──▶ • Title from action item           │
│                               • Description with context        │
│                               • Links to meeting                │
│                               • Auto-assigns to mentioned user  │
│                                                                  │
│                             ◀──── ✅ Ticket MEET-123 created    │
│                                   [View in Jira]                │
│                                                                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━               │
│                                                                  │
│  CREATED TICKET:                                                 │
│  ┌────────────────────────────────────────────┐                 │
│  │ MEET-123                                   │                 │
│  │ Complete API documentation by Friday       │                 │
│  │                                            │                 │
│  │ Status: To Do                              │                 │
│  │ Assignee: John Smith                       │                 │
│  │ Labels: meeting-action-item                │                 │
│  └────────────────────────────────────────────┘                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 🔒 Security Features

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🔐 OAUTH 2.0                                                   │
│  ━━━━━━━━━━━━━━━━━━━━━                                         │
│  • No passwords stored                                           │
│  • Users login with their own accounts                          │
│  • Tokens are scoped (minimal permissions)                      │
│  • Users can revoke access anytime                              │
│                                                                  │
│  🔒 TOKEN ENCRYPTION                                            │
│  ━━━━━━━━━━━━━━━━━━━━━                                         │
│  • AES-256-GCM encryption at rest                               │
│  • Unique nonce per encryption                                  │
│  • Encrypted refresh tokens                                     │
│                                                                  │
│  ✅ WEBHOOK VERIFICATION                                        │
│  ━━━━━━━━━━━━━━━━━━━━━                                         │
│  • Zoom webhook signature validation                            │
│  • Slack request signing verification                           │
│  • Timestamp validation (prevent replay)                        │
│                                                                  │
│  🛡️ CSRF PROTECTION                                             │
│  ━━━━━━━━━━━━━━━━━━━━━                                         │
│  • State parameter in OAuth flow                                │
│  • State expires after 5 minutes                                │
│  • One-time use tokens                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 📈 Benefits & ROI

```
┌─────────────────────────────────────────────────────────────────┐
│                    BUSINESS VALUE                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ⏱️ TIME SAVINGS                                                │
│  ━━━━━━━━━━━━━━━━━━━━━                                         │
│  • 15-30 min saved per meeting (no manual notes)                │
│  • 5 min saved per action item (auto ticket creation)           │
│  • 10 min saved per follow-up (auto scheduling)                 │
│                                                                  │
│  📊 ESTIMATED SAVINGS                                           │
│  ━━━━━━━━━━━━━━━━━━━━━                                         │
│  • 10 meetings/week × 20 min = 200 min/week                     │
│  • 800 min/month = 13+ hours saved per person                   │
│                                                                  │
│  ✅ ACCOUNTABILITY                                              │
│  ━━━━━━━━━━━━━━━━━━━━━                                         │
│  • No action items lost                                          │
│  • Clear ownership (auto-assignment)                            │
│  • Tracked in Jira (reporting)                                  │
│                                                                  │
│  📝 DOCUMENTATION                                               │
│  ━━━━━━━━━━━━━━━━━━━━━                                         │
│  • Searchable meeting history                                   │
│  • Context preserved in tickets                                 │
│  • Decisions documented automatically                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 🎯 Summary

## What We Built

✅ **AI-Powered Meeting Bot** that automatically:
- Processes Zoom meeting recordings
- Generates intelligent summaries using GPT-4
- Extracts action items with assignees
- Posts rich notifications to Slack
- Creates Jira tickets with one click
- Schedules follow-up meetings

## Key Technical Achievements

✅ **OAuth-based authentication** - No shared secrets
✅ **Secure token storage** - AES-256 encryption
✅ **Production-ready** - Docker, health checks, logging
✅ **Extensible** - Clean architecture, easy to add integrations

## Get Started

```bash
git clone <repository>
cd ai-meeting-bot-python
python run.py
```

Then mention `@MeetingBot setup` in Slack!

---

# 🙋 Questions?

## Resources

- 📖 **Documentation**: `/docs/README.md`
- 🐛 **Issues**: GitHub Issues
- 💬 **Support**: #meeting-bot-support

## Contact

- 📧 Email: team@example.com
- 💼 Slack: @meeting-bot-team

---

*Thank you!*
