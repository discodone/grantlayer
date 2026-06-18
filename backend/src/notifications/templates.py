"""Jinja2 HTML email templates for GrantLayer notifications."""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, select_autoescape

_TEMPLATES: dict[str, str] = {
    "grant_approved": """\
<!DOCTYPE html><html><body style="font-family:sans-serif;background:#f5f5f5;padding:2rem;">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;padding:2rem;border:1px solid #ddd;">
<h2 style="color:#2ea043;">Grant Approved</h2>
<p>Your grant request has been <strong>approved</strong>.</p>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
  <tr><td style="padding:.5rem;color:#666;">Grant ID</td><td>{{ grant_id }}</td></tr>
  <tr><td style="padding:.5rem;color:#666;">Action</td><td>{{ action }}</td></tr>
  <tr><td style="padding:.5rem;color:#666;">Resource</td><td>{{ resource }}</td></tr>
  <tr><td style="padding:.5rem;color:#666;">Valid Until</td><td>{{ valid_until }}</td></tr>
</table>
<p style="color:#666;font-size:.85rem;">This notification was sent by GrantLayer. To unsubscribe, <a href="{{ unsubscribe_url }}">click here</a>.</p>
</div></body></html>
""",
    "grant_rejected": """\
<!DOCTYPE html><html><body style="font-family:sans-serif;background:#f5f5f5;padding:2rem;">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;padding:2rem;border:1px solid #ddd;">
<h2 style="color:#da3633;">Grant Rejected</h2>
<p>Your grant request has been <strong>rejected</strong>.</p>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
  <tr><td style="padding:.5rem;color:#666;">Request ID</td><td>{{ request_id }}</td></tr>
  <tr><td style="padding:.5rem;color:#666;">Reason</td><td>{{ reason }}</td></tr>
</table>
<p style="color:#666;font-size:.85rem;">To unsubscribe, <a href="{{ unsubscribe_url }}">click here</a>.</p>
</div></body></html>
""",
    "grant_request_submitted": """\
<!DOCTYPE html><html><body style="font-family:sans-serif;background:#f5f5f5;padding:2rem;">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;padding:2rem;border:1px solid #ddd;">
<h2 style="color:#58a6ff;">Grant Request Submitted</h2>
<p>Your grant request has been <strong>submitted</strong> for review.</p>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
  <tr><td style="padding:.5rem;color:#666;">Request ID</td><td>{{ request_id }}</td></tr>
  <tr><td style="padding:.5rem;color:#666;">Action</td><td>{{ action }}</td></tr>
  <tr><td style="padding:.5rem;color:#666;">Resource</td><td>{{ resource }}</td></tr>
</table>
<p style="color:#666;font-size:.85rem;">To unsubscribe, <a href="{{ unsubscribe_url }}">click here</a>.</p>
</div></body></html>
""",
    "webhook_failure_alert": """\
<!DOCTYPE html><html><body style="font-family:sans-serif;background:#f5f5f5;padding:2rem;">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;padding:2rem;border:1px solid #ddd;">
<h2 style="color:#d29922;">Webhook Delivery Failed</h2>
<p>A webhook delivery has <strong>failed</strong> after {{ attempts }} attempts.</p>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
  <tr><td style="padding:.5rem;color:#666;">Webhook ID</td><td>{{ webhook_id }}</td></tr>
  <tr><td style="padding:.5rem;color:#666;">URL</td><td>{{ url }}</td></tr>
  <tr><td style="padding:.5rem;color:#666;">Event</td><td>{{ event_type }}</td></tr>
  <tr><td style="padding:.5rem;color:#666;">Error</td><td>{{ error }}</td></tr>
</table>
<p style="color:#666;font-size:.85rem;">To unsubscribe, <a href="{{ unsubscribe_url }}">click here</a>.</p>
</div></body></html>
""",
}

_KNOWN_TEMPLATES = frozenset(_TEMPLATES.keys())

_env = Environment(autoescape=select_autoescape(["html"]))


def render_template(template_name: str, context: dict[str, Any]) -> str:
    """Render a named email template with the given context dict."""
    if template_name not in _TEMPLATES:
        raise ValueError(f"Unknown email template: {template_name!r}. Known: {sorted(_KNOWN_TEMPLATES)}")
    tmpl = _env.from_string(_TEMPLATES[template_name])
    return tmpl.render(**context)
