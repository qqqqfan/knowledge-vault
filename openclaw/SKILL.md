---
name: knowledge-vault
description: Automatically extracts knowledge worth keeping from your AI conversations and syncs it to your local Obsidian vault. Supports scheduled collection, on-demand sync, vault reorganization, deletion feedback learning, and historical content retrieval.
triggers:
  - sync my knowledge vault
  - sync obsidian
  - knowledge vault sync
  - reorganize my vault
  - tidy up my knowledge base
  - I remember we talked about
  - remember this
  - save this to my vault
  - change vault collection time
---

# knowledge-vault (OpenClaw)

Automatically extracts knowledge from your AI agent conversations and stores it in your local Obsidian vault.

---

## Architecture: Two Stages

```
Stage 1: Cloud Collection (scheduled, silent)
  Scan today's conversations → evaluate → write to cloud cache
  Send lightweight notification to user

Stage 2: User-triggered Sync (on demand)
  User says trigger phrase
  → Read cache → write structured notes to local Obsidian via desktop node
```

---

## Stage 1: Scheduled Collection

### Schedule
- Default: daily at 18:00 (user's local time)
- User can change: "change vault collection time to 10pm"
- User can change frequency: "only on weekdays" / "twice a day"

### Execution

**Step 1: Get today's sessions**
Use `sessions_list` to find sessions updated today.

**Step 2: Read and evaluate each session**
Use `sessions_history` to read content. Evaluate each session:

```
P0 — User explicitly marked: "remember this", "save this"
     → Always include, no further judgment

P1 — High-density professional knowledge
     Signs: model explaining a non-trivial concept,
            user asking "what is X" / "how does X work"
     Examples: system design patterns, domain-specific terminology,
               technical architectures, research methodologies

P2 — Design decisions and reasoning
     Signs: comparing options, architecture discussion, "why" reasoning,
            vibe coding sessions where approach > code
     Examples: product design tradeoffs, technical architecture choices

P3 — Reusable SOPs / guides embedded in task conversations
     Signs: step-by-step instructions produced, process documented,
            content user would want to reference again
     Examples: setup guides, workflow SOPs, reference sheets

❌ Skip:
  - Pure task execution (send a message, check a date)
  - Small talk, emotional chat
  - One-off lookups (current weather, one specific number)
  - Content involving named individuals' performance reviews,
    compensation, or undisclosed business information
```

**Step 3: Write to cloud cache**

```
obsidian-output/
  YYYY-MM-DD/
    index.json          ← metadata for all notes this run
    [note-title].md     ← extracted note content
```

index.json format:
```json
{
  "run_id": "20260618-180000",
  "date": "2026-06-18",
  "notes": [
    {
      "title": "Note Title",
      "file": "Knowledge/AI/note-title.md",
      "suggested_folder": "Knowledge/AI",
      "priority": "P1",
      "summary": "One-line summary",
      "synced": false
    }
  ]
}
```

**Step 4: Send notification**

Send a brief, natural notification via the user's configured IM channel (if connected). Example:

> 📚 Picked up 2 things worth keeping from today's conversations:
> · Agent Two-Layer Architecture — clear mental model for scripting vs. reasoning boundaries
> · GraphRAG — knowledge-graph-enhanced retrieval, significant upgrade over naive RAG
>
> Say "sync my knowledge vault" whenever you're ready to push to Obsidian 📥

If nothing worth keeping: "Today's conversations were mostly task-focused — nothing to distill. See you tomorrow 👋"

### Cache Policy
- Keep last **7 days** of cache
- Auto-delete entries older than 7 days on each run
- Content not synced within 7 days is considered abandoned

---

## Stage 2: User-triggered Sync

### Trigger phrases
- "sync my knowledge vault"
- "sync obsidian"
- "knowledge vault sync"
- "push to obsidian"

### Execution

**Step 1: Check for user deletions (feedback learning)**

Before syncing new content, compare previous sync records against current vault state:

```
Previously synced files (synced: true in index.json)
  vs.
Current vault file list (fs_list)

Missing files = user deliberately deleted
```

For each deleted note:
1. Mark as `user_deleted: true` in `obsidian-output/deletion-log.json`
2. Never restore this content or close variants in future syncs
3. Analyze: what was the original priority? Why might it have been deleted?
4. Write calibration note to `vault-profile.json` → `calibration_log`
5. If 3+ deletions in one sync, notify user: "I noticed you removed X notes — I may have been scoring [topic type] too generously. I'll tighten that up."

**Step 2: Read cloud cache**
Scan all `synced: false` entries across all cached dates, sorted oldest first.

**Step 3: Read vault structure**
Use `fs_list` on the vault root. List existing folders as write targets.

**Step 4: Write notes**

For each note:
```
Target folder exists → write directly ✅

Target folder does not exist →
  Ask user:
    "1 note belongs in 'Systems & Infra/' — folder doesn't exist yet.
     A. Create it   B. Put it somewhere else   C. Skip"

  User chooses A →
    Run: mkdir -p '{VAULT_PATH}/Systems & Infra'
    Then write note
    Report: "Created folder and wrote note"

  User chooses B → write to specified existing folder
  User chooses C → write to Inbox/, note in changelog
```

**Step 5: De-duplicate**

Before writing any note, check for existing notes with similar titles or >60% content overlap:
- Title match → skip, log as duplicate
- Content overlap → mark as `action: append` candidate, ask user

**Step 6: Update index**
Mark successfully written notes as `synced: true`.

**Step 7: Sync summary**

```
✅ Sync complete
Added: X notes  |  Updated: Y notes  |  Skipped: Z (duplicates / expired)

New folder created: "Systems & Infra"
```

---

## Vault Reorganization

### Trigger phrases
- "reorganize my vault"
- "tidy up my knowledge base"
- "help me restructure my notes"

### Three modes

**Mode A — Full auto**
"Auto-reorganize everything"
→ Scan all notes, analyze content, re-classify and move
→ Report: "Moved X notes, created Y folders, merged Z duplicates"

**Mode B — Plan first**
"Tell me what you'd do before doing it"
→ Generate proposed changes, show to user
→ Execute only after explicit approval

**Mode C — Specific instruction**
"Move 'X' to 'Y'" / "Merge 'X' and 'Y'" / "Rename folder 'A' to 'B'"
→ Execute directly, confirm when done

### Implementation
- Move: `fs_read` source + `fs_write` destination + `fs_delete` source
- New folder: `mkdir -p` via desktop node shell
- All changes logged to `.changelog/` for rollback

---

## Historical Content Retrieval

### Trigger
"I remember we talked about X — why isn't it in my vault?"

### Execution
1. Search existing vault — confirm it's genuinely missing
2. Use `sessions_list` to find all historical sessions (not just today)
3. Search for sessions matching the topic
4. Evaluate content and suggested priority
5. Ask user: "Found it — in your session from [date]. Want me to save it now?"
6. On confirmation: extract, write to vault, update HOME.md

Also: log this retrieval in `vault-profile.json` → `user_interest_signals`. Increase sensitivity for this topic in future collection.

---

## Note Format

Read `vault-profile.json` before generating notes. Match the user's existing style.

Default format:

```markdown
# Note Title

**Source date**: YYYY-MM-DD | **Priority**: P1

---

## Core content

(Structured, with subheadings, 200–400 words)

---

## Related

- [[Linked concept 1]]
- [[Linked concept 2]]
```

---

## Tool Reference

| Tool | Stage | Purpose |
|------|-------|---------|
| `sessions_list` | Collection | Get today's session list |
| `sessions_history` | Collection | Read session content for evaluation |
| `write` | Collection | Write to cloud cache |
| `fs_list` | Sync | List vault folders |
| `fs_read` | Sync / Reorganize | Read vault-profile, existing notes |
| `fs_write` | Sync / Reorganize | Write notes to user's local machine |
| `fs_delete` | Reorganize / Rollback | Delete files (source after move) |
| `mkdir -p` (desktop node shell) | Sync / Reorganize | Create new folders |

---

## First-time Setup

See `README.md` in this directory.
