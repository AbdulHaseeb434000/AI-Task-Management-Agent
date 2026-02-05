# AI Task Management Agent

## Project Overview

An intelligent AI-powered task management assistant that helps users manage their tasks autonomously. Built with Python, FastAPI, and the OpenAI Agents SDK.

## Tech Stack

- **Language**: Python 3.11
- **Package Manager**: uv
- **Framework**: FastAPI
- **AI SDK**: openai-agents

## Key Commands

```bash
# Install dependencies
uv sync

# Run the server
uv run main.py

# Run tests (when available)
uv run pytest
```

## Architecture

This project follows a **skills-based architecture**:

- **Skills** are loaded on-demand, not all at once
- **Memory** is tiered (hot/warm/cold) to minimize context overhead
- **Task Graph** is managed internally but presented simply to users
- **Approval Queue** controls which actions need user confirmation

See `spec.md` for the complete architecture specification.

## Project Structure (Planned)

```
ai-task-management-agent/
├── main.py                 # FastAPI entry point
├── src/
│   ├── agent/              # Core agent layer
│   ├── skills/             # Skills system
│   ├── memory/             # Memory management
│   ├── tasks/              # Task management
│   └── api/                # API routes
├── .claude/
│   └── skills/             # Claude Code skills
└── spec.md                 # Architecture specification
```

## Development Guidelines

- Use type hints for all functions
- Follow PEP 8 style guidelines
- Write tests for new features
- Keep functions small and focused
- Document complex logic with comments

## Current Status

- [x] Project initialized with uv
- [x] FastAPI server with root endpoint
- [x] Architecture specification complete
- [ ] Core agent implementation
- [ ] Skills system implementation
- [ ] Database setup
- [ ] API endpoints
