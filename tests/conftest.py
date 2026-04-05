"""Pytest configuration and shared fixtures."""

import os

import pytest

# Use in-memory SQLite for all tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("COPERNICUS_CLIENT_ID", "test-client-id")
os.environ.setdefault("COPERNICUS_CLIENT_SECRET", "test-client-secret")
