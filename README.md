# Flagcaddy

Flagcaddy is a terminal-aware assistant that records the commands you run
during CTFs or pentests and keeps a running list of the next steps you should
try. It can:

- wrap any shell or tool in a PTY and capture both stdin and stdout streams,
- deduplicate noisy commands and score each event for novelty,
- store extracted facts (hosts, services, interesting strings) in SQLite,
- fire quick rule-based recommendations immediately, and
- optionally batch recent events into a `codex exec` prompt for LLM-backed
  guidance without burning tokens on every keystroke.

> The project name is a nod to golf caddies: keep working in your usual shell
> while Flagcaddy quietly tracks progress and whispers suggestions.

---

## Installation

Flagcaddy targets Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

The CLI entrypoint is `flagcaddy`.

---

## Quick start

Wrap the shell you plan to use for an engagement:

```bash
flagcaddy wrap hackthebox -- /bin/zsh
```

- `hackthebox` becomes the session identifier (recommendations are grouped per
  session).
- Everything you type passes through your usual shell; Flagcaddy simply records
  command + output pairs on the side.
- The prompt is temporarily prefixed with `[flagcaddy]` so the recorder can
  detect command boundaries.

After you exit the wrapped shell:

```bash
flagcaddy sessions           # list known sessions
flagcaddy events hackthebox  # show the most recent captured commands
flagcaddy recommendations hackthebox  # show rule/LLM suggestions
```

Each event stores:

- canonical command text,
- raw output (post-PTY capture),
- novelty score (how unique/valuable Flagcaddy thinks the event is),
- dedup flag (if we have already seen the same command/output fingerprint),
- timestamp metadata.

---

## Architecture overview

1. **Capture (PTY wrapper)** – `flagcaddy wrap` launches a child command inside
   a pseudoterminal. Stdin and stdout are mirrored back to your terminal while
   a recorder tracks keystrokes, command boundaries, and prompt appearances.
2. **Event store** – every command + output pair is normalized, hashed, and
   inserted into `~/.flagcaddy/state.db` (SQLite). Canonicalized fingerprints
   prevent re-processing duplicate events.
3. **Fact extraction** – simple regex-based parsers save hosts, services,
   credentials, and `tool` markers in a fact table. New facts bump the novelty
   score for current events.
4. **Recommendation engine** – rule packs (`flagcaddy.rules.DEFAULT_RULES`)
   fire instantly (HTTP enumeration, SMB follow-ups, shell stabilization, etc.).
   Events whose novelty exceeds a threshold enter the LLM dispatcher queue.
5. **LLM dispatcher** – optionally shells out to `codex exec`, batching the most
   recent high-signal events into a single prompt. Cooldown timers and novelty
   thresholds ensure only meaningful changes trigger token usage.

---

## Configuring LLM dispatches

Flagcaddy writes `~/.flagcaddy/config.toml` on first run. Edit the `[llm]`
section to wire up the `codex exec` invocation you want:

```toml
[llm]
command = "codex exec --model gpt-4o-mini"
novelty_threshold = 1.5    # minimum novelty needed before batching events
cooldown_seconds = 120     # per-session delay between codex calls
batch_size = 5             # how many recent events to include
max_chars = 6000           # prompt truncation guardrail
```

Flagcaddy sends prompts via stdin; `codex exec` should print the model response
to stdout. If no `command` is configured (or the binary is missing), LLM
recommendations stay disabled and the CLI will show a reminder.

**Batching logic:** Whenever an event lands with `novelty >= novelty_threshold`
and the cooldown has elapsed since the last LLM call for that session, the
dispatcher concatenates up to `batch_size` recent events (`Command`, `Output`,
`Novelty`) up to `max_chars`, appends clear instructions, and feeds the prompt
to `codex exec`. The returned text is stored as a recommendation so you can
review it later with `flagcaddy recommendations <session>`.

---

## Deduplication & novelty scoring

Flagcaddy tries to keep the LLM budget focused on genuinely new information:

- **Fingerprints** – command text + canonicalized output (IPs masked, large
  numbers replaced, whitespace collapsed) hashed via SHA-1. If an event's
  fingerprint already exists in the session, it is marked as a duplicate and
  given a low novelty score.
- **Fact hits** – regex-based extraction saves hosts, `proto/port:service`
  strings, credentials, `flag{}` tokens, and tool families. Newly discovered
  facts add +0.6 each to the novelty score.
- **Signal keywords** – terms like `shell`, `password`, `flag{` add small bumps.
- **Decay guardrails** – novelty is clamped between 0.15 and 5.0.

This scoring feeds both rule prioritization and the LLM dispatcher.

---

## Rule-based recommendations

`flagcaddy.rules.DEFAULT_RULES` ships with a few evergreen heuristics:

| Rule             | Trigger                                    | Example suggestion |
| ---------------- | ------------------------------------------ | ------------------ |
| `http-enum`      | HTTP ports spotted in output               | Run feroxbuster, screenshot sites |
| `smb-enum`       | SMB services listed                        | Use `smbclient`, `enum4linux`, check signing |
| `ftp-enum`       | FTP banner / login hints                   | Try anonymous login, brute creds |
| `shell-checklist`| Reverse shells or `nc` usage in commands   | Stabilize shell, run linpeas/WinPEAS |

You can create new rules by adding to the `DEFAULT_RULES` list – each rule is a
callable that receives the `EventContext` (command, output, extracted facts,
novelty) and returns an optional `Recommendation`.

---

## Usage patterns

### Wrap a single tool

```bash
flagcaddy wrap bloodhound -- neo4j console
```

This is helpful when a single utility prints lots of context (e.g., `nmap`,
`linpeas`). Flagcaddy will record that tool's output, produce service facts, and
maybe call `codex exec` when new hosts/ports appear.

### Wrap a login shell

For everyday workflows, start a new shell per target:

```bash
flagcaddy wrap academy -- /bin/bash --noprofile --norc
```

Every command executed in that shell is recorded; when you're done the session
remains queryable even after closing the terminal.

### Viewing recommendations during an engagement

Run a second terminal with `watch`:

```bash
watch -n 20 'flagcaddy recommendations academy -n 5'
```

This gives you a near-live feed of advice without touching the wrapped shell.

---

## Development

The repository is intentionally simple:

- `flagcaddy/capture.py` handles PTY work and command segmentation.
- `flagcaddy/analysis.py` has canonicalization + fact extraction helpers.
- `flagcaddy/engine.py` ties events, rules, and LLM dispatches together.
- `flagcaddy/rules.py` defines rule-based heuristics.

Run linting and tests (add more as the project grows):

```bash
python -m compileall flagcaddy
```

---

## Roadmap ideas

- pluggable fact extractors for tool-specific JSON outputs (e.g., `nmap -oX`)
- optional REST API / TUI dashboard
- multi-user session syncing (e.g., team events)
- scheduler that replays historical transcripts into different rule packs

PRs and suggestions welcome!
