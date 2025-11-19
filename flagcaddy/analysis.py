"""Analysis coordination and management."""

import time
from datetime import datetime
from typing import Dict, Any

from .db import Database
from .llm import CodexLLM
from .rules import EntityExtractor
from .config import ANALYSIS_INTERVAL, CODEX_EXEC_PATH


class AnalysisEngine:
    """Coordinates analysis of captured terminal activity."""

    def __init__(self, db: Database = None, llm: CodexLLM = None):
        self.db = db or Database()
        self.llm = llm or CodexLLM(CODEX_EXEC_PATH)
        self.extractor = EntityExtractor()
        self.last_analysis_time = None
        self.analysis_interval = ANALYSIS_INTERVAL

        # Change detection: track state at last analysis
        self.last_command_count = 0
        self.last_entity_counts = {}  # {entity_type: {entity_value: command_count}}

    def process_command(self, command: str, working_dir: str, output: str, session_id: str):
        """
        Process a newly captured command.

        Args:
            command: The command that was executed
            working_dir: Working directory where command was run
            output: Command output
            session_id: Session identifier
        """
        # Store command in database
        command_id = self.db.add_command(command, working_dir, output, session_id=session_id)

        # Extract entities
        entities = self.extractor.extract_entities(command, output)

        # Store entities and link to command
        for entity_type, value, metadata in entities:
            entity_id = self.db.add_entity(entity_type, value, metadata)
            self.db.link_entity_command(entity_id, command_id)

        print(f"[FlagCaddy] Processed command: {command[:60]}... (found {len(entities)} entities)")

    def has_changes_for_global_analysis(self) -> bool:
        """
        Check if there are new commands since last global analysis.

        Returns:
            True if there are new commands to analyze
        """
        commands = self.db.get_recent_commands(limit=1000)
        current_count = len(commands)

        if current_count > self.last_command_count:
            return True

        return False

    def run_global_analysis(self, force: bool = False) -> Dict[str, Any]:
        """
        Run global analysis on all recent activity.

        Args:
            force: If True, run analysis even if no changes detected

        Returns:
            Analysis results dictionary
        """
        # Check for changes
        if not force and not self.has_changes_for_global_analysis():
            print("[FlagCaddy] No new commands since last analysis, skipping global analysis")
            return {
                "summary": "No changes since last analysis",
                "discoveries": [],
                "next_steps": [],
                "notes": []
            }

        print("[FlagCaddy] Running global analysis...")

        # Get recent commands and entities
        commands = self.db.get_recent_commands(limit=50)
        entities = self.db.get_all_entities()

        # Update change tracking
        self.last_command_count = len(self.db.get_recent_commands(limit=1000))

        # Run LLM analysis
        try:
            analysis = self.llm.analyze_commands(commands, entities)

            # Store analysis
            recommendations = analysis.get('next_steps', [])
            summary = analysis.get('summary', 'No summary available')

            self.db.add_analysis(
                scope='global',
                summary=summary,
                recommendations=recommendations,
                metadata={
                    'discoveries': analysis.get('discoveries', []),
                    'notes': analysis.get('notes', [])
                }
            )

            print(f"[FlagCaddy] Global analysis complete: {len(recommendations)} recommendations")
            return analysis

        except Exception as e:
            print(f"[FlagCaddy] Error in global analysis: {e}")
            return {
                "summary": f"Analysis failed: {e}",
                "discoveries": [],
                "next_steps": [],
                "notes": []
            }

    def has_changes_for_entity(self, entity_type: str, entity_value: str, entity_id: int) -> bool:
        """
        Check if there are new commands for a specific entity since last analysis.

        Args:
            entity_type: Type of entity
            entity_value: Entity identifier
            entity_id: Database ID of entity

        Returns:
            True if there are new commands related to this entity
        """
        # Get current command count for this entity
        related_commands = self.db.get_entity_commands(entity_id)
        current_count = len(related_commands)

        # Initialize tracking for this entity type if needed
        if entity_type not in self.last_entity_counts:
            self.last_entity_counts[entity_type] = {}

        # Check if command count changed
        last_count = self.last_entity_counts[entity_type].get(entity_value, 0)

        return current_count > last_count

    def run_entity_analysis(self, entity_type: str = None, force: bool = False):
        """
        Run focused analysis on specific entities.

        Args:
            entity_type: If provided, only analyze entities of this type
            force: If True, run analysis even if no changes detected
        """
        print(f"[FlagCaddy] Running entity analysis (type: {entity_type or 'all'})...")

        entities_dict = self.db.get_all_entities()

        types_to_analyze = [entity_type] if entity_type else entities_dict.keys()

        analyzed_count = 0
        skipped_count = 0

        for etype in types_to_analyze:
            entities = entities_dict.get(etype, [])

            # Initialize tracking for this type
            if etype not in self.last_entity_counts:
                self.last_entity_counts[etype] = {}

            for entity in entities:
                entity_id = entity['id']
                entity_value = entity['value']

                # Get related commands
                related_commands = self.db.get_entity_commands(entity_id)

                if not related_commands:
                    continue

                # Check for changes
                if not force and not self.has_changes_for_entity(etype, entity_value, entity_id):
                    skipped_count += 1
                    continue

                # Run analysis
                try:
                    analysis = self.llm.analyze_entity(etype, entity_value, related_commands)

                    # Store analysis
                    self.db.add_analysis(
                        scope=etype,
                        scope_id=entity_value,
                        summary=analysis.get('status', ''),
                        recommendations=analysis.get('next_steps', []),
                        metadata={
                            'findings': analysis.get('findings', []),
                            'priority': analysis.get('priority', 'medium')
                        }
                    )

                    # Update change tracking
                    self.last_entity_counts[etype][entity_value] = len(related_commands)

                    print(f"[FlagCaddy] Analyzed {etype}: {entity_value}")
                    analyzed_count += 1

                except Exception as e:
                    print(f"[FlagCaddy] Error analyzing {etype} {entity_value}: {e}")

        if skipped_count > 0:
            print(f"[FlagCaddy] Skipped {skipped_count} entities with no changes")

    def analysis_loop(self):
        """
        Main analysis loop that periodically runs analysis.
        """
        print(f"[FlagCaddy] Starting analysis loop (interval: {self.analysis_interval}s)")

        while True:
            try:
                # Run global analysis
                self.run_global_analysis()

                # Run entity analysis for high-priority types
                for entity_type in ['host', 'service', 'vulnerability']:
                    self.run_entity_analysis(entity_type)

                # Wait for next analysis cycle
                time.sleep(self.analysis_interval)

            except KeyboardInterrupt:
                print("\n[FlagCaddy] Analysis loop stopped")
                break
            except Exception as e:
                print(f"[FlagCaddy] Error in analysis loop: {e}")
                time.sleep(self.analysis_interval)
