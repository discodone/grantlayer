"""Admin UI router — serves HTML dashboard at /admin and /admin/health."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..core.db import get_db_health
from .deps import require_admin_user

router = APIRouter(prefix="/admin", tags=["admin-ui"])

_ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GrantLayer Admin</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}
a{color:#58a6ff;text-decoration:none}
a:hover{text-decoration:underline}
#login-screen{display:flex;align-items:center;justify-content:center;min-height:100vh}
.login-box{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:2rem;width:360px}
.login-box h1{font-size:1.4rem;margin-bottom:1.5rem;color:#e6edf3}
.form-group{margin-bottom:1rem}
label{display:block;margin-bottom:.4rem;font-size:.85rem;color:#8b949e}
input{width:100%;padding:.6rem .8rem;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:.9rem}
input:focus{outline:none;border-color:#58a6ff}
button{padding:.6rem 1.2rem;background:#238636;border:none;border-radius:6px;color:#fff;cursor:pointer;font-size:.9rem;width:100%;margin-top:.5rem}
button:hover{background:#2ea043}
button.secondary{background:#21262d;margin-top:.5rem}
button.secondary:hover{background:#30363d}
button.danger{background:#da3633}
button.danger:hover{background:#b91c1c}
.error-msg{color:#f85149;font-size:.85rem;margin-top:.5rem}
#app{display:none;flex-direction:column;min-height:100vh}
nav{background:#161b22;border-bottom:1px solid #30363d;padding:.8rem 1.5rem;display:flex;align-items:center;gap:1rem}
nav .brand{font-weight:700;color:#e6edf3;font-size:1.1rem}
nav .spacer{flex:1}
nav button{width:auto;padding:.4rem .9rem;font-size:.8rem;background:#21262d}
nav button:hover{background:#30363d}
.layout{display:flex;flex:1}
.sidebar{width:200px;background:#161b22;border-right:1px solid #30363d;padding:1rem 0;flex-shrink:0}
.sidebar-item{display:block;padding:.6rem 1.2rem;cursor:pointer;font-size:.9rem;color:#8b949e;border-left:3px solid transparent}
.sidebar-item:hover{background:#21262d;color:#c9d1d9}
.sidebar-item.active{background:#21262d;color:#58a6ff;border-left-color:#58a6ff}
.content{flex:1;padding:1.5rem;overflow-y:auto}
h2{font-size:1.2rem;color:#e6edf3;margin-bottom:1rem}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1rem;margin-bottom:1.5rem}
.stat-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1.2rem;text-align:center}
.stat-card .value{font-size:2rem;font-weight:700;color:#58a6ff}
.stat-card .label{font-size:.8rem;color:#8b949e;margin-top:.3rem}
table{width:100%;border-collapse:collapse;background:#161b22;border-radius:8px;overflow:hidden;font-size:.875rem}
th{background:#21262d;color:#8b949e;text-align:left;padding:.7rem 1rem;font-weight:500;border-bottom:1px solid #30363d}
td{padding:.7rem 1rem;border-bottom:1px solid #21262d;color:#c9d1d9}
tr:last-child td{border-bottom:none}
tr:hover td{background:#21262d}
.badge{display:inline-block;padding:.2rem .5rem;border-radius:4px;font-size:.75rem;font-weight:500}
.badge-green{background:#1f4a23;color:#56d364}
.badge-red{background:#4a1818;color:#f85149}
.badge-yellow{background:#4a3518;color:#d29922}
.badge-blue{background:#0d2a4a;color:#58a6ff}
.badge-gray{background:#21262d;color:#8b949e}
.filter-row{display:flex;gap:.7rem;margin-bottom:1rem;align-items:center}
.filter-row select,.filter-row input{width:auto;padding:.4rem .7rem;font-size:.85rem}
.filter-row button{width:auto;padding:.4rem .9rem;font-size:.85rem}
.pagination{display:flex;gap:.5rem;margin-top:1rem;align-items:center;font-size:.85rem}
.pagination button{width:auto;padding:.3rem .8rem;font-size:.8rem;background:#21262d}
.health-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem}
.health-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1rem}
.health-card .hc-label{font-size:.8rem;color:#8b949e;margin-bottom:.4rem}
.health-card .hc-value{font-size:.95rem;color:#e6edf3;font-weight:500}
.loading{color:#8b949e;font-size:.9rem;padding:1rem 0}
.empty{color:#8b949e;font-size:.9rem;padding:1rem 0;text-align:center}
</style>
</head>
<body>

<div id="login-screen">
  <div class="login-box">
    <h1>GrantLayer Admin</h1>
    <div class="form-group">
      <label>Admin Token (Bearer)</label>
      <input type="password" id="token-input" placeholder="Enter admin token" />
    </div>
    <button id="login-btn">Sign In</button>
    <div id="login-error" class="error-msg"></div>
  </div>
</div>

<div id="app">
  <nav>
    <span class="brand">GrantLayer Admin</span>
    <span class="spacer"></span>
    <button onclick="logout()">Sign Out</button>
  </nav>
  <div class="layout">
    <div class="sidebar">
      <span class="sidebar-item active" onclick="showSection('dashboard')">Dashboard</span>
      <span class="sidebar-item" onclick="showSection('grants')">Grants</span>
      <span class="sidebar-item" onclick="showSection('grant-requests')">Grant Requests</span>
      <span class="sidebar-item" onclick="showSection('operators')">Users / Operators</span>
      <span class="sidebar-item" onclick="showSection('audit')">Audit Log</span>
      <span class="sidebar-item" onclick="showSection('webhooks')">Webhooks</span>
      <span class="sidebar-item" onclick="showSection('health')">System Health</span>
    </div>
    <div class="content">
      <div id="section-dashboard">
        <h2>Dashboard</h2>
        <div class="stats-grid" id="stats-grid"><div class="loading">Loading...</div></div>
      </div>
      <div id="section-grants" style="display:none">
        <h2>Grants</h2>
        <div class="filter-row">
          <select id="grant-status-filter">
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="revoked">Revoked</option>
          </select>
          <button onclick="loadGrants()">Filter</button>
        </div>
        <div id="grants-table"></div>
      </div>
      <div id="section-grant-requests" style="display:none">
        <h2>Grant Requests</h2>
        <div id="grant-requests-table"></div>
      </div>
      <div id="section-operators" style="display:none">
        <h2>Users / Operators</h2>
        <div id="operators-table"></div>
        <div class="pagination">
          <button id="ops-prev" onclick="operatorPage(-1)" disabled>Prev</button>
          <span id="ops-page-info">Page 1</span>
          <button id="ops-next" onclick="operatorPage(1)">Next</button>
        </div>
      </div>
      <div id="section-audit" style="display:none">
        <h2>Audit Log (last 100)</h2>
        <div id="audit-table"></div>
      </div>
      <div id="section-webhooks" style="display:none">
        <h2>Webhook Subscriptions</h2>
        <div id="webhooks-table"></div>
      </div>
      <div id="section-health" style="display:none">
        <h2>System Health</h2>
        <div class="health-grid" id="health-grid"></div>
      </div>
    </div>
  </div>
</div>

<script>
let _token = null;
let _opsCursor = null;
let _opsCursorStack = [];

function getToken() { return _token || sessionStorage.getItem('gl_admin_token'); }

async function apiFetch(path, opts={}) {
  const tk = getToken();
  const headers = {'Content-Type': 'application/json'};
  if (tk) headers['Authorization'] = 'Bearer ' + tk;
  Object.assign(headers, opts.headers || {});
  const r = await fetch(path, {...opts, headers});
  if (r.status === 401 || r.status === 403) { logout(); throw new Error('Unauthorized'); }
  return r;
}

document.getElementById('login-btn').addEventListener('click', async () => {
  const t = document.getElementById('token-input').value.trim();
  if (!t) return;
  try {
    const r = await fetch('/admin/health', {headers: {Authorization: 'Bearer ' + t}});
    if (r.ok) {
      sessionStorage.setItem('gl_admin_token', t);
      _token = t;
      showApp();
    } else {
      document.getElementById('login-error').textContent = 'Invalid token (status ' + r.status + ')';
    }
  } catch(e) {
    document.getElementById('login-error').textContent = 'Connection error: ' + e.message;
  }
});

document.getElementById('token-input').addEventListener('keydown', e => { if(e.key==='Enter') document.getElementById('login-btn').click(); });

function logout() {
  sessionStorage.removeItem('gl_admin_token');
  _token = null;
  document.getElementById('app').style.display = 'none';
  document.getElementById('login-screen').style.display = 'flex';
  document.getElementById('token-input').value = '';
  document.getElementById('login-error').textContent = '';
}

function showApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app').style.display = 'flex';
  loadDashboard();
}

function showSection(name) {
  document.querySelectorAll('[id^="section-"]').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.sidebar-item').forEach(el => el.classList.remove('active'));
  document.getElementById('section-' + name).style.display = '';
  event.target.classList.add('active');
  if (name === 'dashboard') loadDashboard();
  else if (name === 'grants') loadGrants();
  else if (name === 'grant-requests') loadGrantRequests();
  else if (name === 'operators') { _opsCursor = null; _opsCursorStack = []; loadOperators(); }
  else if (name === 'audit') loadAudit();
  else if (name === 'webhooks') loadWebhooks();
  else if (name === 'health') loadHealth();
}

function badge(text, cls) { return '<span class="badge badge-' + cls + '">' + text + '</span>'; }
function statusBadge(revoked) { return revoked ? badge('Revoked','red') : badge('Active','green'); }
function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

async function loadDashboard() {
  const el = document.getElementById('stats-grid');
  el.innerHTML = '<div class="loading">Loading...</div>';
  try {
    const [gr, grr, ops] = await Promise.allSettled([
      apiFetch('/v1/grants?limit=1').then(r=>r.json()),
      apiFetch('/v1/grant-requests?limit=1').then(r=>r.json()),
      apiFetch('/v1/admin/operators').then(r=>r.json()),
    ]);
    const grantsCount = gr.status==='fulfilled' ? (Array.isArray(gr.value)?gr.value.length:'?') : '?';
    const grCount = grr.status==='fulfilled' ? (Array.isArray(grr.value.items||grr.value)?((grr.value.items||grr.value).length):'?') : '?';
    const opsCount = ops.status==='fulfilled' ? (Array.isArray(ops.value)?ops.value.length:'?') : '?';
    const hr = await apiFetch('/admin/health').then(r=>r.json()).catch(()=>({}));
    el.innerHTML = `
      <div class="stat-card"><div class="value">${esc(opsCount)}</div><div class="label">Operators</div></div>
      <div class="stat-card"><div class="value">${esc(grantsCount)}</div><div class="label">Grants (page 1)</div></div>
      <div class="stat-card"><div class="value">${esc(grCount)}</div><div class="label">Grant Requests (page 1)</div></div>
      <div class="stat-card"><div class="value">${esc(hr.uptime_seconds||'?')}s</div><div class="label">Uptime</div></div>
      <div class="stat-card"><div class="value" style="font-size:1.2rem">${esc(hr.database||'?')}</div><div class="label">Database</div></div>
      <div class="stat-card"><div class="value" style="font-size:1.2rem">${esc(hr.redis||'?')}</div><div class="label">Redis</div></div>
    `;
  } catch(e) { el.innerHTML = '<div class="loading">Error: ' + esc(e.message) + '</div>'; }
}

async function loadGrants() {
  const el = document.getElementById('grants-table');
  el.innerHTML = '<div class="loading">Loading...</div>';
  try {
    const status = document.getElementById('grant-status-filter').value;
    let url = '/v1/grants?limit=50';
    if (status === 'revoked') url += '&revoked=true';
    else if (status === 'active') url += '&revoked=false';
    const r = await apiFetch(url);
    const data = await r.json();
    const items = Array.isArray(data) ? data : (data.items || []);
    if (!items.length) { el.innerHTML = '<div class="empty">No grants found.</div>'; return; }
    el.innerHTML = '<table><thead><tr><th>ID</th><th>Subject</th><th>Action</th><th>Resource</th><th>Status</th><th>Created</th></tr></thead><tbody>' +
      items.map(g=>`<tr><td>${esc(g.id||g.grantId||'')}</td><td>${esc(g.subject_id||g.subjectId||'')}</td><td>${esc(g.action||'')}</td><td>${esc(g.resource||'')}</td><td>${statusBadge(g.revoked)}</td><td>${esc((g.created_at||g.createdAt||'').slice(0,19))}</td></tr>`).join('') +
      '</tbody></table>';
  } catch(e) { el.innerHTML = '<div class="loading">Error: ' + esc(e.message) + '</div>'; }
}

async function loadGrantRequests() {
  const el = document.getElementById('grant-requests-table');
  el.innerHTML = '<div class="loading">Loading...</div>';
  try {
    const r = await apiFetch('/v1/grant-requests?limit=50');
    const data = await r.json();
    const items = Array.isArray(data) ? data : (data.items || []);
    if (!items.length) { el.innerHTML = '<div class="empty">No grant requests found.</div>'; return; }
    el.innerHTML = '<table><thead><tr><th>ID</th><th>Requester</th><th>Action</th><th>Status</th><th>Created</th></tr></thead><tbody>' +
      items.map(g=>`<tr><td>${esc(g.id||g.requestId||'')}</td><td>${esc(g.requester_id||g.requesterId||'')}</td><td>${esc(g.action||'')}</td><td>${badge(esc(g.status||'?'),'blue')}</td><td>${esc((g.created_at||g.createdAt||'').slice(0,19))}</td></tr>`).join('') +
      '</tbody></table>';
  } catch(e) { el.innerHTML = '<div class="loading">Error: ' + esc(e.message) + '</div>'; }
}

let _opsPage = 1;
async function loadOperators() {
  const el = document.getElementById('operators-table');
  el.innerHTML = '<div class="loading">Loading...</div>';
  try {
    let url = '/v1/admin/operators';
    if (_opsCursor) url += '?cursor=' + encodeURIComponent(_opsCursor);
    const r = await apiFetch(url);
    const data = await r.json();
    const items = Array.isArray(data) ? data : (data.items || []);
    if (!items.length) { el.innerHTML = '<div class="empty">No operators found.</div>'; return; }
    el.innerHTML = '<table><thead><tr><th>Name</th><th>Role</th><th>Tenant</th><th>Active</th><th>Created</th></tr></thead><tbody>' +
      items.map(o=>`<tr><td>${esc(o.name||'')}</td><td>${badge(esc(o.role||'?'),'blue')}</td><td>${esc(o.tenantId||o.tenant_id||'')}</td><td>${o.active?badge('Active','green'):badge('Inactive','red')}</td><td>${esc((o.createdAt||o.created_at||'').slice(0,19))}</td></tr>`).join('') +
      '</tbody></table>';
    document.getElementById('ops-page-info').textContent = 'Page ' + _opsPage;
    const cursor = data.nextCursor || data.next_cursor;
    document.getElementById('ops-next').disabled = !cursor;
    if (cursor) _opsCursor = cursor;
  } catch(e) { el.innerHTML = '<div class="loading">Error: ' + esc(e.message) + '</div>'; }
}

function operatorPage(dir) {
  if (dir > 0) { _opsCursorStack.push(_opsCursor); _opsPage++; }
  else { _opsCursor = _opsCursorStack.pop() || null; _opsPage = Math.max(1, _opsPage-1); }
  document.getElementById('ops-prev').disabled = _opsCursorStack.length === 0;
  loadOperators();
}

async function loadAudit() {
  const el = document.getElementById('audit-table');
  el.innerHTML = '<div class="loading">Loading...</div>';
  try {
    const r = await apiFetch('/v1/audit-events?limit=100');
    const data = await r.json();
    const items = Array.isArray(data) ? data : (data.items || data.events || []);
    if (!items.length) { el.innerHTML = '<div class="empty">No audit events found.</div>'; return; }
    el.innerHTML = '<table><thead><tr><th>Time</th><th>Subject</th><th>Action</th><th>Resource</th><th>Approved</th></tr></thead><tbody>' +
      items.map(e=>`<tr><td>${esc((e.timestamp||e.created_at||e.createdAt||'').slice(0,19))}</td><td>${esc(e.subject_id||e.subjectId||'')}</td><td>${esc(e.action||'')}</td><td>${esc(e.resource||'')}</td><td>${e.approved?badge('Yes','green'):badge('No','red')}</td></tr>`).join('') +
      '</tbody></table>';
  } catch(e) { el.innerHTML = '<div class="loading">Error: ' + esc(e.message) + '</div>'; }
}

async function loadWebhooks() {
  const el = document.getElementById('webhooks-table');
  el.innerHTML = '<div class="loading">Loading...</div>';
  try {
    const r = await apiFetch('/v1/webhooks');
    const data = await r.json();
    const items = Array.isArray(data) ? data : (data.items || []);
    if (!items.length) { el.innerHTML = '<div class="empty">No webhook subscriptions found.</div>'; return; }
    el.innerHTML = '<table><thead><tr><th>ID</th><th>URL</th><th>Events</th><th>Active</th><th>Created</th></tr></thead><tbody>' +
      items.map(w=>`<tr><td>${esc(w.id||'')}</td><td>${esc(w.url||'')}</td><td>${esc((w.events||[]).join(', '))}</td><td>${w.active!==false?badge('Active','green'):badge('Inactive','gray')}</td><td>${esc((w.created_at||w.createdAt||'').slice(0,19))}</td></tr>`).join('') +
      '</tbody></table>';
  } catch(e) { el.innerHTML = '<div class="loading">Error: ' + esc(e.message) + '</div>'; }
}

async function loadHealth() {
  const el = document.getElementById('health-grid');
  el.innerHTML = '<div class="loading">Loading...</div>';
  try {
    const r = await apiFetch('/admin/health');
    const d = await r.json();
    el.innerHTML = Object.entries(d).map(([k,v])=>`
      <div class="health-card">
        <div class="hc-label">${esc(k)}</div>
        <div class="hc-value">${esc(String(v))}</div>
      </div>`).join('');
  } catch(e) { el.innerHTML = '<div class="loading">Error: ' + esc(e.message) + '</div>'; }
}

// Auto-login if token already in sessionStorage
if (sessionStorage.getItem('gl_admin_token')) {
  _token = sessionStorage.getItem('gl_admin_token');
  showApp();
}
</script>
</body>
</html>"""


@router.get("", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def admin_ui(
    _: dict = Depends(require_admin_user),
) -> HTMLResponse:
    return HTMLResponse(content=_ADMIN_HTML)


@router.get("/health")
async def admin_health(request: Request, _: dict = Depends(require_admin_user)) -> Any:
    try:
        db_health = get_db_health()
        db_status = "ok" if db_health.get("dbConnected") else "error: unreachable"
    except Exception as e:
        db_status = f"error: {e}"

    try:
        start = request.app.state.start_time
    except AttributeError:
        start = None
    uptime = int(time.time() - start) if start is not None else 0

    limiter = getattr(request.app.state, "auth_rate_limiter", None)
    redis_status = limiter.redis_status if limiter is not None else "disabled"

    return JSONResponse({
        "status": "ok" if db_status == "ok" else "degraded",
        "service": "grantlayer-admin",
        "database": db_status,
        "redis": redis_status,
        "uptime_seconds": uptime,
    })
