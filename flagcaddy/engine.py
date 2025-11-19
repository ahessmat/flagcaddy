"""Main FlagCaddy engine that coordinates all components."""

import threading
import time
from typing import Optional

from .db import Database
from .capture import TerminalCapture
from .analysis import AnalysisEngine
from .config import ANALYSIS_INTERVAL


class FlagCaddyEngine:
    """Main engine that coordinates terminal capture, analysis, and UI updates."""

    def __init__(self):
        self.db = Database()
        self.analysis_engine = AnalysisEngine(self.db)
        self.capture = None
        self.threads = []
        self.running = False

    def on_command_captured(self, command: str, working_dir: str, output: str, session_id: str):
        """
        Callback for when a new command is captured.

        Args:
            command: The command that was executed
            working_dir: Working directory
            output: Command output
            session_id: Session identifier
        """
        self.analysis_engine.process_command(command, working_dir, output, session_id)

    def start(self, capture_interval: int = 2, analysis_interval: int = ANALYSIS_INTERVAL):
        """
        Start the FlagCaddy engine.

        Args:
            capture_interval: Seconds between terminal capture checks
            analysis_interval: Seconds between analysis runs
        """
        if self.running:
            print("[FlagCaddy] Already running")
            return

        self.running = True
        print("[FlagCaddy] Starting FlagCaddy engine...")

        # Initialize terminal capture
        self.capture = TerminalCapture(callback=self.on_command_captured)

        # Update analysis interval
        self.analysis_engine.analysis_interval = analysis_interval

        # Start capture thread
        capture_thread = threading.Thread(
            target=self.capture.monitor_loop,
            args=(capture_interval,),
            daemon=True
        )
        capture_thread.start()
        self.threads.append(capture_thread)

        print("[FlagCaddy] Terminal monitoring started")

        # Start analysis thread
        analysis_thread = threading.Thread(
            target=self.analysis_engine.analysis_loop,
            daemon=True
        )
        analysis_thread.start()
        self.threads.append(analysis_thread)

        print("[FlagCaddy] Analysis engine started")
        print(f"[FlagCaddy] Web UI will be available at http://localhost:5000")
        print("[FlagCaddy] All systems running. Press Ctrl+C to stop.")

    def stop(self):
        """Stop the FlagCaddy engine."""
        print("\n[FlagCaddy] Stopping FlagCaddy engine...")
        self.running = False

        # Threads are daemon threads, so they'll stop when main thread exits

    def run_analysis_once(self):
        """Run analysis once and exit (useful for testing)."""
        print("[FlagCaddy] Running one-time analysis...")
        self.analysis_engine.run_global_analysis()
        self.analysis_engine.run_entity_analysis()
        print("[FlagCaddy] Analysis complete")

    def get_status(self) -> dict:
        """Get current status of the engine."""
        recent_commands = self.db.get_recent_commands(limit=10)
        entities = self.db.get_all_entities()
        global_analysis = self.db.get_analysis(scope='global', limit=1)

        entity_counts = {etype: len(elist) for etype, elist in entities.items()}

        return {
            "running": self.running,
            "total_commands": len(self.db.get_recent_commands(limit=1000)),
            "recent_commands": len(recent_commands),
            "entities": entity_counts,
            "latest_analysis": global_analysis[0] if global_analysis else None
        }
