"""Databricks Apps entry point — reuses the existing FastAPI server.

Databricks Apps detects the `app` object and serves it on a public URL.
The whole agent (risk engine + LLM enrichment) is unchanged.
"""
from server import app  # noqa: F401