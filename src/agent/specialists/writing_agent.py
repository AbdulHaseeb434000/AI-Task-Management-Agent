"""Writing Agent - Specialist for content creation and editing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents import Agent, function_tool


@function_tool
def draft_document(
    title: str,
    content_type: str,
    outline: list[str] = None,
    tone: str = "professional",
) -> dict:
    """Draft a new document.

    Args:
        title: Document title
        content_type: Type (article, report, documentation, email, proposal)
        outline: Optional outline of sections
        tone: Writing tone (professional, casual, technical, persuasive)

    Returns:
        Drafted document content
    """
    return {
        "status": "success",
        "title": title,
        "content_type": content_type,
        "tone": tone,
        "content": "",
        "word_count": 0,
    }


@function_tool
def edit_content(
    content: str,
    edit_type: str,
    instructions: str = None,
) -> dict:
    """Edit existing content.

    Args:
        content: The content to edit
        edit_type: Type of edit (grammar, clarity, tone, shorten, expand)
        instructions: Specific editing instructions

    Returns:
        Edited content with change summary
    """
    return {
        "status": "success",
        "edit_type": edit_type,
        "original_length": len(content.split()),
        "edited_content": "",
        "changes_made": [],
    }


@function_tool
def format_document(
    content: str,
    format_type: str,
) -> dict:
    """Format content for a specific output.

    Args:
        content: The content to format
        format_type: Target format (markdown, html, plain_text, rst)

    Returns:
        Formatted content
    """
    return {
        "status": "success",
        "format": format_type,
        "formatted_content": content,
    }


@function_tool
def proofread(
    content: str,
    check_level: str = "standard",
) -> dict:
    """Proofread content for errors.

    Args:
        content: The content to proofread
        check_level: Level of checking (basic, standard, thorough)

    Returns:
        Proofread results with corrections
    """
    return {
        "status": "success",
        "check_level": check_level,
        "errors_found": 0,
        "corrections": [],
        "suggestions": [],
    }


@function_tool
def generate_outline(
    topic: str,
    content_type: str,
    depth: int = 2,
) -> dict:
    """Generate an outline for content.

    Args:
        topic: The topic to outline
        content_type: Type of content being planned
        depth: Outline depth (1-3)

    Returns:
        Generated outline structure
    """
    return {
        "status": "success",
        "topic": topic,
        "content_type": content_type,
        "outline": [],
    }


WRITING_AGENT_INSTRUCTIONS = """You are a Writing Agent specialized in content creation and editing.

## Capabilities

- **Draft Documents**: Create new content from scratch
- **Edit Content**: Improve existing text
- **Format**: Convert between formats
- **Proofread**: Check for errors
- **Outline**: Plan content structure

## Content Types

- Technical documentation
- Reports and proposals
- Articles and blog posts
- API documentation
- User guides
- README files

## Guidelines

1. Match tone and style to the context
2. Use clear, concise language
3. Structure content logically
4. Include examples where helpful
5. Maintain consistency throughout

## Writing Process

1. Understand the purpose and audience
2. Create or review the outline
3. Draft the content
4. Edit for clarity and flow
5. Proofread for errors

## When Done

After completing writing:
1. Provide the final content
2. Note the word count
3. Summarize key sections
4. List any assumptions made

Write for clarity. Good writing is rewriting.
"""


def create_writing_agent() -> Agent:
    """Create the writing specialist agent."""
    return Agent(
        name="Writing Agent",
        instructions=WRITING_AGENT_INSTRUCTIONS,
        model="gpt-4o",
        tools=[
            draft_document,
            edit_content,
            format_document,
            proofread,
            generate_outline,
        ],
    )


# Alias for consistency
WritingAgent = create_writing_agent
