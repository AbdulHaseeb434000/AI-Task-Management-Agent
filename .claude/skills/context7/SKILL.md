---
name: context7
description: Fetch up-to-date library documentation via Context7 API. Use when working with external libraries, frameworks, or APIs to get current documentation beyond training data cutoff.
---

# Context7 Documentation Fetcher

Retrieves current, version-specific documentation for any programming library or framework via the Context7 API.

## When to Use

Activate this skill when:
- Writing code using external libraries/frameworks
- Seeking current API documentation or references
- Setting up or configuring frameworks
- Needing code examples with specific packages
- Uncertain about current API signatures
- Verifying best practices for a library

## Workflow

### Step 1: Search for the Library

Find the Context7 library ID:

```bash
python3 .claude/skills/context7/scripts/context7.py search "<library-name>"
```

**Examples:**
```bash
python3 .claude/skills/context7/scripts/context7.py search "next.js"
python3 .claude/skills/context7/scripts/context7.py search "react"
python3 .claude/skills/context7/scripts/context7.py search "fastapi"
```

This returns library metadata including the `id` field needed for Step 2.

### Step 2: Fetch Documentation

Get documentation for your specific query:

```bash
python3 .claude/skills/context7/scripts/context7.py context "<library-id>" "<query>"
```

**Examples:**
```bash
python3 .claude/skills/context7/scripts/context7.py context "/vercel/next.js" "app router middleware"
python3 .claude/skills/context7/scripts/context7.py context "/facebook/react" "useEffect cleanup patterns"
python3 .claude/skills/context7/scripts/context7.py context "/tiangolo/fastapi" "dependency injection"
```

**Options:**
- `--type txt|md` — Output format (default: txt)
- `--tokens N` — Limit response tokens (default: 5000)

## Quick Reference

| Task | Command |
|------|---------|
| Find React docs | `search "react"` |
| Get React hooks info | `context "/facebook/react" "hooks useCallback useMemo"` |
| Find Next.js | `search "next.js"` |
| Get Next.js routing | `context "/vercel/next.js" "app router dynamic routes"` |
| Find FastAPI | `search "fastapi"` |
| Get FastAPI auth | `context "/tiangolo/fastapi" "oauth2 jwt authentication"` |
| Find Prisma | `search "prisma"` |
| Get Prisma relations | `context "/prisma/prisma" "relations one to many"` |

## MCP Server Alternative

For persistent integration, install Context7 as an MCP server:

```bash
claude mcp add context7 -- npx -y @upstash/context7-mcp@latest
```

Then use `use context7` in prompts to automatically fetch docs.

## Why Use This

- Training data has knowledge cutoffs - this fetches **current** documentation
- Eliminates hallucinated APIs that no longer exist
- Gets version-specific information
- Provides working code examples from official docs
