#!/usr/bin/env python3
"""Dual memory system for skill-security meta-skill.

Identical architecture to tt_memory.py / fg_memory.py / yt_memory.py:
- Shared memory  (data/memory.json)  — sanitized, shipped with plugin
- Private memory (~/.config/skill-security/memory.json) — as-is, stays local
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
MEMORY_PATH = SKILL_ROOT / "data" / "memory.json"


def _get_config_dir():
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", "~")) / "skill-security"
    else:
        base = Path.home() / ".config" / "skill-security"
    base.mkdir(parents=True, exist_ok=True)
    return base


PRIVATE_MEMORY_PATH = _get_config_dir() / "memory.json"


def _load_sensitive_patterns():
    """Build patterns to sanitize from memory entries.

    For the meta-skill there are no API credentials.
    Instead we sanitize absolute user paths and service-specific data.
    """
    exact_strings = []
    regex_patterns = []

    # Sanitize home directory paths
    home = str(Path.home())
    if home and len(home) > 3:
        exact_strings.append(home)

    # Sanitize absolute paths that look like skill directories
    regex_patterns.append(
        (re.compile(r'/(?:home|root|Users)/[^\s"\']+/(?:skills|projects)/[^\s"\']+'), '<skill_path>')
    )
    # Sanitize Windows paths
    regex_patterns.append(
        (re.compile(r'[A-Z]:\\[^\s"\']+\\(?:skills|projects)\\[^\s"\']+'), '<skill_path>')
    )
    # Sanitize real service URLs
    regex_patterns.append(
        (re.compile(r'https?://(?!developer\.|api\.)[a-zA-Z0-9.-]+\.(?:com|org|io|net)/[^\s"\']*'), '<service_url>')
    )
    # Sanitize token-like strings
    regex_patterns.append(
        (re.compile(r'(?:figd_|y0__|ghp_|xox[baprs]-)[A-Za-z0-9_-]{10,}'), '***')
    )
    # Sanitize emails
    regex_patterns.append(
        (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), '<email>')
    )

    return exact_strings, regex_patterns


def _sanitize_text(text):
    """Remove sensitive data from text, keeping generic mechanics."""
    if not text:
        return text

    exact_strings, regex_patterns = _load_sensitive_patterns()

    for s in exact_strings:
        text = text.replace(s, "<home>")

    for pat, replacement in regex_patterns:
        text = pat.sub(replacement, text)

    return text


def _load_store(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_store(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def load_memory():
    return _load_store(MEMORY_PATH)


def save_memory(entries):
    _save_store(MEMORY_PATH, entries)


def load_private_memory():
    return _load_store(PRIVATE_MEMORY_PATH)


def save_private_memory(entries):
    _save_store(PRIVATE_MEMORY_PATH, entries)


def _score_entries(entries, context_lower, tokens):
    """Score entries by relevance to context."""
    scored = []
    for e in entries:
        if e.get("status") == "deleted":
            continue
        score = 0
        # Promoted entries get a bonus
        if e.get("status") == "promoted":
            score += 1
        for tag in e.get("tags", []):
            if tag.lower() in context_lower:
                score += 2
        prob = e.get("problem", "").lower()
        sol = e.get("solution", "").lower()
        for t in tokens:
            if len(t) > 3:
                if t in prob:
                    score += 1
                if t in sol:
                    score += 0.5
        if score > 0:
            scored.append((score, e))
    return scored


def check_memory(context):
    """Search BOTH shared and private memory. Returns (top3_entries, best_solution_or_None)."""
    context_lower = context.lower()
    tokens = set(context_lower.split())

    shared = load_memory()
    private = load_private_memory()

    scored = _score_entries(shared, context_lower, tokens)
    scored += _score_entries(private, context_lower, tokens)

    scored.sort(key=lambda x: -x[0])
    top3 = [item[1] for item in scored[:3]]

    if top3:
        top_ids = {e["id"] for e in top3}
        shared_changed = False
        for e in shared:
            if e["id"] in top_ids:
                e["hit_count"] = e.get("hit_count", 0) + 1
                shared_changed = True
        if shared_changed:
            save_memory(shared)

        private_changed = False
        for e in private:
            if e["id"] in top_ids:
                e["hit_count"] = e.get("hit_count", 0) + 1
                private_changed = True
        if private_changed:
            save_private_memory(private)

    best_solution = top3[0].get("solution") if top3 else None
    return top3, best_solution


def _next_id(entries, prefix):
    max_id = 0
    for e in entries:
        eid = e.get("id", "")
        if eid.startswith(prefix):
            try:
                num = int(eid.split("_")[1])
                if num > max_id:
                    max_id = num
            except (IndexError, ValueError):
                pass
    return max_id + 1


def record_entry(problem, solution, tags, category="audit_finding", private=False):
    """Add a memory entry. Shared entries are sanitized; private entries are stored as-is."""
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")] if tags else []

    if private:
        entries = load_private_memory()
        entry = {
            "id": f"prv_{_next_id(entries, 'prv'):03d}",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "category": category,
            "problem": problem,
            "solution": solution,
            "tags": tags,
            "hit_count": 0,
            "confirmations": 0,
            "status": "active",
        }
        entries.append(entry)
        save_private_memory(entries)
    else:
        problem = _sanitize_text(problem)
        solution = _sanitize_text(solution)
        tags = [_sanitize_text(t) for t in tags]

        entries = load_memory()
        entry = {
            "id": f"mem_{_next_id(entries, 'mem'):03d}",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "category": category,
            "problem": problem,
            "solution": solution,
            "tags": tags,
            "hit_count": 0,
            "confirmations": 0,
            "status": "active",
        }
        entries.append(entry)
        save_memory(entries)

    return entry


def confirm_entry(mem_id):
    """Increment confirmations counter. Returns updated entry or None."""
    for loader, saver in [(load_memory, save_memory), (load_private_memory, save_private_memory)]:
        entries = loader()
        for e in entries:
            if e["id"] == mem_id:
                e["confirmations"] = e.get("confirmations", 0) + 1
                saver(entries)
                return e
    return None


def promote_entry(mem_id):
    """Mark entry as promoted. Returns updated entry or None."""
    for loader, saver in [(load_memory, save_memory), (load_private_memory, save_private_memory)]:
        entries = loader()
        for e in entries:
            if e["id"] == mem_id:
                e["status"] = "promoted"
                saver(entries)
                return e
    return None


# ── CLI ──────────────────────────────────────────────────────────

def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(0 if obj.get("ok") else 1)


def cmd_check(args):
    top3, _ = check_memory(args.context)
    shared = load_memory()
    private = load_private_memory()
    out({"ok": True, "data": {"matches": top3, "total_checked": len(shared) + len(private)}})


def cmd_record(args):
    entry = record_entry(args.problem, args.solution, args.tags,
                         args.category or "audit_finding", private=args.private)
    out({"ok": True, "data": entry})


def cmd_confirm(args):
    entry = confirm_entry(args.mem_id)
    if entry is None:
        out({"ok": False, "error": f"Memory entry {args.mem_id} not found", "error_type": "not_found"})
    promote_ready = entry.get("confirmations", 0) >= 2 and entry.get("status") != "promoted"
    out({"ok": True, "data": entry, "meta": {"promote_ready": promote_ready}})


def cmd_promote(args):
    entry = promote_entry(args.mem_id)
    if entry is None:
        out({"ok": False, "error": f"Memory entry {args.mem_id} not found", "error_type": "not_found"})
    out({"ok": True, "data": entry})


def cmd_list(args):
    if args.private:
        entries = load_private_memory()
        store = "private"
    else:
        entries = load_memory()
        store = "shared"
    if args.category:
        entries = [e for e in entries if e.get("category") == args.category]
    if args.status:
        entries = [e for e in entries if e.get("status") == args.status]
    summary = []
    for e in entries:
        summary.append({
            "id": e["id"],
            "category": e.get("category", ""),
            "problem": e.get("problem", "")[:100],
            "tags": e.get("tags", []),
            "hit_count": e.get("hit_count", 0),
            "confirmations": e.get("confirmations", 0),
            "status": e.get("status", "active"),
        })
    out({"ok": True, "data": {"store": store, "entries": summary, "total": len(summary)}})


def main():
    parser = argparse.ArgumentParser(description="Skill-security dual memory")
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check")
    p_check.add_argument("context", help="Context string to search for")

    p_record = sub.add_parser("record")
    p_record.add_argument("--problem", required=True)
    p_record.add_argument("--solution", required=True)
    p_record.add_argument("--tags", default="")
    p_record.add_argument("--category", default="audit_finding")
    p_record.add_argument("--private", action="store_true",
                          help="Store in private memory (~/.config/, not shared)")

    p_confirm = sub.add_parser("confirm")
    p_confirm.add_argument("mem_id", help="Memory entry ID (e.g. mem_001)")

    p_promote = sub.add_parser("promote")
    p_promote.add_argument("mem_id", help="Memory entry ID to mark as promoted")

    p_list = sub.add_parser("list")
    p_list.add_argument("--category", default="", help="Filter by category")
    p_list.add_argument("--status", default="", help="Filter by status")
    p_list.add_argument("--private", action="store_true",
                        help="List private memory entries")

    args = parser.parse_args()

    commands = {
        "check": cmd_check,
        "record": cmd_record,
        "confirm": cmd_confirm,
        "promote": cmd_promote,
        "list": cmd_list,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
