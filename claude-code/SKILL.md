---
name: knowledge-vault
description: Extract knowledge worth keeping from your Claude Code conversations and sync it to a local Obsidian vault. Use when the user says "sync my knowledge vault", "save this to my vault", "remember this", "what did we figure out", or asks to collect/distill insights from recent sessions. Two-way sync — deletions in the vault are read back as feedback.
---

# knowledge-vault (Claude Code)

Extract durable knowledge from Claude Code conversations and write it to the user's local Obsidian vault as linked Markdown notes. You are the agent — you read the conversation files, judge what's worth keeping, and write the notes yourself with Read / Glob / Grep / Bash / Write. No API key, no cron, no external service.

This is the Claude Code-native counterpart to the OpenClaw version and the Python CLI in this repo. Same design (P0–P3 extraction, style adaptation, deletion-is-feedback), different runtime: here the runtime is you.

---

## Configuration

On first use, read `vault-profile.json` in this skill's directory if present. If absent, ask the user for their **vault path** and the **target folder** for extracted notes, then create `vault-profile.json`:

```json
{
  "vault_path": "/Users/you/Desktop/Obsidian",
  "notes_folder": "claude_says",
  "language": "中文",
  "deletion_log": "claude_says/.deletion-log.json"
}
```

- `vault_path` — Obsidian vault root (a plain folder of Markdown files).
- `notes_folder` — where extracted notes go, relative to the vault root.
- `language` — the language to write notes in (match the user's existing notes).
- `deletion_log` — where the deletion-feedback record lives, relative to the vault root. Keep it inside the notes folder, hidden (leading dot), so it travels with the notes.

If the vault path is outside your working directory, you may need the user to grant access to it before you can read/write there.

---

## What to extract — priority system

Judge each conversation by this bar. Most task-execution chatter is **not** worth keeping.

```
P0 — User explicitly marked it
     "remember this", "save this to my vault", "note this down"
     → Always include.

P1 — High-density professional knowledge
     A non-trivial concept being explained; "what is X / how does X work";
     technical architectures, domain terminology, research methods.

P2 — Design decisions and reasoning
     Option comparisons, "why we chose X", problem-solving approaches,
     the insight behind a refactor — the thinking, not the diff.

P3 — Reusable SOPs / guides produced during a task
     Step-by-step procedures, setup guides, reference sheets the user
     would want to find again.

❌ Skip
     Pure task execution (run this command, fix this typo), small talk,
     one-off lookups, and any sensitive personal/business info
     (compensation, performance, undisclosed confidential matters).
```

When in doubt, lean toward **not** writing a note. A sparse, high-signal vault is the goal — the user curates by deleting, and you learn from that (see Deletion feedback).

---

## Where notes go — reuse the vault's existing taxonomy

**Before writing anything, learn the folder taxonomy the user already uses, and write into it. Do NOT invent a parallel set of folders.** This is the single most common failure mode: the user has a categorization scheme they arrived at deliberately (often refined with help over time), and inventing your own theme folders silently throws it away.

1. Glob the whole vault (not just `notes_folder`) and look at the **top-level folders** — e.g. `工作 / 项目 / 知识 / 方法论`, or `Knowledge / Frameworks / Projects / Inbox`. That set is the user's taxonomy. Treat it as fixed.
2. Place each note in the category that fits. A useful default split: **knowledge** (what X is / how it works — definitions, mechanisms, facts) vs **methodology** (how to do / how to judge — frameworks, procedures, heuristics) vs **project** (decisions and lessons specific to one project) vs **work** (reusable SOPs for recurring tasks).
3. Sub-folders *within* a category are fine and encouraged when the category has many notes — mirror the depth the vault already uses.
4. If `notes_folder` is a fresh/empty folder but the wider vault has an established taxonomy, **reuse that same taxonomy inside `notes_folder`** rather than starting from scratch.
5. Only when the vault has no discernible taxonomy at all should you fall back to the recommended starter structure (Knowledge / Frameworks / Projects / Inbox). Even then, ask the user before committing to a scheme.

If you're unsure which category a note belongs in, ask — don't guess and don't create a new top-level folder to sidestep the decision.

## Note format

**Match the vault's existing note style too.** Glob a few real notes and look at: note length, heading structure, link density, the metadata header (e.g. `**建立于** | **优先级**`). Write new notes to match what's there, not this template verbatim.

Default shape (adapt to the vault):

```markdown
# Note Title

**建立于**: YYYY-MM-DD | **优先级**: P1
**来源**: <which conversation / session, one line>

---

## Core content

Structured, with `##` subheadings. 200–400 words. Lead with the insight.

---

## 相关概念

- [[Linked concept]]
- [[Another note]]
```

- Write in the `language` from the profile.
- **Link liberally.** Use `[[wikilinks]]` to existing notes (Glob to find real titles) and to concepts that *should* exist — Obsidian's graph is the point.
- **Don't duplicate.** Before writing, Grep the vault for an existing note on the same topic. If one exists, link to it instead of rewriting; if it's close, suggest appending rather than creating a near-duplicate.

---

## Commands (triggered in conversation)

### Collect / sync — "sync my knowledge vault", "save what we figured out"

This is the main flow. It is **two-way reconciliation** between the conversation history and the vault. Do the reverse direction first.

**Step 1 — Reverse: read deletions back as feedback.**
Read the deletion log (`deletion_log` from the profile; treat missing as empty). Then, for every note you previously wrote (the log also tracks what you've written, or Glob the notes folder against your own past changelogs), check whether it still exists in the vault. A note you wrote that is now **gone** = the user deleted it deliberately.

For each newly-missing note:
1. Append it to the deletion log with its title, path, priority, folder, and date.
2. **Never recreate it or a close variant.**
3. Increment a calibration counter for its `(priority, folder)` bucket.
4. If a bucket reaches **2+** deletions, tell the user you're tightening the bar on that kind of content, and actually apply it in Step 3.

Deletion log shape:

```json
{
  "deleted": [
    {"title": "...", "path": "claude_says/....md", "priority": "P2",
     "folder": "claude_says", "detected_at": "YYYY-MM-DD"}
  ],
  "calibration": {
    "P2|claude_says": {"priority": "P2", "folder": "claude_says", "deletions": 2}
  }
}
```

**Step 2 — Pick the source conversations.**
By default, distill **the current conversation**. If the user says "sync my vault" broadly, you may also scan recent sessions:

```bash
# Recent Claude Code sessions for THIS project (most recent first)
ls -t ~/.claude/projects/<project-dir>/*.jsonl | head -10
```

Each line of a `.jsonl` is one event. Conversation turns are the lines where the top-level `type` is `user` or `assistant`; the actual role and content are nested under `.message.role` / `.message.content`. Skip `queue-operation`, `attachment`, `custom-title`, etc. Read with `jq` or Read.

**Step 3 — Extract.**
Apply the P0–P3 bar, *minus* anything in the never-recreate list, *with* the calibration adjustments. For each kept item, draft a note (matching vault style, deduped against existing notes).

**Step 4 — Write, asking before creating folders.**
Write each note into `notes_folder`. If a note belongs in a subfolder that doesn't exist, ask the user: create it / put it elsewhere / skip. Record what you wrote (title → actual path) so the next sync's reverse step can detect deletions accurately.

**Step 5 — Changelog.**
Summarize: what you added, what you skipped and why, what you noticed was deleted. This is the "transparent, not magic" principle — the user always knows what happened.

### remember this / save this — "remember this", "save this to my vault" (P0)

Force-save the thing the user just pointed at, regardless of the P1–P3 bar. Still dedupe and match style.

### find — "I remember we talked about X", "did we capture Y?"

1. Grep the vault first — confirm it's genuinely missing.
2. Search session history (`~/.claude/projects/`) for the topic.
3. If found, show the user what you'd save and ask before writing.

---

## Core principles (keep these true)

1. **The user sets the bar.** P0–P3 above. Skip sensitive content always, even if asked — flag it instead.
2. **Deletion is feedback.** Sync reads deletions back. Never restore a deleted note; self-calibrate scoring. This fires at sync time — no background watcher.
3. **Reuse the vault's taxonomy — don't invent one.** Read the existing top-level folders first and write into them; match note length and link density. Never create a parallel folder scheme (see "Where notes go").
4. **Transparent, not magic.** Every sync produces a changelog. The user can always ask "why did you save / skip / delete X".

---

## First-time setup

See `README.md` in this directory for the broader project. To install this skill globally:

```bash
mkdir -p ~/.claude/skills/knowledge-vault
cp SKILL.md ~/.claude/skills/knowledge-vault/
# then create vault-profile.json there on first use
```
