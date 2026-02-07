---
name: code-specialist
description: Handle programming tasks including writing code, analyzing codebases, running tests, debugging errors, and refactoring. Use when the task involves creating files, fixing bugs, improving code quality, or executing test suites.
---

# Code Specialist

Execute code operations using `src/scripts/code_ops.py`.

## Commands

### Write Code
```bash
uv run python src/scripts/code_ops.py write <file_path> -l <language> -d "<description>"
```

### Analyze Code
```bash
uv run python src/scripts/code_ops.py analyze <file_path>
```

### Run Tests
```bash
uv run python src/scripts/code_ops.py test <test_path> -f pytest
```

### Debug Error
```bash
uv run python src/scripts/code_ops.py debug "<error_message>" -f <file_path>
```

### Refactor
```bash
uv run python src/scripts/code_ops.py refactor <file_path> -t <type>
```
Types: `extract_function`, `rename`, `simplify`

## Workflow

1. Analyze existing code first to understand structure
2. Make targeted changes - avoid over-engineering
3. Run tests after modifications
4. Debug any failures
5. Refactor only when explicitly requested
