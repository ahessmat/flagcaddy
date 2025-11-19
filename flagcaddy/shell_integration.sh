#!/bin/bash
# FlagCaddy Shell Integration
# Source this file to enable command+output capture for FlagCaddy
#
# Add to your ~/.bashrc or ~/.zshrc:
#   source /path/to/flagcaddy/shell_integration.sh

# Configuration
FLAGCADDY_LOG="${FLAGCADDY_LOG:-$HOME/.flagcaddy/commands.jsonl}"

# Ensure directory exists
mkdir -p "$(dirname "$FLAGCADDY_LOG")"

# Main capture function - runs a command and logs it with output
# Usage: fc nmap -sV 10.10.10.5
fc() {
    if [ $# -eq 0 ]; then
        echo "Usage: fc <command> [args...]"
        echo "Example: fc nmap -sV 10.10.10.5"
        return 1
    fi

    local cmd="$*"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S")
    local pwd="$PWD"
    local output_file=$(mktemp)
    local cmd_file=$(mktemp)
    local session_id="${FLAGCADDY_SESSION:-default}"

    # Save command to file for safe Python reading
    echo -n "$cmd" > "$cmd_file"

    # Run command and capture output (both stdout and stderr)
    echo "[FlagCaddy] Capturing: $cmd"
    eval "$cmd" 2>&1 | tee "$output_file"
    local exit_code=${PIPESTATUS[0]:-0}

    # Use Python to create properly escaped JSON entry
    # Write to temp file first, then atomically append to log
    # This handles all special characters, newlines, quotes, ANSI codes, etc.
    local json_file=$(mktemp)

    python3 - "$cmd_file" "$output_file" "$timestamp" "$pwd" "${exit_code}" "$session_id" "$json_file" << 'PYSCRIPT'
import json
import sys

# Read arguments
cmd_file = sys.argv[1]
output_file = sys.argv[2]
timestamp = sys.argv[3]
working_dir = sys.argv[4]
exit_code = int(sys.argv[5])
session_id = sys.argv[6]
json_output_file = sys.argv[7]

# Read files
with open(cmd_file, 'r') as f:
    cmd = f.read()

with open(output_file, 'r') as f:
    output = f.read()

# Create JSON object
data = {
    'timestamp': timestamp,
    'command': cmd,
    'working_dir': working_dir,
    'output': output,
    'exit_code': exit_code,
    'session_id': session_id
}

# Write JSON to temp file
with open(json_output_file, 'w') as f:
    f.write(json.dumps(data, ensure_ascii=False))
    f.write('\n')
PYSCRIPT

    # Atomically append JSON line to log
    cat "$json_file" >> "$FLAGCADDY_LOG"

    # Cleanup temp files
    rm -f "$output_file" "$cmd_file" "$json_file"

    return $exit_code
}

# Alias for common pentest tools to auto-capture
# Users can enable this for automatic capture of specific tools
flagcaddy_auto_capture() {
    alias nmap='fc nmap'
    alias gobuster='fc gobuster'
    alias nikto='fc nikto'
    alias sqlmap='fc sqlmap'
    alias dirb='fc dirb'
    alias ffuf='fc ffuf'
    alias wpscan='fc wpscan'
    alias enum4linux='fc enum4linux'
    alias smbclient='fc smbclient'
    alias hydra='fc hydra'
    alias john='fc john'
    alias hashcat='fc hashcat'
    alias curl='fc curl'
    alias wget='fc wget'

    echo "[FlagCaddy] Auto-capture enabled for common pentest tools"
    echo "[FlagCaddy] Use 'command <tool>' to run without capture"
}

# Function to manually append output to last command
# Usage: some_command | fca
fca() {
    local output_file=$(mktemp)

    # Read stdin and display it
    tee "$output_file"

    # Log to FlagCaddy using Python for proper JSON encoding
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S")
    local pwd="$PWD"
    local session_id="${FLAGCADDY_SESSION:-default}"
    local json_file=$(mktemp)

    python3 - "$output_file" "$timestamp" "$pwd" "$session_id" "$json_file" << 'PYSCRIPT'
import json
import sys

output_file = sys.argv[1]
timestamp = sys.argv[2]
working_dir = sys.argv[3]
session_id = sys.argv[4]
json_output_file = sys.argv[5]

with open(output_file, 'r') as f:
    output = f.read()

data = {
    'timestamp': timestamp,
    'command': '<manual_append>',
    'working_dir': working_dir,
    'output': output,
    'exit_code': 0,
    'session_id': session_id
}

with open(json_output_file, 'w') as f:
    f.write(json.dumps(data, ensure_ascii=False))
    f.write('\n')
PYSCRIPT

    # Atomically append JSON line to log
    cat "$json_file" >> "$FLAGCADDY_LOG"

    rm -f "$output_file" "$json_file"
}

# Set session ID based on terminal
if [ -z "$FLAGCADDY_SESSION" ]; then
    export FLAGCADDY_SESSION="session_$(date +%Y%m%d_%H%M%S)_$$"
fi

echo "[FlagCaddy] Shell integration loaded"
echo "[FlagCaddy] Commands logged to: $FLAGCADDY_LOG"
echo ""
echo "Usage:"
echo "  fc <command>          - Run and capture command with output"
echo "  flagcaddy_auto_capture - Auto-capture common pentest tools"
echo ""
echo "Examples:"
echo "  fc nmap -sV 10.10.10.5"
echo "  fc gobuster dir -u http://target.com -w wordlist.txt"
echo ""

# Export functions
export -f fc 2>/dev/null || true
export -f fca 2>/dev/null || true
export -f flagcaddy_auto_capture 2>/dev/null || true
