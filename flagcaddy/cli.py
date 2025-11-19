"""Command-line interface for FlagCaddy."""

import sys
import click
import threading
from pathlib import Path

from . import __version__
from .engine import FlagCaddyEngine
from .web import run_web_server
from .db import Database
from .config import DB_PATH, FLAGCADDY_DIR, WEB_HOST, WEB_PORT


@click.group()
@click.version_option(version=__version__)
def main():
    """FlagCaddy - AI-powered background coach for pentesters and CTF competitors."""
    pass


@main.command()
@click.option('--capture-interval', default=2, help='Seconds between terminal capture checks')
@click.option('--analysis-interval', default=30, help='Seconds between analysis runs')
@click.option('--web/--no-web', default=True, help='Start web UI server')
@click.option('--host', default=WEB_HOST, help='Web server host')
@click.option('--port', default=WEB_PORT, help='Web server port')
def start(capture_interval, analysis_interval, web, host, port):
    """Start the FlagCaddy background monitoring and analysis."""
    click.echo(click.style('FlagCaddy v{}'.format(__version__), fg='green', bold=True))
    click.echo(click.style('AI-Powered Pentesting & CTF Coach', fg='cyan'))
    click.echo()

    # Initialize engine
    engine = FlagCaddyEngine()

    # Start web server in a separate thread if requested
    web_thread = None
    if web:
        click.echo(f'Starting web UI at http://{host}:{port}')
        web_thread = threading.Thread(
            target=run_web_server,
            args=(engine.db, host, port),
            daemon=True
        )
        web_thread.start()

    # Start the main engine
    try:
        engine.start(capture_interval, analysis_interval)

        # Keep main thread alive
        if web_thread:
            web_thread.join()
        else:
            # If no web server, just wait
            import time
            while engine.running:
                time.sleep(1)

    except KeyboardInterrupt:
        engine.stop()
        click.echo('\nFlagCaddy stopped')


@main.command()
def status():
    """Show current FlagCaddy status and statistics."""
    db = Database()

    click.echo(click.style('FlagCaddy Status', fg='green', bold=True))
    click.echo()

    # Commands
    recent_commands = db.get_recent_commands(limit=1000)
    click.echo(f'Total commands captured: {len(recent_commands)}')

    # Entities
    entities = db.get_all_entities()
    click.echo('\nDiscovered entities:')
    for entity_type, entity_list in entities.items():
        click.echo(f'  {entity_type}: {len(entity_list)}')

    # Latest analysis
    global_analysis = db.get_analysis(scope='global', limit=1)
    if global_analysis:
        analysis = global_analysis[0]
        click.echo('\nLatest global analysis:')
        click.echo(f'  Time: {analysis["timestamp"]}')
        click.echo(f'  Summary: {analysis["summary"][:100]}...')

        recommendations = analysis['recommendations']
        if isinstance(recommendations, str):
            import json
            recommendations = json.loads(recommendations)

        click.echo(f'  Recommendations: {len(recommendations)}')


@main.command()
def analyze():
    """Run analysis once on captured data (useful for testing)."""
    click.echo('Running one-time analysis...')

    engine = FlagCaddyEngine()
    engine.run_analysis_once()

    click.echo('Analysis complete. View results with: flagcaddy status')


@main.command()
@click.option('--type', 'entity_type', help='Filter by entity type (host, port, service, etc.)')
@click.option('--limit', default=20, help='Number of entities to show')
def entities(entity_type, limit):
    """List discovered entities."""
    db = Database()

    if entity_type:
        entity_list = db.get_entities_by_type(entity_type)
        click.echo(click.style(f'{entity_type.upper()} Entities', fg='cyan', bold=True))
    else:
        all_entities = db.get_all_entities()
        entity_list = []
        for entities in all_entities.values():
            entity_list.extend(entities)
        click.echo(click.style('All Entities', fg='cyan', bold=True))

    entity_list = entity_list[:limit]

    for entity in entity_list:
        click.echo(f"\n{click.style(entity['value'], fg='green', bold=True)}")
        click.echo(f"  Type: {entity['type']}")
        click.echo(f"  First seen: {entity['first_seen']}")
        click.echo(f"  Last seen: {entity['last_seen']}")

        # Get analysis for this entity
        analysis = db.get_analysis(scope=entity['type'], scope_id=entity['value'], limit=1)
        if analysis:
            import json
            recs = json.loads(analysis[0]['recommendations'])
            if recs:
                click.echo(f"  Recommendations:")
                for rec in recs[:3]:
                    click.echo(f"    - {rec}")


@main.command()
@click.option('--limit', default=20, help='Number of commands to show')
def commands(limit):
    """List recent captured commands."""
    db = Database()

    recent_commands = db.get_recent_commands(limit=limit)

    click.echo(click.style('Recent Commands', fg='cyan', bold=True))
    click.echo()

    for cmd in recent_commands:
        timestamp = cmd['timestamp'][:19]  # Truncate microseconds
        click.echo(f"{click.style(timestamp, fg='yellow')} | {cmd['working_dir']}")
        click.echo(f"$ {click.style(cmd['command'], fg='green')}")
        click.echo()


@main.command()
def web():
    """Start only the web UI server (analysis must be running separately)."""
    click.echo(f'Starting FlagCaddy web UI at http://{WEB_HOST}:{WEB_PORT}')
    click.echo('Press Ctrl+C to stop')

    try:
        run_web_server()
    except KeyboardInterrupt:
        click.echo('\nWeb server stopped')


@main.command()
@click.option('--commands', is_flag=True, help='Delete only commands and command log')
@click.option('--analysis', is_flag=True, help='Delete only analysis results')
@click.option('--entities', is_flag=True, help='Delete only entities')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation prompt')
def reset(commands, analysis, entities, force):
    """Reset captured data (database and/or command log).

    Without options, deletes everything. Use flags for partial reset.
    """
    from pathlib import Path

    # Determine what to delete
    delete_all = not (commands or analysis or entities)

    items_to_delete = []
    if delete_all:
        items_to_delete.append("ALL data (database + command log)")
    else:
        if commands:
            items_to_delete.append("commands and command log")
        if analysis:
            items_to_delete.append("analysis results")
        if entities:
            items_to_delete.append("entities")

    # Confirmation
    message = f"This will delete: {', '.join(items_to_delete)}. Continue?"
    if not force and not click.confirm(message):
        click.echo('Reset cancelled')
        return

    # Perform deletion
    if delete_all:
        # Delete everything
        deleted = []

        if DB_PATH.exists():
            DB_PATH.unlink()
            deleted.append("database")

        jsonl_log = FLAGCADDY_DIR / "commands.jsonl"
        if jsonl_log.exists():
            jsonl_log.unlink()
            deleted.append("command log")

        if deleted:
            click.echo(f"Deleted: {', '.join(deleted)}")
        else:
            click.echo("Nothing to delete (already clean)")

    else:
        # Selective deletion
        db = Database()

        if commands:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM entity_commands")
                cursor.execute("DELETE FROM commands")
                click.echo("✓ Deleted all commands")

            jsonl_log = FLAGCADDY_DIR / "commands.jsonl"
            if jsonl_log.exists():
                jsonl_log.unlink()
                click.echo("✓ Deleted command log file")

        if analysis:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM analysis")
                click.echo("✓ Deleted all analysis results")

        if entities:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM entity_commands")
                cursor.execute("DELETE FROM entities")
                cursor.execute("DELETE FROM analysis WHERE scope != 'global'")
                click.echo("✓ Deleted all entities and entity-specific analysis")

    click.echo()
    click.echo(click.style('Reset complete!', fg='green', bold=True))


@main.command()
@click.option('--force', '-f', is_flag=True, help='Skip confirmation prompt')
def purge(force):
    """Completely purge all FlagCaddy data (nuclear option).

    Deletes:
    - Database (commands, entities, analysis)
    - Command log file
    - All captured data

    This is equivalent to: flagcaddy reset --force
    """
    if not force and not click.confirm(
        click.style('⚠ WARNING: This will DELETE ALL FlagCaddy data. Continue?', fg='red', bold=True)
    ):
        click.echo('Purge cancelled')
        return

    deleted = []

    # Delete database
    if DB_PATH.exists():
        DB_PATH.unlink()
        deleted.append("database")
        click.echo("✓ Deleted database")

    # Delete command log
    jsonl_log = FLAGCADDY_DIR / "commands.jsonl"
    if jsonl_log.exists():
        jsonl_log.unlink()
        deleted.append("command log")
        click.echo("✓ Deleted command log")

    # Could also delete other files in .flagcaddy if needed
    # For now, just DB and log

    if deleted:
        click.echo()
        click.echo(click.style('All data purged!', fg='green', bold=True))
        click.echo('FlagCaddy is now in a clean state.')
    else:
        click.echo('Nothing to purge (already clean)')


@main.command()
def cleanup():
    """Remove false positive entities (files, git config, etc.)."""
    from .rules import EntityExtractor

    click.echo('Cleaning up false positive entities...')

    db = Database()
    extractor = EntityExtractor()

    # Get all host entities
    hosts = db.get_entities_by_type('host')

    removed_count = 0
    kept_count = 0

    for host in hosts:
        entity_value = host['value']

        # Check if it's a valid domain
        if not extractor._is_valid_domain(entity_value):
            # This is a false positive, remove it
            with db.get_connection() as conn:
                cursor = conn.cursor()
                # Delete entity_commands links
                cursor.execute("DELETE FROM entity_commands WHERE entity_id = ?", (host['id'],))
                # Delete analysis for this entity
                cursor.execute("DELETE FROM analysis WHERE scope = 'host' AND scope_id = ?", (entity_value,))
                # Delete the entity
                cursor.execute("DELETE FROM entities WHERE id = ?", (host['id'],))

            click.echo(f"  Removed: {entity_value}")
            removed_count += 1
        else:
            kept_count += 1

    click.echo()
    click.echo(f'Cleanup complete:')
    click.echo(f'  Removed: {removed_count} false positives')
    click.echo(f'  Kept: {kept_count} valid hosts')


@main.command()
@click.option('--install', is_flag=True, help='Add to ~/.bashrc or ~/.zshrc')
@click.option('--show', is_flag=True, help='Show the source command')
def shell(install, show):
    """Enable shell integration for command capture.

    This allows you to use 'fc' command to capture commands with output.

    Usage:
      eval "$(flagcaddy shell)"       # Enable in current shell
      flagcaddy shell --install       # Add to ~/.bashrc or ~/.zshrc
      flagcaddy shell --show          # Show the source command
    """
    from pathlib import Path
    import os

    # Find the shell integration script
    integration_paths = [
        Path(__file__).parent / "shell_integration.sh",
        FLAGCADDY_DIR.parent / "flagcaddy" / "flagcaddy" / "shell_integration.sh",
    ]

    integration_file = None
    for path in integration_paths:
        if path.exists():
            integration_file = path
            break

    if not integration_file:
        click.echo(click.style('Error: shell_integration.sh not found', fg='red'))
        click.echo('Try reinstalling FlagCaddy')
        return

    # Show mode - just print the source command
    if show:
        click.echo(f'source {integration_file}')
        return

    # Install mode - add to shell rc file
    if install:
        shell_env = os.environ.get('SHELL', '')
        if 'zsh' in shell_env:
            rc_file = Path.home() / '.zshrc'
        elif 'bash' in shell_env:
            rc_file = Path.home() / '.bashrc'
        else:
            click.echo(click.style('Error: Could not detect shell type', fg='red'))
            click.echo(f'Shell: {shell_env}')
            click.echo('Manually add to your rc file:')
            click.echo(f'  source {integration_file}')
            return

        source_line = f'source {integration_file}'

        # Check if already installed
        if rc_file.exists():
            with open(rc_file, 'r') as f:
                content = f.read()
                if source_line in content or 'shell_integration.sh' in content:
                    click.echo(click.style('Already installed!', fg='yellow'))
                    click.echo(f'Found in: {rc_file}')
                    return

        # Add to rc file
        with open(rc_file, 'a') as f:
            f.write(f'\n# FlagCaddy shell integration\n')
            f.write(f'{source_line}\n')

        click.echo(click.style('Installed!', fg='green', bold=True))
        click.echo(f'Added to: {rc_file}')
        click.echo()
        click.echo('To activate in current shell, run:')
        click.echo(f'  source {rc_file}')
        click.echo()
        click.echo('Or start a new terminal session.')
        return

    # Default mode - output source command for eval
    # This allows: eval "$(flagcaddy shell)"
    click.echo(f'source {integration_file}')


@main.command()
def info():
    """Show FlagCaddy configuration and paths."""
    click.echo(click.style('FlagCaddy Configuration', fg='green', bold=True))
    click.echo()
    click.echo(f'Version: {__version__}')
    click.echo(f'Data directory: {FLAGCADDY_DIR}')
    click.echo(f'Database: {DB_PATH}')
    click.echo(f'Web UI bind address: {WEB_HOST}:{WEB_PORT}')

    if WEB_HOST == '0.0.0.0':
        click.echo(f'  Local access: http://localhost:{WEB_PORT}')
        click.echo(f'  Network access: http://YOUR_IP:{WEB_PORT}')
        click.echo(click.style('  ⚠ Warning: Accessible from network (no authentication)', fg='yellow'))
    else:
        click.echo(f'  Access: http://{WEB_HOST}:{WEB_PORT}')

    click.echo()
    click.echo('To start monitoring:')
    click.echo('  flagcaddy start')
    click.echo()
    click.echo('To enable shell integration:')
    click.echo('  eval "$(flagcaddy shell)"')


if __name__ == '__main__':
    main()
