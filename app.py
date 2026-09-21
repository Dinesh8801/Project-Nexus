"""Databricks Apps entry point — serves the existing FastAPI server.

Databricks Apps runs `python app.py` (see app.yaml). The server binds to the
port Databricks injects via the DATABRICKS_APP_PORT environment variable.

Local dev:   python app.py   (defaults to port 8000)
"""
import os

from server import app  # noqa: F401  (also re-exported so `uvicorn app:app` works)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("DATABRICKS_APP_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)