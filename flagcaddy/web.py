"""Web UI for FlagCaddy using Flask and Socket.IO."""

import json
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
import threading
import time

from .db import Database
from .config import WEB_HOST, WEB_PORT


def create_app(db: Database = None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'flagcaddy-secret-key-change-in-production'

    # Initialize Socket.IO
    socketio = SocketIO(app, cors_allowed_origins="*")

    # Database instance
    if db is None:
        db = Database()

    @app.route('/')
    def index():
        """Main dashboard page."""
        return render_template('index.html')

    @app.route('/api/status')
    def api_status():
        """Get current status."""
        recent_commands = db.get_recent_commands(limit=20)
        entities = db.get_all_entities()

        entity_counts = {etype: len(elist) for etype, elist in entities.items()}

        return jsonify({
            "total_commands": len(recent_commands),
            "entities": entity_counts,
            "timestamp": datetime.utcnow().isoformat()
        })

    @app.route('/api/commands')
    def api_commands():
        """Get recent commands."""
        limit = int(request.args.get('limit', 50))
        commands = db.get_recent_commands(limit=limit)
        return jsonify(commands)

    @app.route('/api/entities')
    def api_entities():
        """Get all discovered entities."""
        entities = db.get_all_entities()
        return jsonify(entities)

    @app.route('/api/entities/<entity_type>')
    def api_entities_by_type(entity_type):
        """Get entities of a specific type."""
        entities = db.get_entities_by_type(entity_type)
        return jsonify(entities)

    @app.route('/api/analysis')
    def api_analysis():
        """Get global analysis."""
        analysis = db.get_analysis(scope='global', limit=5)
        return jsonify(analysis)

    @app.route('/api/analysis/<entity_type>/<path:entity_value>')
    def api_entity_analysis(entity_type, entity_value):
        """Get analysis for a specific entity."""
        analysis = db.get_analysis(scope=entity_type, scope_id=entity_value, limit=5)
        return jsonify(analysis)

    @app.route('/api/dashboard')
    def api_dashboard():
        """Get complete dashboard data."""
        # Global analysis
        global_analysis = db.get_analysis(scope='global', limit=1)
        latest_global = global_analysis[0] if global_analysis else None

        # Get all entities with their analyses
        entities = db.get_all_entities()

        # Organize entity data with their latest analysis
        organized_entities = {}
        for entity_type, entity_list in entities.items():
            organized_entities[entity_type] = []

            for entity in entity_list:
                entity_data = dict(entity)

                # Get latest analysis for this entity
                entity_analysis = db.get_analysis(
                    scope=entity_type,
                    scope_id=entity['value'],
                    limit=1
                )

                entity_data['analysis'] = entity_analysis[0] if entity_analysis else None
                organized_entities[entity_type].append(entity_data)

        # Recent commands
        recent_commands = db.get_recent_commands(limit=20)

        return jsonify({
            "global_analysis": latest_global,
            "entities": organized_entities,
            "recent_commands": recent_commands,
            "timestamp": datetime.utcnow().isoformat()
        })

    # Socket.IO event handlers
    @socketio.on('connect')
    def handle_connect():
        print('[FlagCaddy] Web client connected')

    @socketio.on('disconnect')
    def handle_disconnect():
        print('[FlagCaddy] Web client disconnected')

    # Background task to push updates to clients
    def push_updates():
        """Push periodic updates to connected clients."""
        while True:
            time.sleep(5)  # Update every 5 seconds
            try:
                # Get latest data
                dashboard_data = {
                    "global_analysis": db.get_analysis(scope='global', limit=1),
                    "entity_counts": {
                        etype: len(elist)
                        for etype, elist in db.get_all_entities().items()
                    },
                    "recent_commands": db.get_recent_commands(limit=5),
                    "timestamp": datetime.utcnow().isoformat()
                }

                socketio.emit('update', dashboard_data)
            except Exception as e:
                print(f'[FlagCaddy] Error pushing update: {e}')

    # Start background update thread
    update_thread = threading.Thread(target=push_updates, daemon=True)
    update_thread.start()

    return app, socketio


def run_web_server(db: Database = None, host: str = WEB_HOST, port: int = WEB_PORT):
    """Run the web server."""
    app, socketio = create_app(db)
    print(f"[FlagCaddy] Starting web server at http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
