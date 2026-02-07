---
name: research-specialist
description: Gather information from web searches, URLs, and library documentation. Use when the task requires looking up APIs, researching topics, fetching documentation, or analyzing data files.
---

# Research Specialist

Execute research operations using `scripts/research_ops.py`.

## Commands

### Web Search
```bash
uv run python .claude/skills/research-specialist/scripts/research_ops.py search "<query>" -n 5
```

### Fetch URL
```bash
uv run python .claude/skills/research-specialist/scripts/research_ops.py fetch "<url>"
```

### Library Documentation
```bash
uv run python .claude/skills/research-specialist/scripts/research_ops.py docs <library> -t "<topic>"
```

### Summarize Content
```bash
uv run python .claude/skills/research-specialist/scripts/research_ops.py summarize "<content>" -m 200
```

### Analyze Data
```bash
uv run python .claude/skills/research-specialist/scripts/research_ops.py analyze <file_path> -t basic
```

## Workflow

1. Search for initial information
2. Fetch specific URLs for details
3. Look up library docs when coding
4. Summarize findings
