"""Terminal capture for monitoring user commands and output."""

import os
import json
import time
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

from .config import FLAGCADDY_DIR


# JSONL log file from shell integration
JSONL_LOG = FLAGCADDY_DIR / "commands.jsonl"


class TerminalCapture:
    """Captures terminal commands and output by monitoring JSONL log file from shell integration."""

    def __init__(self, callback: Optional[Callable] = None, log_file: Path = JSONL_LOG):
        """
        Initialize terminal capture.

        Args:
            callback: Function to call with (command, working_dir, output, session_id) when a new command is detected
            log_file: Path to JSONL log file to monitor
        """
        self.callback = callback
        self.log_file = log_file
        self.last_position = 0

        # Create log file if it doesn't exist
        self.log_file.touch()

        # Initialize position to end of file (don't reprocess old commands on startup)
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                f.seek(0, 2)  # Seek to end
                self.last_position = f.tell()

        self.session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    def monitor_jsonl_log(self) -> list:
        """
        Monitor the JSONL log file for new entries.

        Returns:
            List of new command dictionaries
        """
        if not self.log_file.exists():
            return []

        new_commands = []

        try:
            with open(self.log_file, 'r') as f:
                # Seek to last position
                f.seek(self.last_position)

                # Read new lines
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        # Parse JSON line
                        cmd_data = json.loads(line)
                        new_commands.append(cmd_data)
                    except json.JSONDecodeError as e:
                        print(f"[FlagCaddy] Error parsing JSON line: {e}")
                        continue

                # Update position
                self.last_position = f.tell()

        except Exception as e:
            print(f"[FlagCaddy] Error reading log file: {e}")

        return new_commands

    def get_command_count(self) -> int:
        """Get total number of commands in log file."""
        if not self.log_file.exists():
            return 0

        try:
            with open(self.log_file, 'r') as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def monitor_loop(self, interval: int = 2):
        """
        Main monitoring loop that checks for new commands periodically.

        Args:
            interval: Seconds between checks
        """
        print(f"[FlagCaddy] Starting terminal monitoring")
        print(f"[FlagCaddy] Monitoring: {self.log_file}")
        print()
        print("[FlagCaddy] To capture commands with output, source the shell integration:")

        # Try to find shell_integration.sh
        integration_paths = [
            Path(__file__).parent / "shell_integration.sh",
            FLAGCADDY_DIR.parent / "flagcaddy" / "flagcaddy" / "shell_integration.sh",
        ]

        integration_file = None
        for path in integration_paths:
            if path.exists():
                integration_file = path
                break

        if integration_file:
            print(f"[FlagCaddy]   source {integration_file}")
        else:
            print(f"[FlagCaddy]   source <path-to>/flagcaddy/shell_integration.sh")

        print("[FlagCaddy]   Then use: fc <command>")
        print("[FlagCaddy]   Example: fc nmap -sV 10.10.10.5")
        print()

        command_count = self.get_command_count()
        if command_count > 0:
            print(f"[FlagCaddy] Found {command_count} existing commands in log")

        while True:
            try:
                # Check for new commands in JSONL log
                new_commands = self.monitor_jsonl_log()

                # Process each new command
                for cmd_data in new_commands:
                    if self.callback:
                        self.callback(
                            cmd_data.get('command', ''),
                            cmd_data.get('working_dir', ''),
                            cmd_data.get('output', ''),
                            cmd_data.get('session_id', self.session_id)
                        )

                time.sleep(interval)

            except KeyboardInterrupt:
                print("\n[FlagCaddy] Monitoring stopped")
                break
            except Exception as e:
                print(f"[FlagCaddy] Error in monitoring loop: {e}")
                time.sleep(interval)
