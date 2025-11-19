"""LLM integration using codex exec."""

import json
import subprocess
from typing import List, Dict, Any, Optional


class CodexLLM:
    """Interface to LLM via codex exec."""

    def __init__(self, codex_exec_path: str = "codex"):
        self.codex_exec_path = codex_exec_path

    def execute(self, prompt: str, system_prompt: str = None) -> str:
        """
        Execute a prompt using codex exec.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt (will be prepended to prompt)

        Returns:
            The LLM's response
        """
        try:
            # Combine system prompt and user prompt
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            # Build the command
            cmd = [self.codex_exec_path, "exec", full_prompt]

            # Execute
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # Increased timeout for analysis
            )

            if result.returncode != 0:
                raise Exception(f"codex exec failed: {result.stderr}")

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise Exception("codex exec timed out")
        except FileNotFoundError:
            raise Exception(f"codex exec not found at: {self.codex_exec_path}")
        except Exception as e:
            raise Exception(f"Error executing codex: {e}")

    def analyze_commands(self, commands: List[Dict[str, Any]],
                        entities: Dict[str, List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Analyze recent commands and provide recommendations.

        Args:
            commands: List of command dictionaries
            entities: Dictionary of entities by type

        Returns:
            Dictionary with summary and recommendations
        """
        # Build context
        context = self._build_context(commands, entities)

        system_prompt = """You are an expert penetration tester and CTF competitor assistant.
Analyze the user's terminal activity and provide strategic recommendations for next steps.
Focus on:
1. What has been discovered so far
2. What hasn't been fully explored yet
3. Specific next actions to take
4. Potential vulnerabilities or attack vectors

Respond in JSON format with the following structure:
{
  "summary": "Brief overview of what's been done",
  "discoveries": ["key finding 1", "key finding 2"],
  "next_steps": ["specific action 1", "specific action 2"],
  "notes": ["additional observation 1"]
}"""

        prompt = f"""Analyze this pentesting/CTF activity and provide recommendations:

{context}

Provide your analysis in JSON format."""

        try:
            response = self.execute(prompt, system_prompt)
            # Try to parse as JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # If not JSON, wrap it
            return {
                "summary": response,
                "discoveries": [],
                "next_steps": [],
                "notes": []
            }

    def analyze_entity(self, entity_type: str, entity_value: str,
                      related_commands: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze a specific entity (host, service, etc.) and provide focused recommendations.

        Args:
            entity_type: Type of entity (host, port, service, etc.)
            entity_value: The entity identifier
            related_commands: Commands related to this entity

        Returns:
            Dictionary with summary and recommendations specific to this entity
        """
        context = f"Entity Type: {entity_type}\nEntity: {entity_value}\n\n"
        context += "Related Activity:\n"
        for cmd in related_commands[-20:]:  # Last 20 commands
            context += f"- [{cmd.get('timestamp', 'N/A')}] {cmd.get('command', '')}\n"
            if cmd.get('output'):
                # Truncate output
                output = cmd['output'][:500]
                context += f"  Output: {output}\n"

        system_prompt = f"""You are analyzing a specific {entity_type} during a penetration test or CTF.
Focus your recommendations on this specific target.
Consider what's been tried, what worked, what didn't, and what should be tried next.

Respond in JSON format:
{{
  "status": "description of current state",
  "findings": ["finding 1", "finding 2"],
  "next_steps": ["specific action 1", "specific action 2"],
  "priority": "low|medium|high"
}}"""

        prompt = f"""Analyze this specific target and provide focused recommendations:

{context}

Provide your analysis in JSON format."""

        try:
            response = self.execute(prompt, system_prompt)
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "status": response,
                "findings": [],
                "next_steps": [],
                "priority": "medium"
            }

    def _build_context(self, commands: List[Dict[str, Any]],
                      entities: Dict[str, List[Dict[str, Any]]] = None) -> str:
        """Build context string from commands and entities."""
        context = "Recent Terminal Activity:\n\n"

        # Add command history
        context += "Commands:\n"
        for cmd in commands[-30:]:  # Last 30 commands
            context += f"[{cmd.get('timestamp', 'N/A')}] {cmd.get('working_dir', '')}\n"
            context += f"$ {cmd.get('command', '')}\n"

            # Add truncated output if available
            output = cmd.get('output', '')
            if output:
                output_preview = output[:300] + "..." if len(output) > 300 else output
                context += f"{output_preview}\n"
            context += "\n"

        # Add discovered entities
        if entities:
            context += "\nDiscovered Entities:\n"
            for entity_type, entity_list in entities.items():
                if entity_list:
                    context += f"\n{entity_type.upper()}:\n"
                    for entity in entity_list[:10]:  # Limit to 10 per type
                        context += f"  - {entity.get('value', '')} "
                        context += f"(first seen: {entity.get('first_seen', 'N/A')})\n"

        return context
