#!/usr/bin/env python3
"""Canonical templates for skill files.

Contains string.Template-based templates with placeholders for:
- *_memory.py  (dual memory)
- *_auth.py    (credential management)
- config.json  (universal settings)
- SKILL.md sections (security, dual memory, Step 0)

Rebuild logic: diff current state vs template, generate patches.
"""

import json
import re
import sys
from pathlib import Path
from string import Template

SKILL_ROOT = Path(__file__).resolve().parent.parent

# ═══════════════════════════════════════════════════════════════
# TEMPLATE: *_memory.py
# ═══════════════════════════════════════════════════════════════

MEMORY_TEMPLATE = Template('''\
#!/usr/bin/env python3
"""Self-learning memory for ${SERVICE_NAME} skill."""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
MEMORY_PATH = PLUGIN_ROOT / "data" / "memory.json"


def _get_config_dir(account="default"):
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", "~")) / "${CONFIG_DIR}" / account
    else:
        base = Path.home() / ".config" / "${CONFIG_DIR}" / account
    base.mkdir(parents=True, exist_ok=True)
    return base


def _get_credentials_path(account="default"):
    return _get_config_dir(account) / "credentials.json"


PRIVATE_MEMORY_PATH = _get_config_dir() / "memory.json"


def _load_sensitive_patterns():
    """Load sensitive strings from credentials that must never appear in memory."""
    cred_path = _get_credentials_path()
    if not cred_path.exists():
        return [], []

    try:
        with open(cred_path) as f:
            creds = json.load(f)
    except (json.JSONDecodeError, OSError):
        return [], []

    sensitive = []
    for key in (${SENSITIVE_EXACT_FIELDS}):
        val = creds.get(key, "")
        if val and len(str(val)) > 5:
            sensitive.append(str(val))

    patterns = []
${SENSITIVE_REGEX_PATTERNS}

    return sensitive, patterns


def _sanitize_text(text):
    """Remove sensitive data from text, keeping generic mechanics."""
    if not text:
        return text

    sensitive, patterns = _load_sensitive_patterns()

    for s in sensitive:
        text = text.replace(s, "***")

    for pat, replacement in patterns:
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


def record_entry(problem, solution, tags, category="error_solution", private=False):
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
    entries = load_memory()
    for e in entries:
        if e["id"] == mem_id:
            e["confirmations"] = e.get("confirmations", 0) + 1
            save_memory(entries)
            return e
    return None


def promote_entry(mem_id):
    """Mark entry as promoted. Returns updated entry or None."""
    entries = load_memory()
    for e in entries:
        if e["id"] == mem_id:
            e["status"] = "promoted"
            save_memory(entries)
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
                         args.category or "error_solution", private=args.private)
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
    parser = argparse.ArgumentParser(description="${SERVICE_NAME} self-learning memory")
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check")
    p_check.add_argument("context", help="Context string to search for")

    p_record = sub.add_parser("record")
    p_record.add_argument("--problem", required=True)
    p_record.add_argument("--solution", required=True)
    p_record.add_argument("--tags", default="")
    p_record.add_argument("--category", default="error_solution")
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
''')


# ═══════════════════════════════════════════════════════════════
# TEMPLATE: *_auth.py
# ═══════════════════════════════════════════════════════════════

AUTH_TEMPLATE = Template('''\
#!/usr/bin/env python3
"""Credential management for ${SERVICE_NAME} skill."""

import argparse
import json
import os
import stat
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def _get_config_dir(account="default"):
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", "~")) / "${CONFIG_DIR}" / account
    else:
        base = Path.home() / ".config" / "${CONFIG_DIR}" / account
    base.mkdir(parents=True, exist_ok=True)
    return base


def _get_credentials_path(account="default"):
    return _get_config_dir(account) / "credentials.json"


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(0 if obj.get("ok") else 1)


def cmd_check_credentials(args):
    """Check if credentials file exists WITHOUT reading contents."""
    cred_path = _get_credentials_path(args.account)
    exists = cred_path.exists() and cred_path.stat().st_size > 2
    data = {
        "exists": exists,
        "path": str(cred_path),
    }
    if not exists:
        data["setup_hint"] = (
${SETUP_HINT_TEXT}
        )
    out({"ok": True, "data": data})


def cmd_save_token(args):
    """Save credentials with chmod 600."""
    cred_path = _get_credentials_path(args.account)
    creds = {}
    if cred_path.exists():
        try:
            with open(cred_path) as f:
                creds = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    creds[args.field] = args.value
    cred_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cred_path, "w") as f:
        json.dump(creds, f, indent=2)

    if sys.platform != "win32":
        try:
            os.chmod(cred_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
        except OSError:
            pass

    out({"ok": True, "data": {"message": f"Credential '{args.field}' saved successfully"}})


def cmd_setup(args):
    """Print full setup instructions."""
    out({"ok": True, "data": {"instructions": (
${SETUP_HINT_TEXT}
    )}})


def main():
    parser = argparse.ArgumentParser(description="${SERVICE_NAME} credential management")
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check-credentials",
                             help="Check if credentials file exists (no read)")
    p_check.add_argument("--account", default="default")

    p_save = sub.add_parser("save-token", help="Save a credential field")
    p_save.add_argument("--field", required=True, help="Credential field name")
    p_save.add_argument("--value", required=True, help="Credential value")
    p_save.add_argument("--account", default="default")

    p_setup = sub.add_parser("setup", help="Print setup instructions")
    p_setup.add_argument("--account", default="default")

    args = parser.parse_args()

    commands = {
        "check-credentials": cmd_check_credentials,
        "save-token": cmd_save_token,
        "setup": cmd_setup,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
''')


# ═══════════════════════════════════════════════════════════════
# TEMPLATE: SKILL.md sections
# ═══════════════════════════════════════════════════════════════

SECURITY_SECTION_TEMPLATE = Template('''\
## Безопасность

**Токены НИКОГДА не попадают в контекст разговора.**

- **Проверка наличия credentials:** только `${PREFIX}_auth.py check-credentials` (проверяет существование файла, НЕ читает содержимое)
- **Сохранение credentials:** только `${PREFIX}_auth.py save-token`
- **ЗАПРЕЩЕНО:** Read/cat/head/tail credentials.json — НИКОГДА не читать файл с токенами
- Скрипты (${PREFIX}_api.py и др.) читают токен внутренне для API-вызовов — это безопасно, токен не выводится в stdout
''')

DUAL_MEMORY_SECTION_TEMPLATE = Template('''\
## Разделение данных (двойная память)

### В shared memory (data/memory.json) — деперсонализированное:
- Общие API-паттерны, особенности API, решения ошибок
- Формулировки без реальных данных (QUEUE-NNN вместо PROJ-47)

### В private memory (~/.config/${CONFIG_DIR}/memory.json) — персональное:
- Реальные ключи задач, имена людей, проектная специфика
- Контекст конкретного пользователя/организации

### НИКОГДА в shared:
- Токены, org_id, client_secret, реальные URLs
- Реальные имена пользователей, email
- Реальные идентификаторы проектов/задач
''')

STEP0_SECTION_TEMPLATE = Template('''\
### Step 0 — Проверка credentials (ОБЯЗАТЕЛЬНО)

```bash
cd <skill_path>/scripts && python3 ${PREFIX}_auth.py check-credentials
```

- Если `"exists": false` — показать инструкцию из `setup_hint` и ОСТАНОВИТЬСЯ
- Если `"exists": true` — продолжить

### Step 1 — Проверка памяти

```bash
cd <skill_path>/scripts && python3 ${PREFIX}_memory.py check "<контекст запроса>"
```

- Если есть релевантные записи — использовать как подсказку
''')


# ═══════════════════════════════════════════════════════════════
# TEMPLATE: config.json
# ═══════════════════════════════════════════════════════════════

CONFIG_TEMPLATE = Template('''\
{
  "base_url": "${BASE_URL}",
  "cache_ttl": 3600,
  "rate_limit_delay": 1.0,
  "retry_delays": [1, 3, 10]
}
''')


# ═══════════════════════════════════════════════════════════════
# REBUILD LOGIC
# ═══════════════════════════════════════════════════════════════

def _detect_service_info(skill_path):
    """Detect service name, prefix, config dir from skill files."""
    skill_path = Path(skill_path).resolve()
    info = {
        "service_name": skill_path.name,
        "prefix": "",
        "config_dir": skill_path.name,
        "base_url": "",
        "sensitive_exact_fields": [],
        "sensitive_regex_patterns": [],
        "credential_fields": [],
        "setup_hint": "",
    }

    # Find prefix from existing scripts
    for py in (skill_path / "scripts").glob("*_api.py"):
        info["prefix"] = py.stem.split("_")[0]
        break
    if not info["prefix"]:
        for py in (skill_path / "scripts").glob("*_memory.py"):
            info["prefix"] = py.stem.split("_")[0]
            break
    if not info["prefix"]:
        info["prefix"] = info["service_name"][:2]

    # Parse config.json for base_url
    config_path = skill_path / "config" / "config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                cfg = json.load(f)
            info["base_url"] = cfg.get("base_url", "")
        except (json.JSONDecodeError, OSError):
            pass

    # Detect config_dir from existing memory/auth scripts
    for py_file in (skill_path / "scripts").glob("*.py"):
        try:
            content = py_file.read_text(errors="ignore")
            # Look for config dir patterns
            match = re.search(r'["\']\.config["\']\s*/\s*["\']([^"\']+)["\']', content)
            if not match:
                match = re.search(r'/ "([^"]+)"', content)
            if match:
                info["config_dir"] = match.group(1)
                break
        except OSError:
            pass

    return info


def _check_function_exists(content, func_name):
    """Check if a function definition exists in Python source."""
    return bool(re.search(rf'^def {func_name}\s*\(', content, re.MULTILINE))


def _check_section_exists(content, section_title):
    """Check if a markdown section exists."""
    return bool(re.search(rf'^#{1,4}\s+.*{re.escape(section_title)}', content, re.MULTILINE))


def analyze_gaps(skill_path):
    """Analyze what's missing from the skill compared to canonical templates.

    Returns list of gaps with recommended patches.
    """
    skill_path = Path(skill_path).resolve()
    info = _detect_service_info(skill_path)
    prefix = info["prefix"]
    gaps = []

    # Check *_memory.py
    memory_file = skill_path / "scripts" / f"{prefix}_memory.py"
    if not memory_file.exists():
        gaps.append({
            "file": str(memory_file),
            "type": "missing_file",
            "tom": 2,
            "description": f"Missing {prefix}_memory.py (dual memory)",
            "action": "generate_from_template",
            "template": "memory",
        })
    else:
        content = memory_file.read_text(errors="ignore")
        required_funcs = [
            "_get_config_dir", "_get_credentials_path", "_load_sensitive_patterns",
            "_sanitize_text", "_load_store", "_save_store", "load_memory",
            "save_memory", "load_private_memory", "save_private_memory",
            "_score_entries", "check_memory", "_next_id", "record_entry",
        ]
        for func in required_funcs:
            if not _check_function_exists(content, func):
                gaps.append({
                    "file": str(memory_file),
                    "type": "missing_function",
                    "tom": 2,
                    "description": f"Missing function {func}() in {prefix}_memory.py",
                    "action": "add_function",
                    "function": func,
                })
        # Check PRIVATE_MEMORY_PATH
        if "PRIVATE_MEMORY_PATH" not in content:
            gaps.append({
                "file": str(memory_file),
                "type": "missing_constant",
                "tom": 2,
                "description": "Missing PRIVATE_MEMORY_PATH constant",
                "action": "add_constant",
            })

    # Check *_auth.py
    auth_file = skill_path / "scripts" / f"{prefix}_auth.py"
    if not auth_file.exists():
        gaps.append({
            "file": str(auth_file),
            "type": "missing_file",
            "tom": 3,
            "description": f"Missing {prefix}_auth.py (credential management)",
            "action": "generate_from_template",
            "template": "auth",
        })
    else:
        content = auth_file.read_text(errors="ignore")
        if "check-credentials" not in content and "check_credentials" not in content:
            gaps.append({
                "file": str(auth_file),
                "type": "missing_command",
                "tom": 3,
                "description": "Missing check-credentials command in auth script",
                "action": "add_command",
            })
        if "setup_hint" not in content:
            gaps.append({
                "file": str(auth_file),
                "type": "missing_feature",
                "tom": 3,
                "description": "Missing setup_hint in check-credentials response",
                "action": "add_setup_hint",
            })
        if "chmod" not in content and "S_IRUSR" not in content:
            gaps.append({
                "file": str(auth_file),
                "type": "missing_feature",
                "tom": 1,
                "description": "Missing chmod 600 on credential save",
                "action": "add_chmod",
            })

    # Check config/config.json
    config_file = skill_path / "config" / "config.json"
    if not config_file.exists():
        gaps.append({
            "file": str(config_file),
            "type": "missing_file",
            "tom": 6,
            "description": "Missing config/config.json",
            "action": "generate_from_template",
            "template": "config",
        })
    else:
        try:
            with open(config_file) as f:
                cfg = json.load(f)
            # Check for secrets in config
            for key in ("token", "access_token", "client_secret", "org_id", "api_key"):
                if key in cfg:
                    gaps.append({
                        "file": str(config_file),
                        "type": "secret_in_config",
                        "tom": 1,
                        "description": f"Secret field '{key}' found in config.json — must be in ~/.config/",
                        "action": "remove_secret",
                        "field": key,
                    })
        except (json.JSONDecodeError, OSError):
            gaps.append({
                "file": str(config_file),
                "type": "invalid_json",
                "tom": 7,
                "description": "config.json is not valid JSON",
                "action": "fix_json",
            })

    # Check data/memory.json
    memory_data = skill_path / "data" / "memory.json"
    if not memory_data.exists():
        gaps.append({
            "file": str(memory_data),
            "type": "missing_file",
            "tom": 2,
            "description": "Missing data/memory.json (shared memory store)",
            "action": "create_empty",
        })

    # Check SKILL.md
    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(errors="ignore")
        if not _check_section_exists(content, "Безопасность"):
            gaps.append({
                "file": str(skill_md),
                "type": "missing_section",
                "tom": 1,
                "description": "Missing security section in SKILL.md",
                "action": "add_section",
                "section": "security",
            })
        if not _check_section_exists(content, "двойная память") and not _check_section_exists(content, "Разделение данных"):
            gaps.append({
                "file": str(skill_md),
                "type": "missing_section",
                "tom": 2,
                "description": "Missing dual memory section in SKILL.md",
                "action": "add_section",
                "section": "dual_memory",
            })
        if "check-credentials" not in content:
            gaps.append({
                "file": str(skill_md),
                "type": "missing_step",
                "tom": 3,
                "description": "Missing Step 0 (check-credentials) in SKILL.md",
                "action": "add_section",
                "section": "step0",
            })
    else:
        gaps.append({
            "file": str(skill_md),
            "type": "missing_file",
            "tom": 6,
            "description": "Missing SKILL.md",
            "action": "create_skill_md",
        })

    return {"service_info": info, "gaps": gaps, "total_gaps": len(gaps)}


def generate_file(template_name, info):
    """Generate a complete file from a template using service info."""
    sensitive_exact = ", ".join(f'"{f}"' for f in info.get("sensitive_exact_fields", ["access_token", "client_id", "client_secret"]))
    sensitive_regex = info.get("sensitive_regex_patterns", "")
    if not sensitive_regex:
        sensitive_regex = "    # Add service-specific regex patterns here\n    # patterns.append((re.compile(r'pattern'), 'replacement'))"

    setup_hint = info.get("setup_hint", "")
    if not setup_hint:
        setup_hint = (
            '            "Credentials not found. Please configure the service:\\n"\n'
            '            "1. Obtain API credentials from the service\\n"\n'
            f'            "2. Run: python3 {info.get("prefix", "xx")}_auth.py save-token --field token --value <TOKEN>"'
        )

    params = {
        "SERVICE_NAME": info.get("service_name", "service"),
        "CONFIG_DIR": info.get("config_dir", info.get("service_name", "service")),
        "PREFIX": info.get("prefix", "xx"),
        "SENSITIVE_EXACT_FIELDS": sensitive_exact,
        "SENSITIVE_REGEX_PATTERNS": sensitive_regex,
        "SETUP_HINT_TEXT": setup_hint,
        "BASE_URL": info.get("base_url", "https://api.example.com"),
    }

    templates = {
        "memory": MEMORY_TEMPLATE,
        "auth": AUTH_TEMPLATE,
        "config": CONFIG_TEMPLATE,
    }

    tpl = templates.get(template_name)
    if not tpl:
        return None

    return tpl.safe_substitute(params)


def generate_section(section_name, info):
    """Generate a SKILL.md section from template."""
    params = {
        "PREFIX": info.get("prefix", "xx"),
        "CONFIG_DIR": info.get("config_dir", info.get("service_name", "service")),
    }

    sections = {
        "security": SECURITY_SECTION_TEMPLATE,
        "dual_memory": DUAL_MEMORY_SECTION_TEMPLATE,
        "step0": STEP0_SECTION_TEMPLATE,
    }

    tpl = sections.get(section_name)
    if not tpl:
        return None

    return tpl.safe_substitute(params)


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(0 if obj.get("ok") else 1)


def main():
    parser = argparse.ArgumentParser(description="Skill template analyzer and generator")
    sub = parser.add_subparsers(dest="command")

    p_gaps = sub.add_parser("analyze-gaps", help="Analyze gaps in a skill")
    p_gaps.add_argument("target", help="Path to skill directory")

    p_gen = sub.add_parser("generate", help="Generate a file from template")
    p_gen.add_argument("template", choices=["memory", "auth", "config"],
                       help="Template to generate")
    p_gen.add_argument("target", help="Path to skill directory (for auto-detection)")
    p_gen.add_argument("--output", help="Output file path (default: stdout)")

    p_section = sub.add_parser("section", help="Generate a SKILL.md section")
    p_section.add_argument("section", choices=["security", "dual_memory", "step0"])
    p_section.add_argument("target", help="Path to skill directory (for auto-detection)")

    args = parser.parse_args()

    if args.command == "analyze-gaps":
        result = analyze_gaps(args.target)
        out({"ok": True, "data": result})
    elif args.command == "generate":
        info = _detect_service_info(args.target)
        content = generate_file(args.template, info)
        if content is None:
            out({"ok": False, "error": f"Unknown template: {args.template}"})
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(content)
            out({"ok": True, "data": {"file": args.output, "size": len(content)}})
        else:
            print(content)
    elif args.command == "section":
        info = _detect_service_info(args.target)
        content = generate_section(args.section, info)
        if content is None:
            out({"ok": False, "error": f"Unknown section: {args.section}"})
        print(content)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
