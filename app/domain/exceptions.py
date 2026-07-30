"""Domain-level exceptions.

Kept distinct from HTTP status codes / FastAPI exceptions -- the API layer is
responsible for translating these into the right HTTP response (see
app/api/routes_chat.py). This keeps the domain and service layers free of any
knowledge of HTTP.
"""

from __future__ import annotations


class ClientNotFoundError(Exception):
    """Raised when a tool or service call references an unknown synthetic client_id."""

    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        super().__init__(f"Unknown client_id: {client_id!r}")
