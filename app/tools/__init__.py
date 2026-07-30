"""Function-calling tools exposed to the Assistant.

Each tool is a plain, synchronous Python function operating on the in-memory
synthetic seed data (app.domain.seed_data). They are deliberately free of any
OpenAI-specific types so the exact same implementations back both
`MockAssistantsClient` and the real `OpenAIAssistantsClient` -- only the JSON Schema
descriptors in `tool_registry.py` are OpenAI-specific (the function-calling "tools="
payload shape).
"""
