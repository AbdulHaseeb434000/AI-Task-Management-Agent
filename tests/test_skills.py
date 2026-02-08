"""Tests for skills module."""

import pytest
import uuid

from src.skills.base import (
    SkillContext,
    SkillResult,
    SkillManifest,
    SkillCategory,
    PermissionLevel,
    LoadStrategy,
)


class TestSkillContext:
    """Tests for SkillContext."""

    def test_create_context(self):
        """Test creating a skill context."""
        user_id = str(uuid.uuid4())
        context = SkillContext(
            user_id=user_id,
            parameters={"action": "test"},
        )

        assert context.user_id == user_id
        assert context.parameters == {"action": "test"}
        assert context.session_id is None

    def test_context_with_session(self):
        """Test context with session ID."""
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        context = SkillContext(
            user_id=user_id,
            session_id=session_id,
            parameters={},
        )

        assert context.session_id == session_id


class TestSkillResult:
    """Tests for SkillResult."""

    def test_success_result(self):
        """Test successful result."""
        result = SkillResult(
            success=True,
            data={"items": [1, 2, 3]},
        )

        assert result.success is True
        assert result.data == {"items": [1, 2, 3]}
        assert result.error is None

    def test_error_result(self):
        """Test error result."""
        result = SkillResult(
            success=False,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.data is None

    def test_result_with_approval(self):
        """Test result requiring approval."""
        result = SkillResult(
            success=True,
            requires_approval=True,
            approval_id="approval-123",
        )

        assert result.requires_approval is True
        assert result.approval_id == "approval-123"


class TestSkillManifest:
    """Tests for SkillManifest."""

    def test_create_manifest(self):
        """Test creating a skill manifest."""
        manifest = SkillManifest(
            name="test_skill",
            description="A test skill",
            version="1.0.0",
            category=SkillCategory.INTERNAL,
            triggers=["test", "demo"],
            permission_level=PermissionLevel.INTERNAL,
            approval_required=False,
            load_strategy=LoadStrategy.EAGER,
        )

        assert manifest.name == "test_skill"
        assert manifest.category == SkillCategory.INTERNAL
        assert "test" in manifest.triggers
        assert manifest.approval_required is False

    def test_manifest_with_parameters(self):
        """Test manifest with parameter definitions."""
        manifest = SkillManifest(
            name="parameterized_skill",
            description="Skill with params",
            version="1.0.0",
            category=SkillCategory.EXTERNAL,
            triggers=["param"],
            permission_level=PermissionLevel.EXTERNAL_WRITE,
            approval_required=True,
            parameters={
                "query": {"type": "string", "required": True},
                "limit": {"type": "integer", "default": 10},
            },
        )

        assert "query" in manifest.parameters
        assert manifest.parameters["query"]["required"] is True
        assert manifest.approval_required is True


class TestSkillCategories:
    """Tests for skill category enums."""

    def test_category_values(self):
        """Test category enum values."""
        assert SkillCategory.INTERNAL.value == "internal"
        assert SkillCategory.EXTERNAL.value == "external"
        assert SkillCategory.AUTONOMOUS.value == "autonomous"

    def test_permission_levels(self):
        """Test permission level values."""
        assert PermissionLevel.INTERNAL.value == "internal"
        assert PermissionLevel.EXTERNAL_READ.value == "external_read"
        assert PermissionLevel.EXTERNAL_WRITE.value == "external_write"
        assert PermissionLevel.AUTONOMOUS.value == "autonomous"

    def test_load_strategies(self):
        """Test load strategy values."""
        assert LoadStrategy.EAGER.value == "eager"
        assert LoadStrategy.JIT.value == "jit"
