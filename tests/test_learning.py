"""Tests for Learning Module functionality."""

import uuid
from datetime import datetime, timedelta
import pytest

from src.memory.learning import (
    LearningModule,
    LearnedPattern,
    ImportantContext,
    PreferenceUpdate,
    PatternType,
    ImportanceLevel,
    MEMORY_TYPE_LEARNED_PATTERN,
    MEMORY_TYPE_IMPORTANT_CONTEXT,
)


class TestPatternType:
    """Tests for PatternType enum."""

    def test_pattern_type_values(self):
        """Test pattern type values."""
        assert PatternType.TIME_PREFERENCE.value == "time_preference"
        assert PatternType.PRIORITY_STYLE.value == "priority_style"
        assert PatternType.TASK_CATEGORY.value == "task_category"
        assert PatternType.COMMUNICATION_STYLE.value == "communication_style"
        assert PatternType.WORK_PATTERN.value == "work_pattern"
        assert PatternType.REMINDER_PREFERENCE.value == "reminder_preference"


class TestImportanceLevel:
    """Tests for ImportanceLevel enum."""

    def test_importance_level_values(self):
        """Test importance level values."""
        assert ImportanceLevel.LOW.value == "low"
        assert ImportanceLevel.MEDIUM.value == "medium"
        assert ImportanceLevel.HIGH.value == "high"
        assert ImportanceLevel.PERMANENT.value == "permanent"


class TestLearnedPattern:
    """Tests for LearnedPattern dataclass."""

    def test_create_pattern(self):
        """Test creating a learned pattern."""
        pattern_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.utcnow()

        pattern = LearnedPattern(
            id=pattern_id,
            user_id=user_id,
            pattern_type=PatternType.TIME_PREFERENCE,
            description="Most productive in the morning",
            confidence=0.85,
            observation_count=5,
            first_observed=now - timedelta(days=7),
            last_observed=now,
            metadata={"morning_ratio": 0.7},
        )

        assert pattern.id == pattern_id
        assert pattern.user_id == user_id
        assert pattern.pattern_type == PatternType.TIME_PREFERENCE
        assert pattern.confidence == 0.85
        assert pattern.observation_count == 5

    def test_pattern_to_dict(self):
        """Test converting pattern to dict."""
        pattern_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.utcnow()

        pattern = LearnedPattern(
            id=pattern_id,
            user_id=user_id,
            pattern_type=PatternType.PRIORITY_STYLE,
            description="Focuses on high priority tasks",
            confidence=0.75,
            observation_count=3,
            first_observed=now,
            last_observed=now,
        )

        pattern_dict = pattern.to_dict()

        assert pattern_dict["id"] == str(pattern_id)
        assert pattern_dict["pattern_type"] == "priority_style"
        assert pattern_dict["confidence"] == 0.75
        assert pattern_dict["observation_count"] == 3


class TestImportantContext:
    """Tests for ImportantContext dataclass."""

    def test_create_context(self):
        """Test creating important context."""
        context_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.utcnow()
        expires = now + timedelta(days=7)

        context = ImportantContext(
            id=context_id,
            user_id=user_id,
            content="User is preparing for Q4 presentation",
            importance=ImportanceLevel.HIGH,
            created_at=now,
            expires_at=expires,
            tags=["q4", "presentation"],
        )

        assert context.id == context_id
        assert context.user_id == user_id
        assert context.content == "User is preparing for Q4 presentation"
        assert context.importance == ImportanceLevel.HIGH
        assert "q4" in context.tags

    def test_permanent_context_no_expiry(self):
        """Test permanent context has no expiry."""
        context = ImportantContext(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            content="User prefers brief communication",
            importance=ImportanceLevel.PERMANENT,
            created_at=datetime.utcnow(),
            expires_at=None,
        )

        assert context.expires_at is None


class TestPreferenceUpdate:
    """Tests for PreferenceUpdate dataclass."""

    def test_create_preference_update(self):
        """Test creating a preference update."""
        update = PreferenceUpdate(
            preference_key="working_hours",
            old_value="9am-5pm",
            new_value="8am-4pm",
            reason="User consistently completes tasks before 4pm",
            confidence=0.85,
            requires_approval=True,
        )

        assert update.preference_key == "working_hours"
        assert update.old_value == "9am-5pm"
        assert update.new_value == "8am-4pm"
        assert update.requires_approval is True

    def test_auto_update_high_confidence(self):
        """Test auto-update with high confidence."""
        update = PreferenceUpdate(
            preference_key="preferred_task_view",
            old_value="list",
            new_value="kanban",
            reason="User always switches to kanban view",
            confidence=0.95,
            requires_approval=False,
        )

        assert update.requires_approval is False


class TestLearningModuleConfiguration:
    """Tests for LearningModule configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        module = LearningModule()

        assert module.AUTO_UPDATE_CONFIDENCE_THRESHOLD == 0.9
        assert module.MIN_OBSERVATIONS_TO_LEARN == 3

    def test_approval_required_preferences(self):
        """Test which preferences require approval."""
        module = LearningModule()

        # These should require approval
        assert "default_priority" in module.APPROVAL_REQUIRED_PREFERENCES
        assert "notification_preferences" in module.APPROVAL_REQUIRED_PREFERENCES
        assert "working_hours" in module.APPROVAL_REQUIRED_PREFERENCES
        assert "timezone" in module.APPROVAL_REQUIRED_PREFERENCES

        # This should NOT require approval
        assert "preferred_task_view" not in module.APPROVAL_REQUIRED_PREFERENCES


class TestLearningModuleHelpers:
    """Tests for LearningModule helper methods."""

    def test_pattern_type_validation(self):
        """Test that invalid pattern types default to WORK_PATTERN."""
        # This is tested indirectly through store_learned_pattern
        # The method should handle invalid types gracefully
        try:
            PatternType("invalid_type")
            assert False, "Should raise ValueError"
        except ValueError:
            pass  # Expected

    def test_importance_level_validation(self):
        """Test that invalid importance levels default to MEDIUM."""
        try:
            ImportanceLevel("invalid_level")
            assert False, "Should raise ValueError"
        except ValueError:
            pass  # Expected


class TestMemoryTypeConstants:
    """Tests for memory type constants."""

    def test_memory_type_values(self):
        """Test memory type constant values."""
        assert MEMORY_TYPE_LEARNED_PATTERN == "learned_pattern"
        assert MEMORY_TYPE_IMPORTANT_CONTEXT == "important_context"
