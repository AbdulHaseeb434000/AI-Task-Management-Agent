"""Tests for the SDK-native guardrails module.

These tests focus on:
1. Delegation guardrails (synchronous, testable without LLM)
2. Guardrail agent instructions (verify they exist and are configured)
3. Helper functions
"""

import pytest
from src.agent.guardrails import (
    # Delegation guardrails
    DelegationGuardrails,
    create_safe_delegation,
    # Guardrail agents
    input_guardrail_agent,
    output_guardrail_agent,
    INPUT_GUARDRAIL_INSTRUCTIONS,
    OUTPUT_GUARDRAIL_INSTRUCTIONS,
    # Guardrail functions
    INPUT_GUARDRAILS,
    OUTPUT_GUARDRAILS,
    _extract_text_from_input,
)


class TestDelegationGuardrails:
    """Test DelegationGuardrails class."""

    def test_create_delegation_context_basic(self):
        """Test creating basic delegation context."""
        context = DelegationGuardrails.create_delegation_context(
            task_description="Fix the bug in auth.py",
            required_files=["src/auth.py"],
            constraints=["Don't change the API"],
            output_requirements="Return fixed code",
        )

        assert context["task"] == "Fix the bug in auth.py"
        assert context["files"] == ["src/auth.py"]
        assert context["constraints"] == ["Don't change the API"]
        assert context["output_requirements"] == "Return fixed code"

    def test_create_delegation_context_defaults(self):
        """Test delegation context with defaults."""
        context = DelegationGuardrails.create_delegation_context(
            task_description="Simple task",
        )

        assert context["task"] == "Simple task"
        assert context["files"] == []
        assert context["constraints"] == []
        assert "Return a clear summary" in context["output_requirements"]

    def test_long_task_truncated(self):
        """Test long task description is truncated."""
        long_task = "a" * 10000
        context = DelegationGuardrails.create_delegation_context(
            task_description=long_task,
        )

        assert len(context["task"]) <= DelegationGuardrails.MAX_TASK_DESCRIPTION + 3
        assert context["task"].endswith("...")

    def test_forbidden_fields_filtered(self):
        """Test forbidden fields are filtered from additional context."""
        context = DelegationGuardrails.create_delegation_context(
            task_description="Test task",
            additional_context={
                "safe_field": "allowed",
                "user_password": "should be filtered",
                "api_keys": "should be filtered",
                "another_safe": "allowed",
                "learned_patterns": "should be filtered",
                "system_prompts": "should be filtered",
            },
        )

        additional = context.get("additional", {})
        assert "safe_field" in additional
        assert "another_safe" in additional
        assert "user_password" not in additional
        assert "api_keys" not in additional
        assert "learned_patterns" not in additional
        assert "system_prompts" not in additional

    def test_validate_delegation_clean(self):
        """Test validating clean delegation context."""
        context = {
            "task": "Fix bug",
            "files": ["test.py"],
        }
        is_valid, message = DelegationGuardrails.validate_delegation(context)
        assert is_valid is True
        assert "validated" in message.lower()

    def test_validate_delegation_with_forbidden_fields(self):
        """Test validating delegation with forbidden fields."""
        context = {
            "task": "Fix bug",
            "learned_patterns": ["should not be here"],
        }
        is_valid, message = DelegationGuardrails.validate_delegation(context)
        assert is_valid is False
        assert "blocked" in message.lower()

    def test_validate_delegation_nested_forbidden(self):
        """Test validating delegation with nested forbidden fields."""
        context = {
            "task": "Fix bug",
            "nested": {
                "user_password": "secret",
            },
        }
        is_valid, message = DelegationGuardrails.validate_delegation(context)
        assert is_valid is False
        assert "blocked" in message.lower()


class TestCreateSafeDelegation:
    """Test create_safe_delegation convenience function."""

    def test_basic_delegation(self):
        """Test basic safe delegation creation."""
        context = create_safe_delegation(
            task="Write tests",
            files=["test.py"],
            constraints=["Use pytest"],
            output_format="Return test results",
        )

        assert context["task"] == "Write tests"
        assert context["files"] == ["test.py"]
        assert context["constraints"] == ["Use pytest"]
        assert context["output_requirements"] == "Return test results"

    def test_minimal_delegation(self):
        """Test minimal delegation with only task."""
        context = create_safe_delegation(task="Simple task")

        assert context["task"] == "Simple task"
        assert context["files"] == []
        assert context["constraints"] == []


class TestGuardrailAgents:
    """Test guardrail agent configurations."""

    def test_input_guardrail_agent_exists(self):
        """Test input guardrail agent is configured."""
        assert input_guardrail_agent is not None
        assert input_guardrail_agent.name == "InputGuardrail"
        assert input_guardrail_agent.model == "gpt-4o-mini"

    def test_output_guardrail_agent_exists(self):
        """Test output guardrail agent is configured."""
        assert output_guardrail_agent is not None
        assert output_guardrail_agent.name == "OutputGuardrail"
        assert output_guardrail_agent.model == "gpt-4o-mini"

    def test_input_guardrail_instructions_comprehensive(self):
        """Test input guardrail instructions cover key threats."""
        instructions = INPUT_GUARDRAIL_INSTRUCTIONS.lower()

        # Should cover prompt injection
        assert "injection" in instructions
        assert "ignore" in instructions or "override" in instructions

        # Should cover dangerous actions
        assert "dangerous" in instructions
        assert "delete" in instructions or "system files" in instructions

        # Should cover social engineering
        assert "social engineering" in instructions

        # Should cover data exfiltration
        assert "exfiltration" in instructions

        # Should have JSON response format
        assert "json" in instructions
        assert "is_threat" in instructions

    def test_output_guardrail_instructions_comprehensive(self):
        """Test output guardrail instructions cover key issues."""
        instructions = OUTPUT_GUARDRAIL_INSTRUCTIONS.lower()

        # Should cover sensitive data
        assert "sensitive" in instructions
        assert "api key" in instructions or "password" in instructions

        # Should cover dangerous instructions
        assert "dangerous" in instructions

        # Should cover privacy
        assert "privacy" in instructions

        # Should have JSON response format
        assert "json" in instructions
        assert "is_unsafe" in instructions


class TestGuardrailLists:
    """Test guardrail function lists."""

    def test_input_guardrails_list(self):
        """Test INPUT_GUARDRAILS list is configured."""
        assert INPUT_GUARDRAILS is not None
        assert len(INPUT_GUARDRAILS) > 0
        # Should contain the detect_malicious_input function
        assert any("malicious" in str(g) for g in INPUT_GUARDRAILS)

    def test_output_guardrails_list(self):
        """Test OUTPUT_GUARDRAILS list is configured."""
        assert OUTPUT_GUARDRAILS is not None
        assert len(OUTPUT_GUARDRAILS) > 0
        # Should contain the detect_unsafe_output function
        assert any("unsafe" in str(g) for g in OUTPUT_GUARDRAILS)


class TestExtractTextFromInput:
    """Test the _extract_text_from_input helper."""

    def test_extract_from_string(self):
        """Test extracting text from string input."""
        result = _extract_text_from_input("Hello world")
        assert result == "Hello world"

    def test_extract_from_list_of_dicts(self):
        """Test extracting text from list of dict items."""
        input_data = [
            {"content": "First message"},
            {"content": "Second message"},
        ]
        result = _extract_text_from_input(input_data)
        assert "First message" in result
        assert "Second message" in result

    def test_extract_from_list_with_nested_content(self):
        """Test extracting text from nested content structure."""
        input_data = [
            {
                "content": [
                    {"text": "Nested text 1"},
                    {"text": "Nested text 2"},
                ]
            },
        ]
        result = _extract_text_from_input(input_data)
        assert "Nested text 1" in result
        assert "Nested text 2" in result

    def test_extract_from_list_of_strings(self):
        """Test extracting text from list of strings."""
        input_data = ["Hello", "World"]
        result = _extract_text_from_input(input_data)
        assert "Hello" in result
        assert "World" in result

    def test_extract_handles_empty_list(self):
        """Test extracting from empty list."""
        result = _extract_text_from_input([])
        assert result == ""


class TestForbiddenFieldsList:
    """Test the forbidden fields configuration."""

    def test_forbidden_fields_contains_sensitive_items(self):
        """Test forbidden fields list contains sensitive items."""
        forbidden = DelegationGuardrails.FORBIDDEN_FIELDS

        # Memory-related
        assert "learned_patterns" in forbidden
        assert "user_preferences" in forbidden
        assert "full_conversation_history" in forbidden

        # Security-related
        assert "user_password" in forbidden
        assert "api_keys" in forbidden
        assert "auth_tokens" in forbidden
        assert "session_secrets" in forbidden

        # System-related
        assert "system_prompts" in forbidden
        assert "internal_config" in forbidden
