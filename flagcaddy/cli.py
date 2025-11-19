from __future__ import annotations

import os
from typing import List, Optional

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from .capture import PtySession
from .config import AppConfig, load_config
from .db import Database
from .engine import RecommendationEngine
from .llm import CodexExecClient
from .web import create_app


app = typer.Typer(help="Passive recommendation engine for CTF/pentest terminals.")
console = Console()


def bootstrap() -> tuple[AppConfig, Database, RecommendationEngine]:
    config = load_config()
    db = Database(config.db_path)
    engine = RecommendationEngine(db, config, CodexExecClient(config.llm_command))
    return config, db, engine


def _require_session_id(db: Database, session: str) -> int:
    session_id = db.get_session_id(session)
    if session_id is None:
        console.print(f"[bold red]Unknown session[/] {session!r}")
        raise typer.Exit(1)
    return session_id


@app.command()
def wrap(
    session: str = typer.Argument(..., help="Session name used to group recommendations."),
    command: List[str] = typer.Argument(None, help="Command to execute (defaults to current shell)."),
):
    """
    Wrap an interactive shell or command in a PTY so Flagcaddy can capture stdin/stdout.
    """
    _, db, engine = bootstrap()
    cmd = command or [os.environ.get("SHELL", "/bin/bash")]
    console.print(f"[bold green]Starting session[/] {session!r} -> {' '.join(cmd)}")
    pty_session = PtySession(session, cmd, db, engine)
    exit_code = pty_session.start()
    raise typer.Exit(os.waitstatus_to_exitcode(exit_code))


@app.command("sessions")
def list_sessions():
    """
    List known sessions.
    """
    _, db, _ = bootstrap()
    rows = db.list_sessions()
    table = Table("Session", "Created")
    for row in rows:
        table.add_row(row["name"], row["created_at"])
    console.print(table)


@app.command("events")
def show_events(
    session: str = typer.Argument(...),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of events to display."),
):
    """
    Show captured events for a session.
    """
    _, db, _ = bootstrap()
    session_id = _require_session_id(db, session)
    rows = db.recent_events(session_id, limit=limit)
    table = Table("ID", "Command", "Novelty", "Duplicate", "Created")
    for row in rows:
        table.add_row(
            str(row["id"]),
            row["command"],
            f"{row['novelty']:.2f}" if row["novelty"] is not None else "-",
            "yes" if row["duplicate"] else "no",
            row["created_at"],
        )
    console.print(table)


@app.command("recommendations")
def show_recommendations(
    session: str = typer.Argument(...),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of recommendations."),
):
    """
    Show recorded recommendations for a session.
    """
    _, db, _ = bootstrap()
    session_id = _require_session_id(db, session)
    rows = db.list_recommendations(session_id, limit=limit)
    table = Table("ID", "Source", "Title", "Created")
    for row in rows:
        table.add_row(str(row["id"]), row["source"], row["title"], row["created_at"])
    console.print(table)
    for row in rows:
        console.rule(f"{row['id']} · {row['title']}")
        console.print(row["body"])


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
):
    """
    Launch a FastAPI-powered web UI for reviewing recommendations.
    """
    config, db, _ = bootstrap()
    fastapi_app = create_app(config, db)
    console.print(
        f"[bold green]Serving[/] http://{host}:{port} (Ctrl+C to stop)"
    )
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")
