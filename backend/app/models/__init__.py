"""Declarative base for application-layer business tables.

BFF business data only (users, projects, bookmarks, report exports, demo
scenarios, ui preferences, app audit events). AgentGuard-stored investigation and
experience data is never duplicated wholesale. First migrations land with B3/B8.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all BFF tables."""
