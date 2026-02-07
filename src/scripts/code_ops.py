#!/usr/bin/env python3
"""Code operations script - write, analyze, test, debug, refactor code."""

import argparse
import json
import sys
from pathlib import Path


def write_code(file_path: str, language: str, description: str) -> dict:
    """Generate code skeleton for a file."""
    path = Path(file_path)

    # Language-specific templates
    templates = {
        "python": f'"""{description}"""\n\n# TODO: Implement\n',
        "javascript": f"// {description}\n\n// TODO: Implement\n",
        "typescript": f"// {description}\n\n// TODO: Implement\n",
    }

    content = templates.get(language, f"// {description}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

    return {"status": "created", "path": str(path), "language": language}


def analyze_code(file_path: str) -> dict:
    """Analyze code structure and patterns."""
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    content = path.read_text()
    lines = content.splitlines()

    return {
        "status": "success",
        "path": str(path),
        "lines": len(lines),
        "characters": len(content),
        "has_imports": any("import" in line for line in lines[:20]),
        "has_functions": "def " in content or "function " in content,
        "has_classes": "class " in content,
    }


def run_tests(test_path: str, framework: str = "pytest") -> dict:
    """Run tests using specified framework."""
    import subprocess

    cmd = {
        "pytest": ["uv", "run", "pytest", test_path, "-v"],
        "unittest": ["uv", "run", "python", "-m", "unittest", test_path],
    }.get(framework, ["uv", "run", "pytest", test_path])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return {
            "status": "passed" if result.returncode == 0 else "failed",
            "output": result.stdout,
            "errors": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "message": "Tests timed out after 5 minutes"}


def debug_error(error_message: str, file_path: str = None) -> dict:
    """Analyze an error message and suggest fixes."""
    suggestions = []

    if "ModuleNotFoundError" in error_message or "ImportError" in error_message:
        suggestions.append("Install missing package with: uv add <package>")
    if "SyntaxError" in error_message:
        suggestions.append("Check for missing colons, brackets, or quotes")
    if "IndentationError" in error_message:
        suggestions.append("Fix indentation - use consistent spaces or tabs")
    if "TypeError" in error_message:
        suggestions.append("Check function arguments and types")
    if "AttributeError" in error_message:
        suggestions.append("Verify object has the attribute; check for typos")

    return {
        "status": "analyzed",
        "suggestions": suggestions or ["Review the error traceback carefully"],
        "file": file_path,
    }


def refactor(file_path: str, refactor_type: str) -> dict:
    """Suggest refactoring for code."""
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    content = path.read_text()
    suggestions = []

    if refactor_type == "extract_function":
        if content.count("\n") > 50:
            suggestions.append("Consider breaking long functions into smaller ones")
    elif refactor_type == "rename":
        suggestions.append("Use descriptive names that explain purpose")
    elif refactor_type == "simplify":
        if "if " in content and "else" in content:
            suggestions.append("Consider using early returns to reduce nesting")

    return {
        "status": "success",
        "refactor_type": refactor_type,
        "suggestions": suggestions,
    }


def main():
    parser = argparse.ArgumentParser(description="Code operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # write command
    write_parser = subparsers.add_parser("write", help="Write code to file")
    write_parser.add_argument("file_path", help="Output file path")
    write_parser.add_argument("--language", "-l", default="python")
    write_parser.add_argument("--description", "-d", default="New file")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze code")
    analyze_parser.add_argument("file_path", help="File to analyze")

    # test command
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument("test_path", help="Test file or directory")
    test_parser.add_argument("--framework", "-f", default="pytest")

    # debug command
    debug_parser = subparsers.add_parser("debug", help="Debug error")
    debug_parser.add_argument("error_message", help="Error message to analyze")
    debug_parser.add_argument("--file", "-f", help="Related file")

    # refactor command
    refactor_parser = subparsers.add_parser("refactor", help="Suggest refactoring")
    refactor_parser.add_argument("file_path", help="File to refactor")
    refactor_parser.add_argument("--type", "-t", default="simplify",
                                  choices=["extract_function", "rename", "simplify"])

    args = parser.parse_args()

    if args.command == "write":
        result = write_code(args.file_path, args.language, args.description)
    elif args.command == "analyze":
        result = analyze_code(args.file_path)
    elif args.command == "test":
        result = run_tests(args.test_path, args.framework)
    elif args.command == "debug":
        result = debug_error(args.error_message, args.file)
    elif args.command == "refactor":
        result = refactor(args.file_path, args.type)
    else:
        result = {"error": "Unknown command"}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
