# knowledge-vault — Claude Code Version

## How It Works

```
System cron (runs locally on your machine)
  → Reads ~/.claude/projects/ conversation files
  → Calls Claude API to evaluate and extract knowledge
  → Writes structured Markdown notes directly to your Obsidian Vault

No cloud intermediary. No desktop bridge. Just Python + cron + Obsidian.
```

## Requirements

- Python 3.10+
- An Anthropic API key (`ANTHROPIC_API_KEY`)
- Obsidian installed — [obsidian.md](https://obsidian.md), no account needed
- Claude Code with conversation history saved locally

## Installation

**Step 1 — Clone and install dependencies**

```bash
git clone https://github.com/yourname/knowledge-vault
cd knowledge-vault/claude-code
pip install -r requirements.txt
```

**Step 2 — Configure**

```bash
cp vault-profile-template.json vault-profile.json
```

Edit `vault-profile.json`:

```json
{
  "vault_path": "/Users/yourname/Documents/MyVault",
  "claude_projects_path": "~/.claude/projects",
  "api_key_env": "ANTHROPIC_API_KEY",
  "model": "claude-opus-4-8",
  "cache_days": 7,
  "notify": true
}
```

**Step 3 — Test run**

```bash
export ANTHROPIC_API_KEY=your_key_here
python vault_agent.py sync --dry-run
```

This shows what would be written without actually writing anything.

**Step 4 — Set up cron**

Keep your API key out of the crontab itself — put it in a file only you can read:

```bash
echo 'export ANTHROPIC_API_KEY=your_key_here' > ~/.knowledge-vault.env
chmod 600 ~/.knowledge-vault.env
```

Then add a cron line that sources it (so the key never shows up in `crontab -l` or the process list):

```bash
# Open crontab editor
crontab -e

# Add this line (runs daily at 18:00)
0 18 * * * . ~/.knowledge-vault.env && cd /path/to/knowledge-vault/claude-code && python vault_agent.py collect >> ~/.knowledge-vault.log 2>&1
```

See `crontab.example` for more schedule options (weekdays only, twice daily, etc.)

**Done.**

## Usage

```bash
# Collect from today's conversations (also runs via cron)
python vault_agent.py collect

# Sync — reconcile local memory with Obsidian (both directions, see below)
python vault_agent.py sync

# Dry run — see what would be written without writing
python vault_agent.py sync --dry-run

# View recent changelog
python vault_agent.py history

# Roll back last sync
python vault_agent.py rollback
```

## Sync is two-way: deletion is feedback

`sync` reconciles your local memory (the `.cache` of extracted notes) with your Obsidian vault in **both** directions:

- **Forward** — new notes extracted from your conversations are written into the vault.
- **Reverse** — any note you previously synced but have since **deleted** from the vault is read back as a signal. It's recorded so it's never re-created, and the agent reflects on whether it scored that kind of content (priority + folder) too generously. After repeated deletions of a similar pattern, it tightens its bar on the next `collect`.

So the workflow is: `collect` (scheduled, extracts to local cache) → you review in Obsidian after `sync`, deleting whatever you don't want → next `sync` learns from those deletions. The collection stays driven by your Claude Code memory; the vault is where you curate, and curation flows back.

## Roadmap

The OpenClaw version (driven by an agent) supports a couple of capabilities the Claude Code Python CLI doesn't implement yet:

- **`reorganize`** — re-classify and move existing notes (plan mode + auto mode)
- **`find`** — pull missing content from a past session or topic into the vault

These are planned for the Python version. For now, use the OpenClaw version if you need them.

## How Conversation Files Are Read

Claude Code saves conversations to `~/.claude/projects/`. Each project is a directory containing JSONL files, one per conversation session.

`vault_agent.py` reads these files, parses the message history, filters to today's sessions, and sends the content to Claude for evaluation and extraction.

## Notifications (macOS)

When `notify: true` in your profile, a macOS system notification is sent after each collect run:

```
📚 knowledge-vault
2 notes extracted from today's conversations.
Run `python vault_agent.py sync` to push to Obsidian.
```

On Linux: notification via `notify-send` if available. On Windows: Windows Toast notification.

## Privacy

- All processing happens locally on your machine
- Your conversation content is sent to the Anthropic API for extraction (same as normal Claude Code usage)
- Nothing is stored on any third-party server beyond the API call
- Final notes are written to your local Obsidian Vault only

## Troubleshooting

**No conversations found**
Check that `claude_projects_path` in your profile points to the right directory. Default is `~/.claude/projects/`.

**API errors**
Make sure `ANTHROPIC_API_KEY` is set in your environment. For cron, add it explicitly: `ANTHROPIC_API_KEY=xxx python vault_agent.py collect`

**Notes not appearing in Obsidian**
Verify `vault_path` is correct and the directory exists. Run with `--dry-run` first to confirm output paths.
