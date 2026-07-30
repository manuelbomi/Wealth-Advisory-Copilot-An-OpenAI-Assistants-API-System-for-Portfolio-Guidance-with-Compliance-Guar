"""Infrastructure layer: external integrations and I/O.

Contains the OpenAI Assistants API client and its offline `MockAssistantsClient`
twin (selected by `client_factory.get_assistants_client`), the fund fact-sheet
retrieval store used to simulate/back the File Search tool, the audit log writer,
a minimal circuit breaker, and Prometheus metrics registration.

This is the only layer allowed to perform network calls, disk I/O, or import the
`openai` SDK.
"""
