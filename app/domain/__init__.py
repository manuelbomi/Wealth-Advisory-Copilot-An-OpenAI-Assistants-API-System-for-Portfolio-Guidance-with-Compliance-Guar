"""Domain layer: pure business models and synthetic seed data.

Nothing in this package performs I/O (no network calls, no file reads besides the
static seed module, no logging side-effects beyond what pydantic itself does). This
keeps the domain layer trivially unit-testable and free of infrastructure concerns.
"""
