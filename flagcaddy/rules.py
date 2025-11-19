"""Entity extraction and organization rules."""

import re
from typing import List, Dict, Tuple, Any

from .config import IP_PATTERN, DOMAIN_PATTERN, PORT_PATTERN


class EntityExtractor:
    """Extracts entities (hosts, networks, services, etc.) from command output."""

    def __init__(self):
        self.ip_regex = re.compile(IP_PATTERN)
        self.domain_regex = re.compile(DOMAIN_PATTERN)
        self.port_regex = re.compile(PORT_PATTERN, re.IGNORECASE)

    def extract_entities(self, command: str, output: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """
        Extract entities from command and output.

        Returns:
            List of tuples: (entity_type, value, metadata)
        """
        entities = []

        # Extract IPs
        for ip in self.ip_regex.findall(command + " " + output):
            if self._is_valid_ip(ip):
                entities.append(("host", ip, {"source": "ip"}))

        # Extract domains
        for domain in self.domain_regex.findall(command + " " + output):
            if self._is_valid_domain(domain):
                entities.append(("host", domain, {"source": "domain"}))

        # Extract ports with context
        entities.extend(self._extract_ports(output))

        # Extract network ranges
        entities.extend(self._extract_networks(command + " " + output))

        # Tool-specific extraction
        entities.extend(self._extract_from_nmap(command, output))
        entities.extend(self._extract_from_gobuster(command, output))
        entities.extend(self._extract_from_nikto(command, output))
        entities.extend(self._extract_from_sqlmap(command, output))

        return entities

    def _is_valid_ip(self, ip: str) -> bool:
        """Check if IP is valid and not a common false positive."""
        parts = ip.split('.')
        if len(parts) != 4:
            return False

        try:
            # Filter out invalid IPs and common false positives
            nums = [int(p) for p in parts]
            if any(n > 255 for n in nums):
                return False
            # Ignore version numbers like 1.2.3.4
            if all(n < 10 for n in nums):
                return False
            return True
        except ValueError:
            return False

    def _is_valid_domain(self, domain: str) -> bool:
        """Check if domain is valid and not a common false positive."""
        domain_lower = domain.lower()

        # Must be reasonable length
        if len(domain) < 4 or len(domain) > 253:
            return False

        # Filter out file extensions (comprehensive list)
        file_extensions = [
            '.txt', '.log', '.json', '.xml', '.html', '.js', '.css', '.py', '.sh',
            '.md', '.rst', '.yaml', '.yml', '.toml', '.ini', '.conf', '.cfg',
            '.jpg', '.png', '.gif', '.svg', '.ico', '.pdf', '.zip', '.tar', '.gz',
            '.exe', '.dll', '.so', '.dylib', '.bin', '.dat', '.db', '.sql',
            '.c', '.cpp', '.h', '.java', '.go', '.rs', '.rb', '.php', '.pl',
            '.egg', '.whl', '.pyc', '.pyo', '.class', '.jar', '.war',
            '.bak', '.tmp', '.swp', '.lock', '.cache', '.old', '.orig'
        ]
        if any(domain_lower.endswith(ext) for ext in file_extensions):
            return False

        # Filter out git config keys
        git_config_patterns = [
            'user.name', 'user.email', 'core.editor', 'credential.helper',
            'remote.origin', 'branch.main', 'branch.master', 'init.defaultbranch',
            'core.autocrlf', 'core.filemode', 'merge.tool', 'diff.tool',
            'pull.rebase', 'push.default', 'color.ui'
        ]
        if domain_lower in git_config_patterns:
            return False

        # Filter out common config/code patterns
        if any(pattern in domain_lower for pattern in ['config.', 'settings.', 'package.']):
            return False

        # Check TLD is valid (at least 2 chars, all letters)
        parts = domain.split('.')
        if len(parts) < 2:
            return False

        tld = parts[-1]
        if len(tld) < 2 or not tld.isalpha():
            return False

        # Valid TLDs (common ones to whitelist)
        # This is not exhaustive but covers most legit cases
        valid_tlds = {
            'com', 'org', 'net', 'edu', 'gov', 'mil', 'int',
            'io', 'co', 'us', 'uk', 'de', 'fr', 'jp', 'cn', 'au', 'ca',
            'local', 'localhost', 'lan', 'htb', 'thm', 'ctf', 'box',
            'app', 'dev', 'test', 'example', 'invalid',
            'xyz', 'tech', 'online', 'site', 'website', 'space',
            'ru', 'br', 'in', 'nl', 'ch', 'se', 'no', 'dk', 'fi'
        }

        # For pentest/CTF, be more lenient with certain TLDs
        if tld.lower() not in valid_tlds:
            # Must have at least 3 parts for non-standard TLD (e.g., api.custom.tld)
            if len(parts) < 3:
                return False

        # Each part should be valid (letters, numbers, hyphens)
        for part in parts[:-1]:  # Check all except TLD
            if not part or len(part) > 63:
                return False
            if not re.match(r'^[a-zA-Z0-9-]+$', part):
                return False
            if part.startswith('-') or part.endswith('-'):
                return False

        # Filter out patterns that look like version numbers
        if all(part.replace('-', '').isdigit() or len(part) <= 2 for part in parts[:-1]):
            return False

        return True

    def _extract_ports(self, text: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Extract port numbers with context."""
        entities = []
        lines = text.split('\n')

        for line in lines:
            # Look for open ports in nmap-style output
            if 'open' in line.lower():
                port_match = re.search(r'(\d+)/(tcp|udp)', line)
                if port_match:
                    port = port_match.group(1)
                    protocol = port_match.group(2)
                    # Try to extract service name
                    service_match = re.search(r'(?:tcp|udp)\s+(\S+)', line)
                    service = service_match.group(1) if service_match else "unknown"

                    entities.append(("port", f"{port}/{protocol}", {
                        "port": int(port),
                        "protocol": protocol,
                        "service": service,
                        "state": "open"
                    }))

        return entities

    def _extract_networks(self, text: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Extract network ranges (CIDR notation)."""
        entities = []
        cidr_pattern = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2})\b')

        for cidr in cidr_pattern.findall(text):
            entities.append(("network", cidr, {}))

        return entities

    def _extract_from_nmap(self, command: str, output: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Extract entities from nmap output."""
        entities = []

        if 'nmap' not in command.lower():
            return entities

        # Extract OS detection
        os_match = re.search(r'OS details:\s*(.+)', output)
        if os_match:
            entities.append(("os", os_match.group(1).strip(), {"tool": "nmap"}))

        # Extract service versions
        version_pattern = re.compile(r'(\d+/\w+)\s+open\s+(\S+)\s+(.+?)(?:\n|$)')
        for match in version_pattern.finditer(output):
            port, service, version = match.groups()
            entities.append(("service", f"{service}:{port}", {
                "port": port,
                "service": service,
                "version": version.strip(),
                "tool": "nmap"
            }))

        return entities

    def _extract_from_gobuster(self, command: str, output: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Extract entities from gobuster output."""
        entities = []

        if 'gobuster' not in command.lower():
            return entities

        # Extract discovered paths
        path_pattern = re.compile(r'(/\S+)\s+\(Status:\s*(\d+)\)')
        for match in path_pattern.finditer(output):
            path, status = match.groups()
            entities.append(("web_path", path, {
                "status_code": int(status),
                "tool": "gobuster"
            }))

        return entities

    def _extract_from_nikto(self, command: str, output: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Extract entities from nikto output."""
        entities = []

        if 'nikto' not in command.lower():
            return entities

        # Extract findings
        if '+ OSVDB-' in output or 'OSVDB-' in output:
            entities.append(("vulnerability", "nikto_findings", {
                "tool": "nikto",
                "has_findings": True
            }))

        return entities

    def _extract_from_sqlmap(self, command: str, output: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Extract entities from sqlmap output."""
        entities = []

        if 'sqlmap' not in command.lower():
            return entities

        # Check for SQL injection
        if 'is vulnerable' in output.lower() or 'parameter' in output.lower() and 'injectable' in output.lower():
            entities.append(("vulnerability", "sql_injection", {
                "tool": "sqlmap",
                "confirmed": True
            }))

        return entities


def categorize_command(command: str) -> str:
    """Categorize a command by its primary purpose."""
    command_lower = command.lower()

    if any(tool in command_lower for tool in ['nmap', 'masscan', 'rustscan']):
        return "reconnaissance:port_scan"
    elif any(tool in command_lower for tool in ['gobuster', 'dirb', 'dirbuster', 'ffuf']):
        return "reconnaissance:web_enumeration"
    elif any(tool in command_lower for tool in ['nikto', 'wpscan', 'whatweb']):
        return "reconnaissance:web_scan"
    elif any(tool in command_lower for tool in ['sqlmap']):
        return "exploitation:sql_injection"
    elif any(tool in command_lower for tool in ['metasploit', 'msfconsole', 'msfvenom']):
        return "exploitation:metasploit"
    elif any(tool in command_lower for tool in ['hydra', 'medusa', 'john', 'hashcat']):
        return "exploitation:password_attack"
    elif any(tool in command_lower for tool in ['curl', 'wget']):
        return "reconnaissance:web_request"
    elif any(tool in command_lower for tool in ['nc', 'netcat', 'ncat']):
        return "post_exploitation:network"
    elif any(tool in command_lower for tool in ['ssh', 'scp', 'sftp']):
        return "access:ssh"
    else:
        return "general"
