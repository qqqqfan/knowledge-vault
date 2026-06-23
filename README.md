# knowledge-vault

> Let every deep conversation with AI leave a trace.

## The Problem

You spend an hour with an AI agent, work through a hard problem, reach a real insight. Then you close the window.

Three months later you need that insight again. You scroll through chat history. And scroll. And scroll.

The knowledge happened. It just didn't stick.

## What This Is

**knowledge-vault** automatically extracts knowledge worth keeping from your AI conversations and stores it in your local Obsidian vault — structured, linked, and yours forever.

You keep talking to your AI agent normally. It quietly builds your knowledge base in the background.

## Why Obsidian?

- **Fully local** — plain Markdown files on your own disk. No account, no subscription, no vendor lock-in.
- **Graph view** — bidirectional links let you see how your knowledge connects and grows over time.
- **Your data, your rules** — nothing leaves your machine without your explicit action.

## Two Versions

| | OpenClaw | Claude Code |
|---|---|---|
| **Conversation source** | OpenClaw session history | `~/.claude/projects/` JSONL files |
| **Scheduling** | Cloud cron (always on) | System crontab (local) |
| **File writing** | Desktop node bridge | Direct Python file I/O |
| **Notifications** | IM (if configured) | macOS system notification |
| **Sync trigger** | "sync my knowledge vault" | `python vault_agent.py sync` |

→ [OpenClaw version](./openclaw/README.md)
→ [Claude Code version](./claude-code/README.md)

## Core Design Principles

**1. You set the standard for what's worth keeping.**

The agent judges content by priority:
- P0: You explicitly say "remember this"
- P1: High-density professional concepts being explained
- P2: Design decisions and reasoning processes
- P3: Reusable SOPs and guides buried in task conversations
- ❌ Skip: Small talk, one-off lookups, sensitive personal/business info

**2. Deletion is feedback.**

If you delete a note from Obsidian, the agent notices on the next sync. Sync is two-way: it pushes new notes into the vault *and* reads your deletions back out. It won't restore a deleted note, and it reflects on whether its scoring of that kind of content was too generous, self-calibrating over time. Both versions apply this rule at sync time.

**3. The agent adapts to your vault style.**

On first run, it scans your existing vault structure and infers your preferences: folder depth, note length, link density. It writes new notes to match your style, not a template.

**4. Transparent, not magic.**

Every sync generates a changelog. You always know what was added, what was skipped, and why.

## Recommended Vault Structure

```
YourVault/
├── Knowledge/              ← What you learned (concepts, principles)
│   ├── [Domain]/
│   └── Terminology/
├── Frameworks/             ← Mental models you've internalized
├── Projects/               ← What you built (decisions, lessons)
├── Work/                   ← Domain-specific SOPs and processes
└── Inbox/                  ← Buffer for unclassified new notes
```

Start with just these 4 folders. Let structure grow from content, not the other way around.

## License

MIT
