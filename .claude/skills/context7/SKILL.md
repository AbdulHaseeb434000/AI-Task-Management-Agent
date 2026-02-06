---
name: context7
description: Fetch up-to-date library documentation via Context7 API. Use when (1) writing code with external libraries/frameworks and need current API docs, (2) uncertain about current API signatures or patterns, (3) setting up or configuring frameworks, (4) need version-specific documentation beyond training data cutoff, (5) verifying best practices for any library. Triggers on questions like "how do I use X library", "what's the current API for Y", or when implementing features with external dependencies.
---

# Context7 Documentation Fetcher

Retrieves current, version-specific documentation for any programming library or framework.

## Workflow

### Step 1: Search for the Library

```bash
python3 scripts/context7.py search "<library-name>"
```

Returns library metadata including the `id` field needed for Step 2.

### Step 2: Fetch Documentation

```bash
python3 scripts/context7.py context "<library-id>" "<query>"
```

**Options:**
- `--type txt|md` — Output format (default: txt)
- `--tokens N` — Limit response tokens (default: 5000)

## Examples

**Find and query React:**
```bash
python3 scripts/context7.py search "react"
python3 scripts/context7.py context "/facebook/react" "useEffect cleanup patterns"
```

**Find and query Next.js:**
```bash
python3 scripts/context7.py search "next.js"
python3 scripts/context7.py context "/vercel/next.js" "app router middleware"
```

**Find and query FastAPI:**
```bash
python3 scripts/context7.py search "fastapi"
python3 scripts/context7.py context "/tiangolo/fastapi" "dependency injection"
```

## Quick Reference

| Library | ID | Example Query |
|---------|-----|---------------|
| React | `/facebook/react` | `"hooks useCallback useMemo"` |
| Next.js | `/vercel/next.js` | `"app router dynamic routes"` |
| FastAPI | `/tiangolo/fastapi` | `"oauth2 jwt authentication"` |
| Prisma | `/prisma/prisma` | `"relations one to many"` |

## MCP Alternative

For persistent integration without running scripts:

```bash
claude mcp add context7 -- npx -y @upstash/context7-mcp@latest
```
