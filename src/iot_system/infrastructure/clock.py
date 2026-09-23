"""System clock adapter.

Provides the current time as a timezone-aware UTC datetime. Injected into
the application layer so that time is deterministic in tests.
"""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """Production clock returning timezone-aware UTC timestamps."""

    def now(self) -> datetime:
        """Return the current time in UTC with tzinfo set."""
        return datetime.now(tz=UTC)
