# FlagCaddy Coaching Workflow

This repository bundles an example workflow that mirrors the idea you described: capture each CLI action with `script`, translate those actions into a verbose `notes.md`, then surface prioritized next steps inside a lightweight web UI.

## Components

- **Command capture** – Run `script -af /home/kali/ctf.log` (or add it to your shell profile) whenever you kick off an engagement. The `-a` flag appends, `-f` flushes output so the watcher can pick it up in near real-time.
- **Log → Notes pipeline** – `scripts/log_to_notes.py` polls `/home/kali/ctf.log`, parses command blocks, updates a JSON state file, and re-renders `notes.md` with host/service inventory plus a detailed timeline.
- **Notes → Next Steps pipeline** – `scripts/notes_to_actions.py` reads the JSON state, emits `data/next_steps.json`, and uses a small heuristic library to convert host/service data into tangible action items.
- **Web UI** – `web/app.py` is a tiny Flask application that displays the prioritized queue along with suggested commands.

```
/home/kali/ctf.log -> log_to_notes.py -> data/ctf_state.json + notes.md -> notes_to_actions.py -> data/next_steps.json -> Flask web UI
```

## Quick Start

1. **Install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Capture your terminal**
   ```bash
   script -af /home/kali/ctf.log
   ```

3. **Generate notes + next steps once**
   ```bash
   python scripts/log_to_notes.py
   python scripts/notes_to_actions.py
   ```

4. **Run everything continuously** (three terminals/tmux panes work well):
   ```bash
   python scripts/log_to_notes.py --loop --interval 15
   python scripts/notes_to_actions.py --loop --interval 30
   FLASK_APP=web/app.py flask run --host 0.0.0.0 --port 5000
   ```

5. **Browse the dashboard** at `http://0.0.0.0:5000` to review action items.

### Helper script

Use `scripts/manage_workflow.sh` to start/stop all three services together:

```bash
./scripts/manage_workflow.sh start   # start log watcher, action generator, Flask UI
./scripts/manage_workflow.sh status  # show running PIDs
./scripts/manage_workflow.sh stop    # terminate everything
```

The script writes PID files under `data/pids/` and logs to `logs/*.log`. Override the interpreters with `PYTHON_BIN=/path/to/python FLASK_BIN=/path/to/flask ./scripts/manage_workflow.sh start` if needed.

## Systemd user services (optional)

Drop the following units in `~/.config/systemd/user/` to keep the workflow running in the background:

`ctf-notes.service`
```
[Unit]
Description=Watch ctf.log and refresh notes
After=default.target

[Service]
Type=simple
WorkingDirectory=%h/flagcaddy
ExecStart=%h/flagcaddy/.venv/bin/python scripts/log_to_notes.py --loop --interval 15
Restart=always

[Install]
WantedBy=default.target
```

`ctf-next-steps.service`
```
[Unit]
Description=Generate prioritized next steps from notes
After=ctf-notes.service

[Service]
Type=simple
WorkingDirectory=%h/flagcaddy
ExecStart=%h/flagcaddy/.venv/bin/python scripts/notes_to_actions.py --loop --interval 30
Restart=always

[Install]
WantedBy=default.target
```

`ctf-web.service`
```
[Unit]
Description=Expose the coaching web UI
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/flagcaddy
Environment="FLASK_APP=web/app.py"
ExecStart=%h/flagcaddy/.venv/bin/flask run --host 0.0.0.0 --port 5000
Restart=always

[Install]
WantedBy=default.target
```

Enable/start:
```bash
systemctl --user daemon-reload
systemctl --user enable --now ctf-notes.service ctf-next-steps.service ctf-web.service
```

## Customizing The Notes

- Update the `"engagement"` block inside `data/ctf_state.json` to set the name, scope, and objectives. The next-step generator prioritizes filling these out.
- The parser currently captures `nmap`, `ssh`, `gobuster`, `feroxbuster`, and `enum4linux`. Extend `summarize_command` in `scripts/log_to_notes.py` to add richer handling for other tooling.
- Host/service data lives in `data/ctf_state.json`. You can safely edit the `hosts` structure (e.g., to insert credentials) and the renderer will fold that into `notes.md` on the next run.

## Testing With Sample Data

Add a mock log snippet into `/home/kali/ctf.log` (or symlink/test path) such as:
```
kali@kali:~$ nmap -sCV 10.10.11.5
Nmap scan report for 10.10.11.5
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 8.9p1 Ubuntu 3ubuntu0.3
80/tcp   open  http    Apache httpd 2.4.52
```
Then rerun `python scripts/log_to_notes.py && python scripts/notes_to_actions.py`. The notes file will list host `10.10.11.5` with services, and the dashboard will recommend HTTP/SSH follow-up actions.

## Next Ideas

- Wire in the official Codex CLI so the parsing/summary steps leverage the model instead of heuristics.
- Store state inside SQLite for better concurrency.
- Preserve raw command/output pairs in `data/archive/` for deeper historical analysis.
- Extend `notes_to_actions.py` with vulnerability-specific playbooks (e.g., SMB signing disabled → `ntlmrelayx`).
