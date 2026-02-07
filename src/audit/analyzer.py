"""Audit Analyzer - Analyzes audit logs for insights.

Provides:
- Activity summaries
- Pattern detection
- Usage statistics
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import AuditLog, EventType, Task, Session
from src.database.connection import get_async_session


class AuditAnalyzer:
    """Analyzes audit logs for insights and patterns.

    Provides:
    - Daily/weekly activity summaries
    - Most common actions
    - Productivity patterns
    - Session analytics
    """

    async def get_activity_summary(
        self,
        user_id: uuid.UUID,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get activity summary for a period.

        Args:
            user_id: The user's ID.
            days: Number of days to analyze.

        Returns:
            Activity summary dict.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with get_async_session() as session:
            # Get all events in period
            result = await session.execute(
                select(AuditLog)
                .where(
                    AuditLog.user_id == user_id,
                    AuditLog.created_at >= cutoff,
                )
            )
            logs = result.scalars().all()

        if not logs:
            return {
                "period_days": days,
                "total_events": 0,
                "message": "No activity in this period",
            }

        # Count by event type
        by_type = defaultdict(int)
        for log in logs:
            by_type[log.event_type.value] += 1

        # Count by day
        by_day = defaultdict(int)
        for log in logs:
            day = log.created_at.date().isoformat()
            by_day[day] += 1

        # Most active hours
        by_hour = defaultdict(int)
        for log in logs:
            by_hour[log.created_at.hour] += 1
        peak_hour = max(by_hour, key=by_hour.get) if by_hour else 0

        # Session count
        session_count = sum(
            1 for log in logs
            if log.event_type == EventType.SESSION_STARTED
        )

        # Task stats
        tasks_created = sum(
            1 for log in logs
            if log.event_type == EventType.TASK_CREATED
        )
        tasks_completed = sum(
            1 for log in logs
            if log.event_type == EventType.TASK_COMPLETED
        )

        return {
            "period_days": days,
            "total_events": len(logs),
            "events_by_type": dict(by_type),
            "events_by_day": dict(by_day),
            "peak_activity_hour": peak_hour,
            "session_count": session_count,
            "tasks_created": tasks_created,
            "tasks_completed": tasks_completed,
            "avg_events_per_day": len(logs) / days,
        }

    async def get_productivity_insights(
        self,
        user_id: uuid.UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get productivity insights.

        Args:
            user_id: The user's ID.
            days: Number of days to analyze.

        Returns:
            Productivity insights dict.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with get_async_session() as session:
            # Get task completions
            result = await session.execute(
                select(AuditLog)
                .where(
                    AuditLog.user_id == user_id,
                    AuditLog.event_type == EventType.TASK_COMPLETED,
                    AuditLog.created_at >= cutoff,
                )
            )
            completions = result.scalars().all()

            # Get task creations
            result = await session.execute(
                select(AuditLog)
                .where(
                    AuditLog.user_id == user_id,
                    AuditLog.event_type == EventType.TASK_CREATED,
                    AuditLog.created_at >= cutoff,
                )
            )
            creations = result.scalars().all()

        if not creations:
            return {
                "period_days": days,
                "message": "No tasks created in this period",
            }

        # Completion rate
        completion_rate = len(completions) / len(creations) if creations else 0

        # Analyze completion times
        completion_hours = [c.created_at.hour for c in completions]
        if completion_hours:
            hour_counts = defaultdict(int)
            for h in completion_hours:
                hour_counts[h] += 1
            productive_hours = sorted(
                hour_counts.items(),
                key=lambda x: -x[1]
            )[:3]
        else:
            productive_hours = []

        # Analyze completion days
        completion_days = [c.created_at.weekday() for c in completions]
        if completion_days:
            day_counts = defaultdict(int)
            for d in completion_days:
                day_counts[d] += 1
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            productive_days = sorted(
                day_counts.items(),
                key=lambda x: -x[1]
            )[:3]
            productive_days = [
                (day_names[d], count)
                for d, count in productive_days
            ]
        else:
            productive_days = []

        # Calculate streaks
        completion_dates = sorted(set(
            c.created_at.date() for c in completions
        ))
        current_streak = 0
        max_streak = 0
        if completion_dates:
            streak = 1
            for i in range(1, len(completion_dates)):
                if (completion_dates[i] - completion_dates[i-1]).days == 1:
                    streak += 1
                else:
                    max_streak = max(max_streak, streak)
                    streak = 1
            max_streak = max(max_streak, streak)

            # Check if streak is current
            if completion_dates[-1] >= datetime.utcnow().date() - timedelta(days=1):
                current_streak = streak

        return {
            "period_days": days,
            "tasks_created": len(creations),
            "tasks_completed": len(completions),
            "completion_rate": round(completion_rate * 100, 1),
            "productive_hours": [
                {"hour": h, "completions": c}
                for h, c in productive_hours
            ],
            "productive_days": [
                {"day": d, "completions": c}
                for d, c in productive_days
            ],
            "current_streak": current_streak,
            "max_streak": max_streak,
            "avg_completions_per_day": round(len(completions) / days, 2),
        }

    async def get_session_analytics(
        self,
        user_id: uuid.UUID,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get session analytics.

        Args:
            user_id: The user's ID.
            days: Number of days to analyze.

        Returns:
            Session analytics dict.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with get_async_session() as session:
            result = await session.execute(
                select(Session)
                .where(
                    Session.user_id == user_id,
                    Session.created_at >= cutoff,
                )
                .order_by(desc(Session.created_at))
            )
            sessions = result.scalars().all()

        if not sessions:
            return {
                "period_days": days,
                "total_sessions": 0,
                "message": "No sessions in this period",
            }

        # Calculate session durations
        durations = []
        message_counts = []
        for s in sessions:
            if s.ended_at:
                duration = (s.ended_at - s.created_at).total_seconds() / 60
                durations.append(duration)
            if s.conversation_history:
                message_counts.append(len(s.conversation_history))

        avg_duration = sum(durations) / len(durations) if durations else 0
        avg_messages = sum(message_counts) / len(message_counts) if message_counts else 0

        # Sessions by day
        by_day = defaultdict(int)
        for s in sessions:
            day = s.created_at.date().isoformat()
            by_day[day] += 1

        return {
            "period_days": days,
            "total_sessions": len(sessions),
            "avg_session_duration_minutes": round(avg_duration, 1),
            "avg_messages_per_session": round(avg_messages, 1),
            "sessions_by_day": dict(by_day),
            "avg_sessions_per_day": round(len(sessions) / days, 2),
        }

    async def get_skill_usage(
        self,
        user_id: uuid.UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get skill usage statistics.

        Args:
            user_id: The user's ID.
            days: Number of days to analyze.

        Returns:
            Skill usage dict.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with get_async_session() as session:
            result = await session.execute(
                select(AuditLog)
                .where(
                    AuditLog.user_id == user_id,
                    AuditLog.event_type == EventType.SKILL_EXECUTED,
                    AuditLog.created_at >= cutoff,
                )
            )
            logs = result.scalars().all()

        if not logs:
            return {
                "period_days": days,
                "total_skill_executions": 0,
                "message": "No skill executions in this period",
            }

        # Count by skill
        by_skill = defaultdict(int)
        success_by_skill = defaultdict(int)
        for log in logs:
            skill_name = log.details.get("skill_name", "unknown")
            by_skill[skill_name] += 1
            if log.details.get("result_summary", {}).get("success"):
                success_by_skill[skill_name] += 1

        # Calculate success rates
        skill_stats = []
        for skill, count in sorted(by_skill.items(), key=lambda x: -x[1]):
            success = success_by_skill.get(skill, 0)
            skill_stats.append({
                "skill": skill,
                "executions": count,
                "success_rate": round((success / count) * 100, 1) if count else 0,
            })

        return {
            "period_days": days,
            "total_skill_executions": len(logs),
            "unique_skills_used": len(by_skill),
            "skills": skill_stats,
            "avg_executions_per_day": round(len(logs) / days, 2),
        }

    async def generate_report(
        self,
        user_id: uuid.UUID,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Generate a comprehensive activity report.

        Args:
            user_id: The user's ID.
            days: Number of days to analyze.

        Returns:
            Comprehensive report dict.
        """
        activity = await self.get_activity_summary(user_id, days)
        productivity = await self.get_productivity_insights(user_id, days)
        sessions = await self.get_session_analytics(user_id, days)
        skills = await self.get_skill_usage(user_id, days)

        # Generate highlights
        highlights = []

        if productivity.get("completion_rate", 0) >= 80:
            highlights.append("Great completion rate!")
        elif productivity.get("completion_rate", 0) >= 50:
            highlights.append("Good progress on task completion")

        if productivity.get("current_streak", 0) >= 3:
            highlights.append(f"{productivity['current_streak']}-day completion streak!")

        if sessions.get("avg_session_duration_minutes", 0) > 0:
            avg = sessions["avg_session_duration_minutes"]
            if avg >= 10:
                highlights.append(f"Engaging sessions averaging {avg:.0f} minutes")

        # Generate suggestions
        suggestions = []

        if productivity.get("completion_rate", 0) < 50:
            suggestions.append("Try breaking down large tasks into smaller subtasks")

        if activity.get("avg_events_per_day", 0) < 5:
            suggestions.append("Consider checking in more regularly")

        productive_hours = productivity.get("productive_hours", [])
        if productive_hours:
            peak = productive_hours[0]["hour"]
            suggestions.append(f"You're most productive around {peak}:00 - schedule important tasks then")

        return {
            "period_days": days,
            "generated_at": datetime.utcnow().isoformat(),
            "activity": activity,
            "productivity": productivity,
            "sessions": sessions,
            "skills": skills,
            "highlights": highlights,
            "suggestions": suggestions,
        }
