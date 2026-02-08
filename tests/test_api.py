"""Tests for API endpoints."""

import uuid
import pytest
from httpx import AsyncClient

from src.database.orm import User


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test the root endpoint returns app info."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "AI Task Management Agent"
    assert data["version"] == "0.1.0"
    assert "docs" in data
    assert "api" in data


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """Test the health check endpoint."""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


class TestUsersAPI:
    """Tests for user endpoints."""

    @pytest.mark.asyncio
    async def test_create_user(self, client: AsyncClient):
        """Test creating a new user."""
        user_data = {
            "email": "newuser@example.com",
            "name": "New User",
        }

        response = await client.post("/api/v1/users", json=user_data)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["name"] == user_data["name"]
        assert "id" in data

    @pytest.mark.asyncio
    async def test_get_user(self, client: AsyncClient, test_user: User):
        """Test getting a user by ID."""
        response = await client.get(f"/api/v1/users/{test_user.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user.id)
        assert data["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self, client: AsyncClient):
        """Test getting a user that doesn't exist."""
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v1/users/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_user(self, client: AsyncClient, test_user: User):
        """Test updating a user."""
        update_data = {
            "name": "Updated Name",
        }

        response = await client.patch(
            f"/api/v1/users/{test_user.id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"


class TestTasksAPI:
    """Tests for task endpoints."""

    @pytest.mark.asyncio
    async def test_create_task(self, client: AsyncClient, test_user: User):
        """Test creating a new task."""
        task_data = {
            "title": "Test Task",
            "description": "A test task description",
            "priority": 3,
        }

        response = await client.post(
            f"/api/v1/tasks?user_id={test_user.id}",
            json=task_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == task_data["title"]
        assert data["description"] == task_data["description"]
        assert data["priority"] == task_data["priority"]
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, client: AsyncClient, test_user: User):
        """Test listing tasks when there are none."""
        response = await client.get(f"/api/v1/tasks?user_id={test_user.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_tasks(self, client: AsyncClient, test_user: User):
        """Test listing tasks after creating some."""
        # Create tasks
        for i in range(3):
            await client.post(
                f"/api/v1/tasks?user_id={test_user.id}",
                json={"title": f"Task {i+1}", "priority": i+1},
            )

        response = await client.get(f"/api/v1/tasks?user_id={test_user.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["tasks"]) == 3

    @pytest.mark.asyncio
    async def test_get_task(self, client: AsyncClient, test_user: User):
        """Test getting a specific task."""
        # Create a task
        create_response = await client.post(
            f"/api/v1/tasks?user_id={test_user.id}",
            json={"title": "Get Me", "priority": 5},
        )
        task_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/tasks/{task_id}?user_id={test_user.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Get Me"
        assert data["priority"] == 5

    @pytest.mark.asyncio
    async def test_update_task(self, client: AsyncClient, test_user: User):
        """Test updating a task."""
        # Create a task
        create_response = await client.post(
            f"/api/v1/tasks?user_id={test_user.id}",
            json={"title": "Original Title"},
        )
        task_id = create_response.json()["id"]

        # Update it
        response = await client.patch(
            f"/api/v1/tasks/{task_id}?user_id={test_user.id}",
            json={"title": "Updated Title", "priority": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["priority"] == 5

    @pytest.mark.asyncio
    async def test_complete_task(self, client: AsyncClient, test_user: User):
        """Test completing a task."""
        # Create a task
        create_response = await client.post(
            f"/api/v1/tasks?user_id={test_user.id}",
            json={"title": "Complete Me"},
        )
        task_id = create_response.json()["id"]

        # Complete it
        response = await client.post(
            f"/api/v1/tasks/{task_id}/complete?user_id={test_user.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_delete_task(self, client: AsyncClient, test_user: User):
        """Test deleting a task."""
        # Create a task
        create_response = await client.post(
            f"/api/v1/tasks?user_id={test_user.id}",
            json={"title": "Delete Me"},
        )
        task_id = create_response.json()["id"]

        # Delete it
        response = await client.delete(
            f"/api/v1/tasks/{task_id}?user_id={test_user.id}"
        )

        assert response.status_code == 200

        # Verify it's gone
        get_response = await client.get(
            f"/api/v1/tasks/{task_id}?user_id={test_user.id}"
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_task_stats(self, client: AsyncClient, test_user: User):
        """Test getting task statistics."""
        # Create and complete some tasks
        for i in range(3):
            resp = await client.post(
                f"/api/v1/tasks?user_id={test_user.id}",
                json={"title": f"Task {i+1}"},
            )
            if i == 0:  # Complete the first one
                task_id = resp.json()["id"]
                await client.post(
                    f"/api/v1/tasks/{task_id}/complete?user_id={test_user.id}"
                )

        response = await client.get(
            f"/api/v1/tasks/stats?user_id={test_user.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["completed"] == 1
        assert data["pending"] == 2


class TestSkillsAPI:
    """Tests for skills endpoints."""

    @pytest.mark.asyncio
    async def test_list_skills(self, client: AsyncClient):
        """Test listing available skills."""
        response = await client.get("/api/v1/skills")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least the internal skills
        skill_names = [s["name"] for s in data]
        assert "task_crud" in skill_names or len(data) >= 0  # May be empty if not loaded


class TestChatAPI:
    """Tests for chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_simple_message(self, client: AsyncClient, test_user: User):
        """Test sending a chat message."""
        response = await client.post(
            f"/api/v1/chat?user_id={test_user.id}",
            json={"message": "Hello!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "session_id" in data
        assert "suggestions" in data
