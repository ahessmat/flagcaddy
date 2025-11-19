# FlagCaddy Shell Integration

To capture command output in FlagCaddy, you need to source the shell integration script.

## Quick Setup

### 1. Source the integration script

```bash
source /home/kali/flagcaddy/flagcaddy/shell_integration.sh
```

Or add to your `~/.bashrc` or `~/.zshrc` for automatic loading:

```bash
echo "source /home/kali/flagcaddy/flagcaddy/shell_integration.sh" >> ~/.bashrc
```

### 2. Use the `fc` wrapper

Prefix important commands with `fc` to capture them with their output:

```bash
fc nmap -sV 10.10.10.5
fc gobuster dir -u http://target.com -w /usr/share/wordlists/dirb/common.txt
fc nikto -h http://target.com
fc sqlmap -u "http://target.com/page?id=1" --batch
```

## Features

### Manual Capture (`fc` command)

The `fc` (FlagCaddy) wrapper runs a command and captures:
- Command text
- Working directory
- Full output (stdout + stderr)
- Exit code
- Timestamp

**Usage:**
```bash
fc <command> [args...]
```

**Examples:**
```bash
# Port scanning
fc nmap -sV -p- 192.168.1.10

# Web enumeration
fc gobuster dir -u http://target.com -w wordlist.txt

# Vulnerability scanning
fc nikto -h https://target.com

# Manual testing
fc curl -v http://target.com/api/endpoint
```

### Auto-Capture Mode

Enable automatic capture for common pentest tools:

```bash
flagcaddy_auto_capture
```

This creates aliases for common tools so they automatically use `fc`:
- nmap, gobuster, nikto, sqlmap
- dirb, ffuf, wpscan
- enum4linux, smbclient
- hydra, john, hashcat
- curl, wget

**After enabling auto-capture:**
```bash
# These are automatically captured
nmap -sV 10.10.10.5
gobuster dir -u http://target.com -w wordlist.txt

# To run WITHOUT capture, use 'command'
command nmap -sV 10.10.10.5
```

### Manual Output Append

If you ran a command without `fc`, you can pipe its output to `fca`:

```bash
cat /etc/passwd | fca
echo "Some finding" | fca
```

## How It Works

1. Commands are logged to `~/.flagcaddy/commands.jsonl` (JSONL format)
2. Each line is a JSON object with command + output
3. FlagCaddy monitors this file in real-time
4. As commands appear, entities are extracted and analyzed

## JSONL Format

Each captured command creates one line:

```json
{"timestamp":"2025-11-19T20:30:45","command":"nmap -sV 10.10.10.5","working_dir":"/home/kali","output":"Starting Nmap...","exit_code":0,"session_id":"session_20251119_203045_12345"}
```

## Tips

### For CTF Competitions

```bash
# Start your session
source /home/kali/flagcaddy/flagcaddy/shell_integration.sh

# Enable auto-capture
flagcaddy_auto_capture

# Work normally - all your recon tools are captured
nmap -sV 10.10.10.5
gobuster dir -u http://target.ctf -w /usr/share/wordlists/dirb/common.txt
```

### For Penetration Testing

```bash
# Capture only important commands manually
fc nmap -sV -A -oA scan1 192.168.1.0/24

# Regular commands aren't captured (optional)
ls -la
cd /tmp

# Capture the critical ones
fc curl -v http://192.168.1.10/admin
```

### For Bug Bounty

```bash
# Capture subdomain enumeration
fc subfinder -d target.com -o subdomains.txt

# Capture HTTP probing
fc httpx -l subdomains.txt -title -status-code

# Capture directory bruteforcing
fc ffuf -u https://FUZZ.target.com -w wordlist.txt
```

## Troubleshooting

### "fc: command not found"

Make sure you sourced the integration script:
```bash
source /home/kali/flagcaddy/flagcaddy/shell_integration.sh
```

### Output not being captured

- The `fc` command should display output to your terminal AND capture it
- Check that `~/.flagcaddy/commands.jsonl` is being written to
- Verify FlagCaddy is running and monitoring the file

### Commands logged but not analyzed

- Check that FlagCaddy is running: `flagcaddy status`
- Look for analysis errors in the FlagCaddy terminal output
- Verify `codex exec` is working: `codex exec "test"`

## Advanced Usage

### Custom Log File

```bash
export FLAGCADDY_LOG="/custom/path/commands.jsonl"
source /home/kali/flagcaddy/flagcaddy/shell_integration.sh
```

### Session IDs

Each terminal gets a unique session ID. This helps organize commands:
```bash
echo $FLAGCADDY_SESSION
# Output: session_20251119_203045_12345
```

Set a custom session name:
```bash
export FLAGCADDY_SESSION="htb_box_poison"
source /home/kali/flagcaddy/flagcaddy/shell_integration.sh
```

## Security Considerations

- The `commands.jsonl` file contains all your commands and their output
- This includes credentials, API keys, flags, etc.
- Keep `~/.flagcaddy/` directory secure (it's in your home directory)
- Consider encrypting the directory on shared systems
- Clear sensitive data: `flagcaddy reset`

## Without Shell Integration

If you can't or don't want to use shell integration:

1. FlagCaddy will still work, but won't capture command output
2. You can manually add output to the analysis by running commands and noting results
3. The AI analysis will be less effective without seeing actual output
4. Consider using `script` command for full terminal capture (though harder to parse)

## Examples in Practice

### Typical HTB/CTF Workflow

```bash
# Terminal 1: Start FlagCaddy
source venv/bin/activate
flagcaddy start

# Terminal 2: Load integration and work
source /home/kali/flagcaddy/flagcaddy/shell_integration.sh
flagcaddy_auto_capture

# Now work normally - check dashboard periodically
nmap -sV 10.10.10.5
# -> Dashboard shows: "Port 80 open, try web enumeration"

gobuster dir -u http://10.10.10.5 -w common.txt
# -> Dashboard shows: "Found /admin, investigate authentication"

curl -v http://10.10.10.5/admin
# -> Dashboard shows: "Try default credentials or SQL injection"
```
