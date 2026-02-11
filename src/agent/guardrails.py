"""Input and Output Guardrails for the Agent System.

Provides validation, sanitization, and safety checks for:
- User input before reaching the orchestrator
- Agent output before returning to the user
- Task delegation to specialist agents
"""

import re
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class GuardrailResult(Enum):
    """Result of a guardrail check."""
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class GuardrailCheck:
    """Result of a guardrail check."""
    result: GuardrailResult
    message: str
    original_content: str
    sanitized_content: Optional[str] = None
    violations: List[str] = field(default_factory=list)


class InputGuardrails:
    """Guardrails for user input validation and sanitization."""

    # Maximum input length (tokens are ~4 chars on average)
    MAX_INPUT_LENGTH = 10000

    # Patterns that indicate potential prompt injection
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"forget\s+(all\s+)?previous\s+(instructions|context)",
        r"you\s+are\s+now\s+a",
        r"new\s+instructions?:",
        r"system\s*:\s*",
        r"<\s*system\s*>",
        r"\[INST\]",
        r"<<SYS>>",
    ]

    # Patterns for sensitive data that should be flagged
    SENSITIVE_PATTERNS = [
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email"),
        (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "phone"),
        (r"\b\d{3}[-]?\d{2}[-]?\d{4}\b", "ssn"),
        (r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b", "credit_card"),
        (r"(?i)(password|passwd|pwd)\s*[=:]\s*\S+", "password"),
        (r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[=:]\s*\S+", "api_key"),
    ]

    # Dangerous command patterns
    DANGEROUS_PATTERNS = [
        r"rm\s+-rf\s+[/~]",
        r"sudo\s+rm",
        r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;",  # Fork bomb
        r"dd\s+if=.*of=/dev/",
        r"mkfs\.",
        r">\s*/dev/sd[a-z]",
    ]

    def __init__(self, strict_mode: bool = False):
        """Initialize guardrails.

        Args:
            strict_mode: If True, block on warnings instead of just flagging.
        """
        self.strict_mode = strict_mode
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        self._injection_re = [
            re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS
        ]
        self._sensitive_re = [
            (re.compile(p, re.IGNORECASE), name)
            for p, name in self.SENSITIVE_PATTERNS
        ]
        self._dangerous_re = [
            re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_PATTERNS
        ]

    def check(self, user_input: str) -> GuardrailCheck:
        """Run all input guardrails.

        Args:
            user_input: The raw user input.

        Returns:
            GuardrailCheck with result and any sanitization applied.
        """
        violations = []
        result = GuardrailResult.PASS
        sanitized = user_input

        # Check length
        if len(user_input) > self.MAX_INPUT_LENGTH:
            violations.append(f"Input exceeds maximum length ({len(user_input)} > {self.MAX_INPUT_LENGTH})")
            result = GuardrailResult.BLOCK
            sanitized = user_input[:self.MAX_INPUT_LENGTH]

        # Check for empty input
        if not user_input.strip():
            return GuardrailCheck(
                result=GuardrailResult.BLOCK,
                message="Empty input",
                original_content=user_input,
                violations=["Input is empty or whitespace only"],
            )

        # Check for injection attempts
        for pattern in self._injection_re:
            if pattern.search(user_input):
                violations.append(f"Potential prompt injection detected: {pattern.pattern}")
                result = GuardrailResult.BLOCK

        # Check for dangerous commands
        for pattern in self._dangerous_re:
            if pattern.search(user_input):
                violations.append(f"Dangerous command pattern detected: {pattern.pattern}")
                result = GuardrailResult.BLOCK

        # Check for sensitive data (warn, don't block)
        for pattern, data_type in self._sensitive_re:
            if pattern.search(user_input):
                violations.append(f"Sensitive data detected: {data_type}")
                if result == GuardrailResult.PASS:
                    result = GuardrailResult.WARN

        # Generate message
        if result == GuardrailResult.BLOCK:
            message = f"Input blocked: {'; '.join(violations)}"
        elif result == GuardrailResult.WARN:
            message = f"Input flagged: {'; '.join(violations)}"
        else:
            message = "Input validated"

        return GuardrailCheck(
            result=result,
            message=message,
            original_content=user_input,
            sanitized_content=sanitized if sanitized != user_input else None,
            violations=violations,
        )


class OutputGuardrails:
    """Guardrails for agent output validation."""

    # Maximum output length
    MAX_OUTPUT_LENGTH = 50000

    # Patterns that should never appear in output
    FORBIDDEN_OUTPUT_PATTERNS = [
        r"(?i)my\s+api\s+key\s+is",
        r"(?i)my\s+password\s+is",
        r"(?i)internal\s+system\s+prompt",
        r"(?i)you\s+are\s+an?\s+ai\s+(assistant|language\s+model)",
    ]

    # Patterns indicating potential hallucination markers
    HALLUCINATION_MARKERS = [
        r"(?i)i\s+(cannot|can't)\s+verify",
        r"(?i)i\s+(don't|do\s+not)\s+have\s+access\s+to\s+real-time",
        r"(?i)as\s+of\s+my\s+(last\s+)?knowledge\s+cutoff",
    ]

    def __init__(self):
        """Initialize output guardrails."""
        self._forbidden_re = [
            re.compile(p) for p in self.FORBIDDEN_OUTPUT_PATTERNS
        ]
        self._hallucination_re = [
            re.compile(p) for p in self.HALLUCINATION_MARKERS
        ]

    def check(self, output: str) -> GuardrailCheck:
        """Run all output guardrails.

        Args:
            output: The agent's output.

        Returns:
            GuardrailCheck with result.
        """
        violations = []
        result = GuardrailResult.PASS
        sanitized = output

        # Check length
        if len(output) > self.MAX_OUTPUT_LENGTH:
            sanitized = output[:self.MAX_OUTPUT_LENGTH] + "\n\n[Output truncated]"
            violations.append("Output truncated due to length")
            result = GuardrailResult.WARN

        # Check for forbidden patterns
        for pattern in self._forbidden_re:
            if pattern.search(output):
                violations.append(f"Forbidden output pattern: {pattern.pattern}")
                result = GuardrailResult.BLOCK

        # Check for hallucination markers (just warn)
        for pattern in self._hallucination_re:
            if pattern.search(output):
                violations.append("Potential hallucination marker detected")
                if result == GuardrailResult.PASS:
                    result = GuardrailResult.WARN

        # Generate message
        if result == GuardrailResult.BLOCK:
            message = f"Output blocked: {'; '.join(violations)}"
        elif result == GuardrailResult.WARN:
            message = f"Output flagged: {'; '.join(violations)}"
        else:
            message = "Output validated"

        return GuardrailCheck(
            result=result,
            message=message,
            original_content=output,
            sanitized_content=sanitized if sanitized != output else None,
            violations=violations,
        )


class DelegationGuardrails:
    """Guardrails for task delegation to specialist agents.

    Ensures only necessary information is passed to specialists.
    """

    # Fields that should NEVER be passed to specialists
    FORBIDDEN_FIELDS = [
        "user_password",
        "api_keys",
        "auth_tokens",
        "session_secrets",
        "learned_patterns",  # Memory is orchestrator-only
        "user_preferences",  # Memory is orchestrator-only
        "full_conversation_history",
    ]

    # Maximum task description length for specialists
    MAX_TASK_DESCRIPTION = 5000

    @classmethod
    def create_delegation_context(
        cls,
        task_description: str,
        required_files: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None,
        output_requirements: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a sanitized context for delegation to specialist agents.

        Args:
            task_description: What the specialist needs to do.
            required_files: File paths the specialist needs to access.
            constraints: Any constraints or requirements.
            output_requirements: What output format is expected.
            additional_context: Any additional safe context.

        Returns:
            Sanitized delegation context dict.
        """
        # Truncate task description if needed
        if len(task_description) > cls.MAX_TASK_DESCRIPTION:
            task_description = task_description[:cls.MAX_TASK_DESCRIPTION] + "..."

        context = {
            "task": task_description,
            "files": required_files or [],
            "constraints": constraints or [],
            "output_requirements": output_requirements or "Return a clear summary of what was done.",
        }

        # Add additional context, filtering forbidden fields
        if additional_context:
            safe_context = {
                k: v for k, v in additional_context.items()
                if k.lower() not in [f.lower() for f in cls.FORBIDDEN_FIELDS]
            }
            context["additional"] = safe_context

        return context

    @classmethod
    def validate_delegation(cls, context: Dict[str, Any]) -> GuardrailCheck:
        """Validate a delegation context before sending to specialist.

        Args:
            context: The delegation context dict.

        Returns:
            GuardrailCheck with result.
        """
        violations = []
        result = GuardrailResult.PASS

        # Check for forbidden fields
        def check_dict(d: Dict, path: str = ""):
            for key, value in d.items():
                full_path = f"{path}.{key}" if path else key
                if key.lower() in [f.lower() for f in cls.FORBIDDEN_FIELDS]:
                    violations.append(f"Forbidden field in delegation: {full_path}")
                if isinstance(value, dict):
                    check_dict(value, full_path)

        check_dict(context)

        if violations:
            result = GuardrailResult.BLOCK
            message = f"Delegation blocked: {'; '.join(violations)}"
        else:
            message = "Delegation validated"

        return GuardrailCheck(
            result=result,
            message=message,
            original_content=str(context),
            violations=violations,
        )


# Global instances
input_guardrails = InputGuardrails()
output_guardrails = OutputGuardrails()
delegation_guardrails = DelegationGuardrails()


def validate_input(user_input: str) -> Tuple[bool, str, Optional[str]]:
    """Convenience function to validate user input.

    Args:
        user_input: The raw user input.

    Returns:
        Tuple of (is_valid, message, sanitized_input_or_none).
    """
    check = input_guardrails.check(user_input)
    is_valid = check.result != GuardrailResult.BLOCK
    return is_valid, check.message, check.sanitized_content


def validate_output(output: str) -> Tuple[bool, str, Optional[str]]:
    """Convenience function to validate agent output.

    Args:
        output: The agent's output.

    Returns:
        Tuple of (is_valid, message, sanitized_output_or_none).
    """
    check = output_guardrails.check(output)
    is_valid = check.result != GuardrailResult.BLOCK
    sanitized = check.sanitized_content if check.sanitized_content else output
    return is_valid, check.message, sanitized


def create_safe_delegation(
    task: str,
    files: Optional[List[str]] = None,
    constraints: Optional[List[str]] = None,
    output_format: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a safe delegation context for specialist agents.

    Args:
        task: Task description for the specialist.
        files: Files the specialist needs.
        constraints: Any constraints.
        output_format: Expected output format.

    Returns:
        Safe delegation context dict.
    """
    return delegation_guardrails.create_delegation_context(
        task_description=task,
        required_files=files,
        constraints=constraints,
        output_requirements=output_format,
    )
