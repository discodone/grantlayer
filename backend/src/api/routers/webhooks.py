"""Webhook router — thin re-export from the webhooks module.

The canonical implementation lives in backend/src/webhooks/router.py.
This shim keeps the import path in app.py unchanged.
"""

from ...webhooks.router import router  # noqa: F401
