# FlagCaddy Usage Guide

## Installation

Since this is a Kali Linux system with an externally-managed Python environment, install using a virtual environment:

```bash
cd /home/kali/flagcaddy

# Create virtual environment (if not already created)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install FlagCaddy
pip install -e .
```

## Quick Start

### 1. Activate the virtual environment

```bash
source /home/kali/flagcaddy/venv/bin/activate
```

### 2. Start FlagCaddy

```bash
flagcaddy start
```

This starts:
- Terminal monitoring (checking your shell history every 2 seconds)
- AI analysis engine (analyzing every 30 seconds)
- Web UI accessible at http://YOUR_IP:5000 (binds to 0.0.0.0 for network access)

### 3. Work Normally

Open a new terminal tab/window and do your pentesting/CTF work as usual:

```bash
# Example reconnaissance workflow
nmap -sV -p- 10.10.10.5
gobuster dir -u http://10.10.10.5 -w /usr/share/wordlists/dirb/common.txt
nikto -h http://10.10.10.5

# Check for SQL injection
sqlmap -u "http://10.10.10.5/page?id=1" --batch

# SSH enumeration
ssh-audit 10.10.10.5
```

### 4. View Dashboard

Open the web UI in your browser to see:
- AI-generated overall recommendations
- Discovered hosts, ports, and services
- Specific next steps for each target
- Your command history

**Access URLs:**
- From the same machine: http://localhost:5000
- From another device on the network: http://YOUR_IP:5000
- Find your IP: `hostname -I | awk '{print $1}'` or `ip addr show`

## Example Session

```bash
# Terminal 1: Start FlagCaddy
source venv/bin/activate
flagcaddy start

# Terminal 2: Your pentesting work
nmap -sV 192.168.1.0/24
# FlagCaddy detects: network range, hosts, open ports

gobuster dir -u http://192.168.1.10 -w /usr/share/wordlists/dirb/common.txt
# FlagCaddy detects: web host, discovered paths

# Check the dashboard - you'll see:
# - "Overall: Continue web enumeration on 192.168.1.10"
# - "Host 192.168.1.10: Try exploiting /admin directory"
# - "Port 80/tcp: Check for common web vulnerabilities"
```

## Advanced Usage

### Custom Analysis Intervals

```bash
# Capture every 5 seconds, analyze every 60 seconds
flagcaddy start --capture-interval 5 --analysis-interval 60
```

### Run Without Web UI

```bash
# If you prefer to check status via CLI
flagcaddy start --no-web

# Then use CLI commands
flagcaddy status
flagcaddy entities
flagcaddy commands
```

### One-Time Analysis

```bash
# Run analysis once on existing data
flagcaddy analyze
```

### Custom Web UI Port

```bash
# If port 5000 is already in use
flagcaddy start --port 8080
```

Or set environment variable:
```bash
export FLAGCADDY_PORT=8080
flagcaddy start
```

### Network Access

By default, FlagCaddy binds to `0.0.0.0`, making the web UI accessible from other machines on your network.

**Use Cases:**
- Access the dashboard from your laptop while running commands on a remote pentest box
- Share the dashboard with your team during a CTF competition
- View from a tablet/phone on the same network

**Security Warning:**
- The web UI contains sensitive data (commands, targets, vulnerabilities)
- No authentication is implemented
- **Only run on trusted networks** (VPN, isolated lab, CTF network)

**Restrict to localhost only:**
```bash
export FLAGCADDY_HOST="127.0.0.1"
flagcaddy start
```

**Access via SSH tunnel (secure remote access):**
```bash
# On your local machine
ssh -L 5000:localhost:5000 user@remote-host

# In another terminal on the remote host
flagcaddy start --host 127.0.0.1

# Access on local machine: http://localhost:5000
```

**Find your IP address:**
```bash
hostname -I | awk '{print $1}'  # First IP
ip addr show                     # All interfaces
```

## Understanding the Output

### Entity Types

- **host**: IP addresses and domain names discovered
- **port**: Open ports with service information
- **network**: Network ranges (CIDR notation)
- **service**: Identified services with versions
- **vulnerability**: Potential security issues found
- **web_path**: Discovered web directories/files
- **os**: Operating system detection results

### Priority Levels

Entities are color-coded by priority:
- **Red**: High priority (likely vulnerable or unexplored)
- **Orange**: Medium priority (needs investigation)
- **Green**: Low priority (already explored or low value)

### Recommendations

You'll see two types of recommendations:

1. **Global Recommendations** (top of dashboard)
   - Overall strategy
   - What to focus on next
   - Gaps in your reconnaissance

2. **Entity-Specific Recommendations** (under each target)
   - Specific actions for that host/service
   - Follow-up commands to run
   - Potential attack vectors

## Tips for Best Results

### 1. Use Descriptive Commands

The AI works better when your commands have clear output:

```bash
# Good: Full output
nmap -sV -p- 10.10.10.5 -oN scan.txt

# Less helpful: Quiet mode
nmap -sV -p- 10.10.10.5 -oX - >/dev/null
```

### 2. Let Analysis Run

Give the AI time to analyze (default 30 seconds). You'll see better recommendations after a few analysis cycles.

### 3. Check Entity-Specific Recommendations

Don't just look at global recommendations. Click through your discovered hosts/services to see focused next steps.

### 4. Use Standard Tools

FlagCaddy has built-in support for:
- nmap, masscan, rustscan
- gobuster, dirb, ffuf
- nikto, wpscan
- sqlmap
- hydra, john, hashcat

But it can extract entities from any tool's output.

## Troubleshooting

### "No commands being captured"

FlagCaddy monitors your shell history. Make sure:
- You're using bash or zsh
- History is being saved (check `echo $HISTFILE`)
- You're running commands in a different terminal than FlagCaddy

### "codex exec not found"

Make sure `codex` is installed and in your PATH:
```bash
which codex
```

Or set the path explicitly:
```bash
export FLAGCADDY_CODEX_EXEC=/path/to/codex
```

### "No recommendations appearing"

- Check that analysis is running (`flagcaddy status`)
- Verify codex is working: `codex exec "Hello"`
- Check logs for errors in the FlagCaddy terminal

### "Web UI not loading"

- Check port 5000 isn't in use: `lsof -i :5000`
- Try a different port: `flagcaddy start --port 8080`
- Check browser console for errors

## Data Management

### View Current Data

```bash
flagcaddy status          # Summary
flagcaddy entities        # All discovered entities
flagcaddy commands        # Recent commands
```

### Reset Everything

```bash
flagcaddy reset
# Deletes ~/.flagcaddy/flagcaddy.db
```

### Backup Your Session

```bash
cp ~/.flagcaddy/flagcaddy.db ~/flagcaddy-backup-$(date +%Y%m%d).db
```

## Integration with Existing Workflow

### For Pentesting Engagements

1. Start FlagCaddy at the beginning of your engagement
2. Work through your normal methodology
3. Use the dashboard to track progress and ensure nothing is missed
4. Export findings from the database for your report

### For CTF Competitions

1. Start FlagCaddy when the CTF begins
2. Work on challenges as normal
3. Check recommendations when stuck
4. Use entity view to track which challenges/hosts you've explored

### For Bug Bounty

1. Start FlagCaddy for each target program
2. Track subdomains, endpoints, and vulnerabilities
3. Use recommendations to prioritize testing
4. Reset data between programs

## Security Notes

- All data stored in `~/.flagcaddy/` may contain sensitive information
- Commands and output may include credentials, API keys, etc.
- Keep the `.flagcaddy` directory secure
- Consider encrypting the directory on shared systems
- Only the LLM analysis via `codex exec` sends data externally

## Performance

FlagCaddy is designed to be lightweight:
- Minimal CPU usage (periodic polling)
- SQLite database is fast and efficient
- Web UI uses WebSockets for real-time updates
- Analysis runs in background thread

Typical resource usage:
- Memory: ~50-100 MB
- CPU: <1% (except during LLM analysis)
- Disk: <10 MB (grows with command history)
