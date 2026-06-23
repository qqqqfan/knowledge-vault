# knowledge-vault — OpenClaw Version

## How It Works

```
Daily at 18:00 (cloud, always on)
  → Scan today's conversations
  → Extract P0–P3 knowledge
  → Cache to cloud storage
  → Send you a brief notification (if IM is connected)

When you say "sync my knowledge vault"
  → Agent reads cache
  → Writes structured notes to your local Obsidian via desktop bridge
  → Creates folders as needed (asks first)
  → Generates changelog for review
```

## Requirements

- OpenClaw / Seal with a desktop node connected (the companion app running on your Mac or Windows machine)
- Obsidian installed locally — [obsidian.md](https://obsidian.md), no account needed

## Installation

**Step 1 — Install Obsidian**

Download from [obsidian.md](https://obsidian.md). No account required. Open it and create a new Vault (just a local folder).

Recommended starting structure — create these 4 folders inside your Vault:
```
Knowledge/    Frameworks/    Projects/    Inbox/
```

**Step 2 — Tell the agent your Vault path**

Say to your agent:
> "My Obsidian Vault is at /Users/yourname/Documents/MyVault"

The agent saves this to your `vault-profile.json`.

**Step 3 — First sync and permission grant**

Say: "sync my knowledge vault"

On Mac, a permissions dialog will appear asking for file system access. Click **Allow**. This only happens once.

**Done.** Collection runs daily at 18:00. Sync whenever you want.

## Daily Usage

| Say this | What happens |
|----------|-------------|
| `sync my knowledge vault` | Push cached notes to Obsidian, and read back any notes you deleted as feedback (never restored + self-calibration) |
| `reorganize my vault` | Tidy up existing notes and folders |
| `I remember we talked about X` | Find and save missing content from history |
| `remember this` | Force-save current content (P0) |
| `change vault collection time to 10pm` | Update cron schedule |
| `only collect on weekdays` | Update cron frequency |
| `turn off notifications` | Disable IM notification after each run |

## Adjustable Settings

All settings changed by talking to the agent — no config files to edit manually.

| Setting | Default | How to change |
|---------|---------|---------------|
| Collection time | 18:00 | "change vault collection time to X" |
| Frequency | Daily | "only on weekdays" / "twice a day" |
| Notifications | On | "turn off notifications" |
| Cache duration | 7 days | "keep cache for 14 days" |

## Privacy

- Knowledge extraction happens on the same server your agent conversations already use
- Final notes are written to your local machine — nothing is sent to any external cloud
- Content involving personal evaluations, compensation, or undisclosed business info is never recorded
- Notes you delete from Obsidian are never restored

## Troubleshooting

**"No desktop node found"**
Make sure the OpenClaw companion app is running on your machine and shows as connected.

**Permission dialog didn't appear / was dismissed**
Go to System Settings → Privacy & Security → Files and Folders, find the OpenClaw app, and enable access manually.

**Notes aren't appearing after sync**
Check that your Vault path is correct. Say: "what's my vault path?" to verify.

**Something was saved that shouldn't have been**
Delete it from Obsidian. The agent will notice on the next sync, won't restore it, and will self-calibrate.
