#!/usr/bin/env python3
"""
knowledge-vault — Claude Code version
Extracts knowledge from Claude Code conversations and writes to Obsidian.
"""

import os
import json
import glob
import argparse
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import anthropic

# ── Config ────────────────────────────────────────────────────────────────────

PROFILE_PATH  = Path(__file__).parent / "vault-profile.json"
CACHE_DIR     = Path(__file__).parent / ".cache"
DELETION_LOG  = CACHE_DIR / "deletion-log.json"

def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        print("vault-profile.json not found. Copy vault-profile-template.json and configure it.")
        raise SystemExit(1)
    return json.loads(PROFILE_PATH.read_text())

# ── Conversation reader ───────────────────────────────────────────────────────

def read_today_sessions(projects_path: str) -> list[dict]:
    """Read all Claude Code sessions updated today."""
    today = datetime.now().date()
    sessions = []
    pattern = os.path.expanduser(f"{projects_path}/**/*.jsonl")

    for path in glob.glob(pattern, recursive=True):
        mtime = datetime.fromtimestamp(os.path.getmtime(path)).date()
        if mtime != today:
            continue
        messages = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if messages:
            sessions.append({"path": path, "messages": messages})

    return sessions

def format_session(session: dict) -> str:
    """Format a session's messages into readable text for the model.

    Claude Code JSONL nests role/content under a `message` object and uses the
    top-level `type` to tag the line kind. Only user/assistant lines carry a
    conversation turn; queue-operation/attachment/custom-title/etc. are skipped.
    """
    lines = []
    for entry in session["messages"]:
        if entry.get("type") not in ("user", "assistant"):
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        role = message.get("role", entry["type"])
        content = message.get("content", "")
        if isinstance(content, list):
            # Handle content blocks
            content = " ".join(
                block.get("text", "") for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        if isinstance(content, str) and content.strip():
            lines.append(f"[{role.upper()}]: {content[:2000]}")
    return "\n\n".join(lines)

# ── Extraction ────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are a personal knowledge curator. Your job is to extract knowledge worth keeping from AI conversation logs.

Evaluate the conversation and extract notes according to this priority system:

P0 — User explicitly marked: phrases like "remember this", "save this", "note this down"
     → Always include

P1 — High-density professional knowledge being explained
     → Non-trivial concepts, "what is X / how does X work" answers, technical architectures,
        domain-specific terminology, research methodologies

P2 — Design decisions and reasoning processes
     → Option comparisons, architecture discussions, "why" reasoning,
        problem-solving approaches worth reusing

P3 — Reusable SOPs or guides embedded in task work
     → Step-by-step instructions produced, process documentation,
        reference content the user might want again

SKIP:
     → Pure task execution (send a message, check a calendar)
     → Small talk or emotional support
     → One-off lookups (weather, single numbers, transient facts)
     → Content involving named individuals' performance, compensation,
       or undisclosed confidential business information

For each note worth extracting, output a JSON object in this format:
{
  "title": "Concise descriptive title",
  "priority": "P1",
  "suggested_folder": "Knowledge/AI",
  "summary": "One sentence: what this is and why it matters",
  "content": "Full note content in Markdown, 200-400 words, with ## subheadings"
}

Output a JSON array of note objects. If nothing is worth keeping, output an empty array [].
Do not output anything other than the JSON array."""


def extract_notes(session_text: str, client: anthropic.Anthropic, model: str,
                  calibration: str = "") -> list[dict]:
    """Call Claude to extract knowledge notes from a session.

    `calibration` is an optional prompt addendum derived from the user's past
    deletions, nudging the extractor to score repeatedly-deleted patterns more
    conservatively.
    """
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[
            {"role": "user", "content": f"{EXTRACTION_PROMPT}{calibration}\n\n---\n\n{session_text}"}
        ]
    )
    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []

# ── Cache ─────────────────────────────────────────────────────────────────────

def write_cache(notes: list[dict], run_id: str) -> Path:
    """Write extracted notes to local cache."""
    run_dir = CACHE_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    index = {
        "run_id": run_id,
        "date": run_id[:8],
        "notes": []
    }

    for note in notes:
        slug = note["title"].lower().replace(" ", "-").replace("/", "-")[:50]
        filename = f"{slug}.md"
        (run_dir / filename).write_text(
            f"# {note['title']}\n\n"
            f"**Source date**: {run_id[:4]}-{run_id[4:6]}-{run_id[6:8]} | "
            f"**Priority**: {note['priority']}\n\n---\n\n"
            f"{note['content']}\n\n---\n\n## Related\n\n"
        )
        index["notes"].append({
            "title": note["title"],
            "file": f"{note['suggested_folder']}/{filename}",
            "suggested_folder": note["suggested_folder"],
            "priority": note["priority"],
            "summary": note["summary"],
            "synced": False,
            "cache_path": str(run_dir / filename)
        })

    (run_dir / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False))
    return run_dir

def purge_old_cache(days: int):
    """Delete cache entries older than `days` days."""
    if not CACHE_DIR.exists():
        return
    cutoff = datetime.now() - timedelta(days=days)
    for entry in CACHE_DIR.iterdir():
        if not entry.is_dir():
            continue
        try:
            entry_date = datetime.strptime(entry.name[:8], "%Y%m%d")
            if entry_date < cutoff:
                shutil.rmtree(entry)
                print(f"Purged old cache: {entry.name}")
        except ValueError:
            pass

def load_all_unsynced() -> list[dict]:
    """Load all unsynced notes from cache."""
    unsynced = []
    if not CACHE_DIR.exists():
        return unsynced
    for run_dir in sorted(CACHE_DIR.iterdir()):
        index_path = run_dir / "index.json"
        if not index_path.exists():
            continue
        index = json.loads(index_path.read_text())
        for note in index["notes"]:
            if not note.get("synced"):
                note["_run_dir"] = str(run_dir)
                note["_index_path"] = str(index_path)
                unsynced.append(note)
    return unsynced

def mark_synced(note: dict, written_path: str):
    """Mark a note as synced in its index.json, recording where it was written.

    `written_path` is the note's actual location relative to the vault root, so
    deletion detection on the next sync can check the real file rather than the
    originally-suggested folder.
    """
    index_path = Path(note["_index_path"])
    index = json.loads(index_path.read_text())
    for n in index["notes"]:
        if n["title"] == note["title"]:
            n["synced"] = True
            n["synced_path"] = written_path
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False))

# ── Deletion feedback ───────────────────────────────────────────────────────────
#
# Sync is bidirectional reconciliation between local memory (.cache) and the
# Obsidian vault. The forward direction pushes new notes into the vault. The
# reverse direction — handled here — reads the user's deletions back: a note
# that was synced but is no longer in the vault was deliberately removed. We
# record it so it's never re-created, and reflect on whether scoring of that
# priority/folder was too generous. The same "deletion is feedback" rule the
# OpenClaw version applies at sync time.

def load_deletion_log() -> dict:
    if not DELETION_LOG.exists():
        return {"deleted": [], "calibration": {}}
    try:
        return json.loads(DELETION_LOG.read_text())
    except json.JSONDecodeError:
        return {"deleted": [], "calibration": {}}

def save_deletion_log(log: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DELETION_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False))

def detect_deletions(vault_path: str) -> list[dict]:
    """Find notes that were synced to the vault but the user has since deleted.

    Compares each cached note marked synced (with a recorded synced_path)
    against the current vault. Anything missing is treated as a deliberate
    deletion. Records it in the deletion log (never restore again) and updates
    per-(priority, folder) calibration counts so collect can tighten scoring.
    Returns the list of newly-detected deletions.
    """
    log = load_deletion_log()
    already = {d["synced_path"] for d in log["deleted"]}
    new_deletions = []

    for run_dir in sorted(CACHE_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        index_path = run_dir / "index.json"
        if not index_path.exists():
            continue
        index = json.loads(index_path.read_text())
        for note in index["notes"]:
            synced_path = note.get("synced_path")
            if not note.get("synced") or not synced_path:
                continue
            if synced_path in already:
                continue
            if (Path(vault_path) / synced_path).exists():
                continue
            # Synced before, not in the vault now → user deleted it.
            folder = synced_path.rsplit("/", 1)[0] if "/" in synced_path else ""
            entry = {
                "title": note["title"],
                "synced_path": synced_path,
                "priority": note.get("priority", ""),
                "folder": folder,
                "detected_at": datetime.now().strftime("%Y-%m-%d"),
            }
            log["deleted"].append(entry)
            already.add(synced_path)
            new_deletions.append(entry)

            key = f"{note.get('priority', '?')}|{folder}"
            cal = log["calibration"].setdefault(
                key, {"priority": note.get("priority", ""), "folder": folder, "deletions": 0}
            )
            cal["deletions"] += 1

    if new_deletions:
        save_deletion_log(log)
    return new_deletions

def deleted_titles() -> set[str]:
    """Titles the user has deleted — never re-extract these."""
    return {d["title"].strip().lower() for d in load_deletion_log()["deleted"]}

def calibration_guidance() -> str:
    """Build a prompt addendum from accumulated deletion patterns.

    Surfaces (priority, folder) buckets the user has repeatedly deleted so the
    extractor scores them more conservatively. Empty string if no signal yet.
    """
    cal = load_deletion_log()["calibration"]
    hot = [c for c in cal.values() if c["deletions"] >= 2]
    if not hot:
        return ""
    hot.sort(key=lambda c: c["deletions"], reverse=True)
    lines = [
        f'- {c["deletions"]} deletions from "{c["folder"] or "(root)"}" '
        f'at priority {c["priority"] or "?"}'
        for c in hot
    ]
    return (
        "\n\nCALIBRATION — the user has repeatedly deleted notes matching these "
        "patterns. Score similar content more conservatively (raise the bar or "
        "skip it):\n" + "\n".join(lines)
    )

# ── Vault writing ─────────────────────────────────────────────────────────────

def write_note_to_vault(note: dict, vault_path: str, dry_run: bool = False) -> str | None:
    """Write a single note to the Obsidian vault.

    Returns the path it wrote, relative to the vault root (e.g.
    "Knowledge/AI/foo.md"), or None if skipped. The returned path is the
    *actual* location — which may differ from suggested_folder when the user
    redirects to Inbox or a custom folder — and is what sync records so that
    later deletion detection compares against the real file.
    """
    target_dir = Path(vault_path) / note["suggested_folder"]
    filename = Path(note["file"]).name
    target_path = target_dir / filename

    if not target_dir.exists():
        print(f"\n  Folder '{note['suggested_folder']}' doesn't exist.")
        print(f"  Note: {note['title']}")
        choice = input("  [A]uto-create  [S]kip  [P]ath (enter custom folder): ").strip().lower()

        if choice == "a":
            if not dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)
            print(f"  ✓ Created: {note['suggested_folder']}")
        elif choice == "s":
            print("  Skipped.")
            return None
        else:
            custom = choice if choice else "Inbox"
            target_dir = Path(vault_path) / custom
            target_path = target_dir / filename
            if not dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)

    content = Path(note["cache_path"]).read_text()
    rel_path = str(target_path.relative_to(vault_path))

    if dry_run:
        print(f"  [DRY RUN] Would write: {target_path}")
        return rel_path

    target_path.write_text(content)
    print(f"  ✓ {note['title']} → {rel_path}")
    return rel_path

# ── Notify ────────────────────────────────────────────────────────────────────

def notify(title: str, message: str):
    """Send a system notification (macOS)."""
    try:
        os.system(f'osascript -e \'display notification "{message}" with title "{title}"\'')
    except Exception:
        pass  # Fail silently on non-Mac

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_collect(profile: dict):
    """Collect and extract knowledge from today's conversations."""
    print("📖 Reading today's Claude Code sessions...")

    client = anthropic.Anthropic(api_key=os.environ.get(profile.get("api_key_env", "ANTHROPIC_API_KEY")))
    model  = profile.get("model", "claude-opus-4-8")

    sessions = read_today_sessions(profile["claude_projects_path"])
    if not sessions:
        print("No sessions updated today.")
        return

    print(f"Found {len(sessions)} session(s). Extracting knowledge...")

    # Deletion feedback: nudge scoring away from patterns the user deletes, and
    # never re-create a note the user has already removed.
    calibration = calibration_guidance()
    skip_titles = deleted_titles()

    run_id    = datetime.now().strftime("%Y%m%d-%H%M%S")
    all_notes = []

    for i, session in enumerate(sessions, 1):
        text  = format_session(session)
        notes = extract_notes(text, client, model, calibration=calibration)
        kept  = [n for n in notes if n.get("title", "").strip().lower() not in skip_titles]
        dropped = len(notes) - len(kept)
        suffix = f" ({dropped} skipped — previously deleted)" if dropped else ""
        print(f"  Session {i}/{len(sessions)}: {len(kept)} note(s) extracted{suffix}")
        all_notes.extend(kept)

    if not all_notes:
        print("Nothing worth keeping today.")
        if profile.get("notify"):
            notify("knowledge-vault", "Today's conversations were mostly task-focused — nothing to distill.")
        return

    write_cache(all_notes, run_id)
    purge_old_cache(profile.get("cache_days", 7))

    titles = "\n".join(f"  · {n['title']}" for n in all_notes)
    print(f"\n✅ Extracted {len(all_notes)} note(s):\n{titles}")
    print("\nRun `python vault_agent.py sync` to push to Obsidian.")

    if profile.get("notify"):
        notify(
            "knowledge-vault",
            f"Extracted {len(all_notes)} notes. Run sync to push to Obsidian."
        )


def cmd_sync(profile: dict, dry_run: bool = False):
    """Sync — reconcile local memory (.cache) with the Obsidian vault, both ways.

    Reverse direction first: read back any notes the user deleted from the vault
    and record them as feedback (never restore + self-calibrate). Forward
    direction: push new extracted notes into the vault.
    """
    vault_path = profile.get("vault_path")
    if not vault_path:
        print("vault_path not set in vault-profile.json")
        return

    # ── Reverse: pull deletion signals from the vault ──
    if not dry_run:
        deletions = detect_deletions(vault_path)
        if deletions:
            print(f"🗑️  Noticed {len(deletions)} note(s) you removed from the vault:")
            for d in deletions:
                print(f"  · {d['title']}  ({d['synced_path']})")
            print("  These won't be re-created, and I'll score similar content more conservatively.")
            if profile.get("notify") and len(deletions) >= 3:
                notify(
                    "knowledge-vault",
                    f"You removed {len(deletions)} notes — tightening how I score similar content.",
                )

    # ── Forward: push new notes into the vault ──
    unsynced = load_all_unsynced()
    if not unsynced:
        print("Nothing new to sync — cache is empty or all notes already synced.")
        return

    print(f"📥 Syncing {len(unsynced)} note(s) to Obsidian...")
    if dry_run:
        print("  (dry run — no files will be written)\n")

    synced = 0
    for note in unsynced:
        written_path = write_note_to_vault(note, vault_path, dry_run=dry_run)
        if written_path and not dry_run:
            mark_synced(note, written_path)
            synced += 1

    if not dry_run:
        print(f"\n✅ Sync complete — {synced}/{len(unsynced)} note(s) written.")


def cmd_history():
    """Show recent sync history."""
    if not CACHE_DIR.exists():
        print("No cache found.")
        return
    for run_dir in sorted(CACHE_DIR.iterdir(), reverse=True)[:5]:
        index_path = run_dir / "index.json"
        if not index_path.exists():
            continue
        index = json.loads(index_path.read_text())
        total  = len(index["notes"])
        synced = sum(1 for n in index["notes"] if n.get("synced"))
        print(f"  {index['run_id']}  {total} notes  ({synced} synced)")


def cmd_rollback():
    """Roll back the most recent sync."""
    if not CACHE_DIR.exists():
        print("No cache found.")
        return
    run_dirs = sorted(CACHE_DIR.iterdir(), reverse=True)
    for run_dir in run_dirs:
        index_path = run_dir / "index.json"
        if not index_path.exists():
            continue
        index = json.loads(index_path.read_text())
        synced_notes = [n for n in index["notes"] if n.get("synced")]
        if not synced_notes:
            continue
        vault_path = load_profile().get("vault_path")
        print(f"Rolling back {len(synced_notes)} note(s) from run {index['run_id']}...")
        for note in synced_notes:
            target = Path(vault_path) / note["file"]
            if target.exists():
                target.unlink()
                print(f"  Removed: {note['title']}")
            note["synced"] = False
        index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False))
        print("✅ Rollback complete.")
        return
    print("Nothing to roll back.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="knowledge-vault — Claude Code version")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("collect",  help="Extract knowledge from today's conversations")
    sync_p = sub.add_parser("sync", help="Sync cached notes to Obsidian")
    sync_p.add_argument("--dry-run", action="store_true", help="Preview without writing")
    sub.add_parser("history",  help="Show recent run history")
    sub.add_parser("rollback", help="Roll back the last sync")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    profile = load_profile()

    if args.command == "collect":
        cmd_collect(profile)
    elif args.command == "sync":
        cmd_sync(profile, dry_run=args.dry_run)
    elif args.command == "history":
        cmd_history()
    elif args.command == "rollback":
        cmd_rollback()


if __name__ == "__main__":
    main()
