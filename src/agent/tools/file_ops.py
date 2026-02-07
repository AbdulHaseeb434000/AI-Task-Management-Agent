"""File operation tools - shared across all agents."""

from pathlib import Path
from agents import function_tool


@function_tool
def read_file(file_path: str) -> dict:
    """Read the contents of a file.

    Args:
        file_path: Path to the file to read (absolute or relative to project root)

    Returns:
        File contents and metadata
    """
    try:
        path = Path(file_path)
        if not path.is_absolute():
            # Resolve relative to project root
            path = Path(__file__).parent.parent.parent.parent / file_path

        if not path.exists():
            return {
                "status": "error",
                "error": f"File not found: {file_path}",
            }

        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()

        return {
            "status": "success",
            "path": str(path),
            "content": content,
            "line_count": len(lines),
            "size_bytes": len(content.encode("utf-8")),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@function_tool
def write_file(file_path: str, content: str, create_dirs: bool = True) -> dict:
    """Write content to a file.

    Args:
        file_path: Path to the file to write (absolute or relative to project root)
        content: Content to write to the file
        create_dirs: Create parent directories if they don't exist

    Returns:
        Write operation status
    """
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(__file__).parent.parent.parent.parent / file_path

        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content, encoding="utf-8")

        return {
            "status": "success",
            "path": str(path),
            "bytes_written": len(content.encode("utf-8")),
            "line_count": len(content.splitlines()),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@function_tool
def append_file(file_path: str, content: str) -> dict:
    """Append content to a file.

    Args:
        file_path: Path to the file to append to
        content: Content to append

    Returns:
        Append operation status
    """
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(__file__).parent.parent.parent.parent / file_path

        if not path.exists():
            return {
                "status": "error",
                "error": f"File not found: {file_path}",
            }

        with open(path, "a", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "success",
            "path": str(path),
            "bytes_appended": len(content.encode("utf-8")),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@function_tool
def list_files(directory: str, pattern: str = "*") -> dict:
    """List files in a directory.

    Args:
        directory: Directory path to list
        pattern: Glob pattern to filter files (default: "*")

    Returns:
        List of files matching the pattern
    """
    try:
        path = Path(directory)
        if not path.is_absolute():
            path = Path(__file__).parent.parent.parent.parent / directory

        if not path.exists():
            return {
                "status": "error",
                "error": f"Directory not found: {directory}",
            }

        if not path.is_dir():
            return {
                "status": "error",
                "error": f"Not a directory: {directory}",
            }

        files = list(path.glob(pattern))
        file_list = []
        for f in sorted(files):
            file_list.append({
                "name": f.name,
                "path": str(f),
                "is_dir": f.is_dir(),
                "size": f.stat().st_size if f.is_file() else None,
            })

        return {
            "status": "success",
            "directory": str(path),
            "pattern": pattern,
            "count": len(file_list),
            "files": file_list,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }
