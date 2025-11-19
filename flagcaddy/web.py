from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from .config import AppConfig
from .db import Database


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Flagcaddy Recommendations</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
    header { padding: 1rem 2rem; background: #1e293b; display: flex; justify-content: space-between; align-items: center; }
    main { padding: 1.5rem; max-width: 960px; margin: auto; }
    select, button { padding: 0.5rem; background: #0f172a; color: #f8fafc; border: 1px solid #475569; border-radius: 4px; }
    .panel { border: 1px solid #334155; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; background: #1e293b; }
    .title { font-weight: bold; font-size: 1.1rem; margin-bottom: 0.4rem; }
    .meta { color: #94a3b8; font-size: 0.9rem; margin-bottom: 0.8rem; }
    pre { white-space: pre-wrap; word-break: break-word; background: #0f172a; padding: 0.75rem; border-radius: 4px; font-size: 0.95rem; }
    #empty { text-align: center; color: #94a3b8; margin-top: 2rem; }
  </style>
</head>
<body>
  <header>
    <div>
      <strong>Flagcaddy</strong>
      <span style="color:#94a3b8;">Web recommendations</span>
    </div>
    <div>
      <select id="sessionSelect"></select>
      <button onclick="refresh()">Refresh</button>
    </div>
  </header>
  <main>
    <div id="content"></div>
    <div id="empty" hidden>No recommendations yet.</div>
  </main>
  <script>
    const selectEl = document.getElementById('sessionSelect');
    const contentEl = document.getElementById('content');
    const emptyEl = document.getElementById('empty');

    async function loadSessions() {
      const resp = await fetch('/api/sessions');
      const data = await resp.json();
      selectEl.innerHTML = '';
      data.forEach(session => {
        const opt = document.createElement('option');
        opt.value = session.name;
        opt.textContent = session.name;
        selectEl.appendChild(opt);
      });
      if (data.length) {
        if (!selectEl.value) {
          selectEl.value = data[0].name;
        }
        refresh();
      } else {
        contentEl.innerHTML = '';
        emptyEl.hidden = false;
      }
    }

    async function refresh() {
      if (!selectEl.value) {
        await loadSessions();
        return;
      }
      const resp = await fetch(`/api/sessions/${encodeURIComponent(selectEl.value)}/recommendations?limit=10`);
      if (!resp.ok) {
        contentEl.innerHTML = '<div class="panel">Unable to load recommendations.</div>';
        emptyEl.hidden = true;
        return;
      }
      const data = await resp.json();
      contentEl.innerHTML = '';
      if (!data.length) {
        emptyEl.hidden = false;
        return;
      }
      emptyEl.hidden = true;
      data.forEach(rec => {
        const wrapper = document.createElement('div');
        wrapper.className = 'panel';
        wrapper.innerHTML = `
          <div class="title">${rec.title}</div>
          <div class="meta">${rec.source} · ${new Date(rec.created_at).toLocaleString()}</div>
          <pre>${rec.body}</pre>
        `;
        contentEl.appendChild(wrapper);
      });
    }

    loadSessions();
    setInterval(refresh, 30000);
  </script>
</body>
</html>
"""


def create_app(config: AppConfig, db: Database) -> FastAPI:
    app = FastAPI(title="Flagcaddy", version="0.1.0")

    def _session_id(session_name: str) -> int:
        session_id = db.get_session_id(session_name)
        if session_id is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        return session_id

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML_TEMPLATE

    @app.get("/api/sessions")
    async def list_sessions():
        rows = db.list_sessions()
        return [
            {"id": row["id"], "name": row["name"], "created_at": row["created_at"]}
            for row in rows
        ]

    @app.get("/api/sessions/{session}/recommendations")
    async def session_recommendations(session: str, limit: int = 10):
        session_id = _session_id(session)
        rows = db.list_recommendations(session_id, limit=limit)
        return [
            {
                "id": row["id"],
                "source": row["source"],
                "title": row["title"],
                "body": row["body"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    @app.get("/api/sessions/{session}/events")
    async def session_events(session: str, limit: int = 20):
        session_id = _session_id(session)
        rows = db.recent_events(session_id, limit=limit)
        return [
            {
                "id": row["id"],
                "command": row["command"],
                "novelty": row["novelty"],
                "duplicate": bool(row["duplicate"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    return app


__all__ = ["create_app"]

