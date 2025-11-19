# FlagCaddy

**AI-Powered Background Coach for Pentesters and CTF Competitors**

FlagCaddy is a passive monitoring tool that watches your terminal activity during penetration testing and CTF competitions, automatically cataloging your work and providing AI-powered recommendations for next steps.

## Features

- **Passive Terminal Monitoring**: Captures commands, working directories, and results without interfering with your workflow
- **Intelligent Entity Extraction**: Automatically identifies and organizes:
  - Hosts (IPs and domains)
  - Open ports and services
  - Network ranges
  - Discovered vulnerabilities
  - Web paths and endpoints
- **AI-Powered Analysis**: Uses LLM (via `codex exec`) to:
  - Summarize your progress
  - Identify gaps in reconnaissance
  - Suggest specific next steps
  - Prioritize targets
- **Live Web Dashboard**: Real-time UI showing:
  - Overall recommendations
  - Organized notes by host/network/service
  - Granular recommendations for each discovered entity
  - Recent command history
- **Smart Organization**: Automatically categorizes work by entity type with context-aware recommendations

## Installation

```bash
# Clone or navigate to the flagcaddy directory
cd /home/kali/flagcaddy

# Install in development mode
pip install -e .
```

## Quick Start

### 1. Start FlagCaddy

```bash
source venv/bin/activate  # Activate virtual environment
flagcaddy start
```

This will:
- Start monitoring for captured commands
- Begin analyzing your activity with AI
- Launch the web UI accessible at http://YOUR_IP:5000 (binds to 0.0.0.0)

### 2. Enable Shell Integration (in a new terminal)

To capture command output, source the shell integration:

```bash
source /home/kali/flagcaddy/flagcaddy/shell_integration.sh
```

**Optional**: Enable auto-capture for common pentest tools:
```bash
flagcaddy_auto_capture
```

### 3. Run Commands with the `fc` Wrapper

Use `fc` (FlagCaddy) to run and capture commands with their output:

```bash
fc nmap -sV 10.10.10.5
fc gobuster dir -u http://target.com -w /usr/share/wordlists/dirb/common.txt
fc sqlmap -u "http://target.com/page?id=1" --batch
```

Or if you enabled auto-capture, just run commands normally:
```bash
nmap -sV 10.10.10.5  # Automatically captured
```

**See [SHELL_INTEGRATION.md](SHELL_INTEGRATION.md) for detailed usage**

### 4. View Recommendations

Open the web UI in your browser (http://localhost:5000 locally, or http://YOUR_IP:5000 from another machine) to see:
- Overall strategy recommendations based on all activity
- Discovered targets with specific next steps for each
- Recent command history with output

**Note**: The AI analysis only runs when there are new commands to analyze, saving your LLM quota.

## CLI Commands

```bash
# Start the background monitor and web UI
flagcaddy start

# Start with custom intervals
flagcaddy start --capture-interval 5 --analysis-interval 60

# Start without web UI (monitoring only)
flagcaddy start --no-web

# View current status and statistics
flagcaddy status

# List discovered entities
flagcaddy entities
flagcaddy entities --type host
flagcaddy entities --type port

# List recent commands
flagcaddy commands --limit 50

# Run analysis once (useful for testing)
flagcaddy analyze

# Start only the web UI (if monitoring is already running)
flagcaddy web

# Show configuration
flagcaddy info

# Clean up false positive entities (files, git config, etc.)
flagcaddy cleanup

# Reset all data
flagcaddy reset
```

## Configuration

FlagCaddy uses environment variables for configuration:

```bash
# Custom codex exec path
export FLAGCADDY_CODEX_EXEC="codex"

# Web UI configuration
export FLAGCADDY_HOST="0.0.0.0"  # Default: binds to all interfaces (network accessible)
export FLAGCADDY_PORT="5000"

# Analysis interval (seconds)
export FLAGCADDY_ANALYSIS_INTERVAL="30"
```

### Network Access

By default, FlagCaddy binds to `0.0.0.0:5000`, making the web UI accessible from other machines on your network. This is useful for:
- Viewing the dashboard from your laptop while running commands on a remote server
- Team collaboration during CTF competitions
- Accessing from mobile devices on the same network

**Security Considerations:**
- The web UI contains sensitive pentesting data (commands, discovered hosts, vulnerabilities)
- No authentication is implemented by default
- **Only run on trusted networks** (VPN, isolated lab environment, localhost)
- To restrict to localhost only: `export FLAGCADDY_HOST="127.0.0.1"`
- Consider using SSH tunneling for remote access: `ssh -L 5000:localhost:5000 user@remote-host`

Access the UI:
- **Locally**: http://localhost:5000
- **From network**: http://YOUR_IP_ADDRESS:5000
- Find your IP: `ip addr show` or `hostname -I`

## How It Works

### 1. Command Capture (Shell Integration)

You run commands using the `fc` wrapper (or enable auto-capture). This captures:
- Command text
- Working directory
- **Full command output** (stdout + stderr)
- Exit code
- Timestamp

Commands are logged to `~/.flagcaddy/commands.jsonl` in JSONL format.

### 2. Entity Extraction

As commands are captured, FlagCaddy automatically extracts relevant entities from command output:
- **Hosts**: IP addresses and domain names
- **Ports**: Discovered open ports with services
- **Networks**: CIDR ranges
- **Services**: Identified services with versions
- **Vulnerabilities**: Potential security issues
- **Web Paths**: Discovered URLs and endpoints

### 3. AI Analysis (with Change Detection)

Periodically (default: every 30 seconds), FlagCaddy checks for changes:

**Change Detection**:
- Only runs LLM analysis when new commands have been captured
- Tracks which entities have new activity
- Saves LLM quota by skipping unnecessary analysis

**Global Analysis**: When changes detected, analyzes all recent activity:
- Summary of what's been done
- Overall strategy recommendations
- Identified gaps in reconnaissance

**Entity Analysis**: For entities with new activity:
- Analyzes all related commands and output
- Provides focused next steps
- Assigns priority level

### 4. Web Dashboard

The live web UI shows:
- **Overall Recommendations**: Top-level strategy based on all activity
- **Discovered Targets**: Organized by type (hosts, ports, services, etc.)
- **Entity-Specific Recommendations**: Granular next steps for each target
- **Recent Commands**: Your command history with output

Updates happen automatically every 5-10 seconds via WebSockets.

## Tool Support

FlagCaddy has built-in support for extracting data from:
- nmap (port scans, service detection, OS detection)
- gobuster (directory enumeration)
- nikto (web scanning)
- sqlmap (SQL injection testing)
- And more...

It also uses generic pattern matching to catch IPs, domains, ports, and networks from any tool's output.

## Use Cases

### Penetration Testing
- Keep track of multiple targets across different networks
- Get reminded about ports you haven't fully explored
- See suggestions for privilege escalation or lateral movement

### CTF Competitions
- Organize flags, credentials, and findings
- Get hints about unexplored attack vectors
- Track progress across multiple challenges

### Bug Bounty Hunting
- Manage discoveries across multiple subdomains
- Get recommendations for related endpoints
- Track tested and untested attack surfaces

## Architecture

```
flagcaddy/
├── __init__.py        # Package initialization
├── cli.py            # Command-line interface
├── config.py         # Configuration management
├── db.py             # SQLite database layer
├── capture.py        # Terminal monitoring
├── rules.py          # Entity extraction logic
├── llm.py            # LLM integration via codex exec
├── analysis.py       # Analysis coordination
├── engine.py         # Main orchestration engine
├── web.py            # Flask web server
└── templates/
    └── index.html    # Web dashboard UI
```

## Data Storage

All data is stored in `~/.flagcaddy/`:
- `flagcaddy.db`: SQLite database with commands, entities, and analysis
- `terminal_capture.log`: Optional full terminal capture log

## Privacy & Security

- All data is stored locally in your home directory
- No data is sent to external services except to your configured LLM via `codex exec`
- Commands and output may contain sensitive information, so keep your `~/.flagcaddy/` directory secure

## Requirements

- Python 3.9+
- `codex` CLI tool (for LLM analysis)
- Flask, Flask-SocketIO (installed automatically)

## Troubleshooting

### "codex exec not found"
Make sure the `codex` CLI is installed and in your PATH, or set `FLAGCADDY_CODEX_EXEC` to the correct path.

### No commands being captured
FlagCaddy monitors shell history files. Make sure you're using bash or zsh, and that history is being saved (check `HISTFILE` environment variable).

### Web UI not loading
Check that port 5000 is not in use by another application, or specify a different port with `--port`.

## Contributing

This is a tool for authorized security testing and CTF competitions only. Use responsibly and only on systems you have permission to test.

## License

MIT
