"""API layer: FastAPI routers, request/response schemas, and dependency wiring.

This is the only layer that knows about HTTP, SSE framing, or FastAPI itself.
Everything it does is validate the request (pydantic), delegate to the service
layer, and translate the result back into an HTTP/SSE response.
"""
