#!/usr/bin/env python3
"""Deep analysis for skill-security meta-skill.

Two modes:
  deep-understand <skill_path>  — A1: static analysis + wizard blueprint
  audit <skill_path>            — A:  full 7-volume checklist audit
"""

import argparse
import ast
import glob as glob_mod
import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from ss_security import scan as security_scan


def _load_checklist():
    checklist_path = SKILL_ROOT / "data" / "checklist.json"
    try:
        with open(checklist_path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"toms": []}


# ═══════════════════════════════════════════════════════════════
# Phase A1: Deep Skill Understanding
# ═══════════════════════════════════════════════════════════════

def _scan_python_files(scripts_dir):
    """Extract HTTP calls, base URLs, endpoints, imports from Python files."""
    results = {
        "http_calls": [],
        "base_urls": [],
        "endpoints": [],
        "imports": [],
        "auth_patterns": [],
    }

    for py_file in scripts_dir.glob("*.py"):
        try:
            content = py_file.read_text(errors="ignore")
        except OSError:
            continue

        # Find HTTP method calls
        for match in re.finditer(r'requests?\.(get|post|put|patch|delete)\s*\(\s*["\']?([^"\')\s,]+)', content):
            results["http_calls"].append({
                "file": py_file.name,
                "method": match.group(1).upper(),
                "url_fragment": match.group(2)[:100],
            })

        # Find base URLs
        for match in re.finditer(r'(?:base_url|BASE_URL|api_url)\s*[:=]\s*["\']([^"\']+)["\']', content):
            url = match.group(1)
            if url not in results["base_urls"]:
                results["base_urls"].append(url)

        # Find endpoint patterns
        for match in re.finditer(r'["\']/(v\d+/[^"\']+)["\']', content):
            ep = match.group(1)
            if ep not in results["endpoints"]:
                results["endpoints"].append(ep)

        # Find imports
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        results["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        results["imports"].append(node.module)
        except SyntaxError:
            pass

        # Find auth patterns
        if "_auth" in py_file.name or "auth" in py_file.name:
            results["auth_patterns"].append(py_file.name)
            if "oauth" in content.lower():
                results["auth_patterns"].append("oauth2_detected")
            if "bearer" in content.lower():
                results["auth_patterns"].append("bearer_token_detected")
            if "api_key" in content.lower() or "api-key" in content.lower():
                results["auth_patterns"].append("api_key_detected")

    results["imports"] = list(set(results["imports"]))
    results["auth_patterns"] = list(set(results["auth_patterns"]))
    return results


def _parse_skill_md(skill_path):
    """Parse SKILL.md for description, triggers, mentioned APIs."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return {"exists": False}

    content = skill_md.read_text(errors="ignore")
    result = {"exists": True, "sections": []}

    # Extract frontmatter
    fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        for line in fm.split("\n"):
            if ":" in line:
                key, _, val = line.partition(":")
                result[key.strip()] = val.strip()

    # Extract section headers
    for match in re.finditer(r'^(#{1,4})\s+(.+)$', content, re.MULTILINE):
        result["sections"].append({
            "level": len(match.group(1)),
            "title": match.group(2).strip(),
        })

    # Check for key sections
    content_lower = content.lower()
    result["has_security_section"] = "безопасность" in content_lower or "security" in content_lower
    result["has_dual_memory_section"] = "двойная память" in content_lower or "dual memory" in content_lower or "разделение данных" in content_lower
    result["has_step0"] = "check-credentials" in content
    result["has_check_memory"] = "check_memory" in content or "check memory" in content_lower

    return result


def _parse_config(skill_path):
    """Parse config/config.json."""
    config_path = skill_path / "config" / "config.json"
    if not config_path.exists():
        return {"exists": False}

    try:
        with open(config_path) as f:
            cfg = json.load(f)
        return {"exists": True, **cfg}
    except (json.JSONDecodeError, OSError):
        return {"exists": True, "parse_error": True}


def _find_credential_fields(skill_path):
    """Find what credential fields are used in the skill."""
    fields = set()
    for py_file in (skill_path / "scripts").glob("*.py"):
        try:
            content = py_file.read_text(errors="ignore")
        except OSError:
            continue

        # Look for credential field access patterns
        for match in re.finditer(r'creds?(?:\.get|\[)["\'](\w+)["\']', content):
            fields.add(match.group(1))
        for match in re.finditer(r'(?:save|load)_credentials|credentials_exist', content):
            fields.add("_has_credential_management")

    return list(fields)


def deep_understand(skill_path):
    """Phase A1: Deep skill understanding — static analysis.

    Returns service profile and wizard blueprint.
    """
    skill_path = Path(skill_path).resolve()
    if not skill_path.is_dir():
        return {"ok": False, "error": f"Not a directory: {skill_path}", "error_type": "bad_request"}

    scripts_dir = skill_path / "scripts"
    if not scripts_dir.exists():
        scripts_dir = skill_path  # fallback

    # Step 1: Static analysis
    code_analysis = _scan_python_files(scripts_dir)
    skill_md_info = _parse_skill_md(skill_path)
    config_info = _parse_config(skill_path)
    credential_fields = _find_credential_fields(skill_path)

    # Determine service info
    service_name = skill_path.name
    base_url = ""
    if code_analysis["base_urls"]:
        base_url = code_analysis["base_urls"][0]
    elif config_info.get("base_url"):
        base_url = config_info["base_url"]

    # Determine auth type
    auth_type = "unknown"
    if "oauth2_detected" in code_analysis["auth_patterns"]:
        auth_type = "oauth2"
    elif "bearer_token_detected" in code_analysis["auth_patterns"]:
        auth_type = "token"
    elif "api_key_detected" in code_analysis["auth_patterns"]:
        auth_type = "api_key"

    # Build existing auth coverage
    auth_files = [f for f in code_analysis["auth_patterns"]
                  if f.endswith(".py")]

    # Build wizard blueprint
    wizard_steps = []
    if not auth_files:
        wizard_steps.append({"step": 1, "action": "create_auth_script"})

    wizard_steps.append({"step": len(wizard_steps) + 1, "action": "go_to_docs",
                          "hint": f"Find API documentation for {service_name}"})

    for field in credential_fields:
        if field != "_has_credential_management" and field not in ("get", "items"):
            wizard_steps.append({
                "step": len(wizard_steps) + 1,
                "action": "collect",
                "field": field,
            })

    profile = {
        "service_name": service_name,
        "base_url": base_url,
        "auth_type": auth_type,
        "existing_credential_fields": credential_fields,
        "endpoints_found": code_analysis["endpoints"][:20],
        "http_methods_used": list(set(c["method"] for c in code_analysis["http_calls"])),
        "auth_files": auth_files,
        "skill_md": skill_md_info,
        "config": config_info,
        "wizard_blueprint": {
            "service_name": service_name,
            "auth_type": auth_type,
            "required_credentials": [f for f in credential_fields if f != "_has_credential_management"],
            "wizard_steps": wizard_steps,
        },
    }

    return {"ok": True, "data": profile}


# ═══════════════════════════════════════════════════════════════
# Phase A: Deep Audit
# ═══════════════════════════════════════════════════════════════

def _check_tom1(skill_path, prefix):
    """Tom 1: Security — credential isolation, no secrets in package."""
    items = []

    # §1.1.1.1 — Credentials stored ONLY in ~/.config/
    auth_file = skill_path / "scripts" / f"{prefix}_auth.py"
    if auth_file.exists():
        content = auth_file.read_text(errors="ignore")
        if ".config" in content or "APPDATA" in content:
            items.append({"id": "1.1.1.1.§1", "status": "PASS", "description": "Credentials path uses ~/.config/"})
        else:
            items.append({"id": "1.1.1.1.§1", "status": "FAIL", "description": "Credentials not stored in ~/.config/"})
    else:
        items.append({"id": "1.1.1.1.§1", "status": "FAIL", "description": f"No {prefix}_auth.py found"})

    # §1.1.1.1.§3 — Platform-aware path
    for py_file in (skill_path / "scripts").glob("*.py"):
        content = py_file.read_text(errors="ignore")
        if "sys.platform" in content and ("win32" in content or "APPDATA" in content):
            items.append({"id": "1.1.1.1.§3", "status": "PASS", "description": "Platform-aware credential path"})
            break
    else:
        items.append({"id": "1.1.1.1.§3", "status": "WARN", "description": "No platform-aware path detection found"})

    # §1.1.1.1.2.§1 — chmod 600
    found_chmod = False
    for py_file in (skill_path / "scripts").glob("*.py"):
        content = py_file.read_text(errors="ignore")
        if "chmod" in content or "S_IRUSR" in content:
            found_chmod = True
            break
    items.append({
        "id": "1.1.1.1.2.§1",
        "status": "PASS" if found_chmod else "FAIL",
        "description": "chmod 600 on credential save" if found_chmod else "Missing chmod 600 on credential save",
    })

    # §1.1.1.2 — No secrets in package (delegate to ss_security.py)
    scan_result = security_scan(str(skill_path))
    if scan_result.get("ok"):
        data = scan_result["data"]
        if data["critical"] == 0:
            items.append({"id": "1.1.1.2.§1-7", "status": "PASS",
                          "description": "No secrets found in package"})
        else:
            for f in data.get("findings", []):
                if f["severity"] == "CRITICAL":
                    items.append({"id": "1.1.1.2", "status": "FAIL",
                                  "description": f["description"],
                                  "file": f["file"], "line": f["line"]})

    # §1.1.2.1 — check-credentials format
    if auth_file.exists():
        content = auth_file.read_text(errors="ignore")
        has_check = "check-credentials" in content or "check_credentials" in content
        has_exists = '"exists"' in content
        has_setup_hint = "setup_hint" in content
        has_no_read = True  # assume ok unless we find evidence of reading
        if "json.load" in content and "credentials" in content:
            # Check if it reads credentials content (not just existence check)
            if re.search(r'with open.*credentials.*json\.load', content, re.DOTALL):
                has_no_read = True  # it's ok to load internally

        items.append({"id": "1.1.2.1.§1-3", "status": "PASS" if (has_check and has_exists) else "FAIL",
                       "description": "check-credentials returns {ok, data: {exists}}"})
        items.append({"id": "1.1.2.2.§1", "status": "PASS" if has_setup_hint else "FAIL",
                       "description": "setup_hint present in check-credentials"})

    # §1.1.3 — SKILL.md security section
    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(errors="ignore")
        has_security = "безопасность" in content.lower() or "security" in content.lower()
        has_no_read_rule = "запрещено" in content.lower() or "never read" in content.lower() or "никогда" in content.lower()
        items.append({"id": "1.1.3.1.§1-4", "status": "PASS" if (has_security and has_no_read_rule) else "FAIL",
                       "description": "SKILL.md has security section with explicit restrictions"})

    return items


def _check_tom2(skill_path, prefix):
    """Tom 2: Dual Memory architecture."""
    items = []

    memory_file = skill_path / "scripts" / f"{prefix}_memory.py"
    if not memory_file.exists():
        items.append({"id": "2.1", "status": "FAIL", "description": f"Missing {prefix}_memory.py"})
        return items

    content = memory_file.read_text(errors="ignore")

    # §2.1.1.1 — Shared memory path
    has_memory_path = "MEMORY_PATH" in content and "data" in content and "memory.json" in content
    items.append({"id": "2.1.1.1.§1-5", "status": "PASS" if has_memory_path else "FAIL",
                   "description": "MEMORY_PATH → data/memory.json"})

    # §2.1.1.2 — Private memory path
    has_private = "PRIVATE_MEMORY_PATH" in content and ".config" in content
    items.append({"id": "2.1.1.2.§1-5", "status": "PASS" if has_private else "FAIL",
                   "description": "PRIVATE_MEMORY_PATH → ~/.config/.../memory.json"})

    # §2.1.2.1 — check_memory loads BOTH
    func_match = re.search(r'def check_memory\(.*?\n(?:.*\n)*?(?=\ndef |\Z)', content)
    if func_match:
        func_body = func_match.group()
        loads_shared = "load_memory" in func_body or "shared" in func_body
        loads_private = "load_private_memory" in func_body or "private" in func_body
        items.append({"id": "2.1.2.1.§1-4", "status": "PASS" if (loads_shared and loads_private) else "FAIL",
                       "description": "check_memory() searches BOTH stores"})
    else:
        items.append({"id": "2.1.2.1.§1-4", "status": "FAIL", "description": "check_memory() not found"})

    # §2.1.2.2 — Scoring algorithm
    has_tag_score = "+2" in content or "+ 2" in content
    has_problem_score = "+1" in content or "+ 1" in content
    has_solution_score = "+0.5" in content or "+ 0.5" in content
    items.append({"id": "2.1.2.2.§1-4", "status": "PASS" if (has_tag_score and has_problem_score and has_solution_score) else "WARN",
                   "description": "Scoring: +2 tag, +1 problem, +0.5 solution"})

    # §2.1.3 — record_entry with private param
    has_record = "def record_entry" in content
    has_private_param = "private=False" in content or "private=" in content
    has_sanitize_in_record = "_sanitize_text" in content
    items.append({"id": "2.1.3.1.§1-5", "status": "PASS" if (has_record and has_private_param and has_sanitize_in_record) else "FAIL",
                   "description": "record_entry(private=False) with sanitization"})

    # §2.1.4 — _sanitize_text exists
    has_sanitize = "def _sanitize_text" in content
    has_load_patterns = "def _load_sensitive_patterns" in content
    items.append({"id": "2.1.4.1-3", "status": "PASS" if (has_sanitize and has_load_patterns) else "FAIL",
                   "description": "_sanitize_text + _load_sensitive_patterns"})

    # §2.1.5 — CLI
    has_cli_check = '"check"' in content
    has_cli_record = '"record"' in content
    has_cli_list = '"list"' in content
    has_private_flag = '"--private"' in content or "'--private'" in content
    items.append({"id": "2.1.5.1-3", "status": "PASS" if (has_cli_check and has_cli_record and has_cli_list and has_private_flag) else "FAIL",
                   "description": "CLI: check, record (--private), list (--private)"})

    # §2.1.3.3.§1 — Entry structure
    has_id = '"id"' in content
    has_timestamp = '"timestamp"' in content
    has_category = '"category"' in content
    has_hit_count = '"hit_count"' in content
    items.append({"id": "2.1.3.3.§1", "status": "PASS" if (has_id and has_timestamp and has_category and has_hit_count) else "FAIL",
                   "description": "Entry fields: id, timestamp, category, hit_count"})

    return items


def _check_tom3(skill_path, prefix):
    """Tom 3: First-Install UX."""
    items = []

    # Check auth script has check-credentials + setup_hint
    auth_file = skill_path / "scripts" / f"{prefix}_auth.py"
    if auth_file.exists():
        content = auth_file.read_text(errors="ignore")
        has_check = "check-credentials" in content or "check_credentials" in content
        has_hint = "setup_hint" in content
        items.append({"id": "3.1.1.1.§1-4", "status": "PASS" if (has_check and has_hint) else "FAIL",
                       "description": "Auth script: check-credentials with setup_hint"})
        has_save = "save-token" in content or "save_token" in content
        items.append({"id": "3.1.1.2.§3", "status": "PASS" if has_save else "FAIL",
                       "description": "Auth script: save-token command"})
    else:
        items.append({"id": "3.1.1", "status": "FAIL", "description": f"No {prefix}_auth.py found"})

    # Check SKILL.md has Step 0
    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(errors="ignore")
        has_step0 = "check-credentials" in content
        items.append({"id": "3.1.1.1.§1-2", "status": "PASS" if has_step0 else "FAIL",
                       "description": "SKILL.md has Step 0 (check-credentials)"})

    return items


def _check_tom4(skill_path, prefix):
    """Tom 4: Caches and data isolation."""
    items = []

    # Check that caches are in ~/.config/
    data_dir = skill_path / "data"
    if data_dir.exists():
        for f in data_dir.iterdir():
            if f.name == "memory.json":
                continue
            if f.is_file() and f.suffix == ".json":
                try:
                    content = f.read_text()
                    data = json.loads(content)
                    if isinstance(data, dict) and len(data) > 2:
                        items.append({"id": "4.1.1.§3", "status": "WARN",
                                       "description": f"data/{f.name} contains data (should be placeholder)",
                                       "file": str(f)})
                    elif content.strip() in ("{}", "[]", ""):
                        items.append({"id": "4.1.1.§3", "status": "PASS",
                                       "description": f"data/{f.name} is a placeholder"})
                except (json.JSONDecodeError, OSError):
                    pass

    # Check code uses ~/.config/ paths for caches
    found_cache_in_config = False
    for py_file in (skill_path / "scripts").glob("*.py"):
        try:
            content = py_file.read_text(errors="ignore")
            if "CACHE_PATH" in content and ".config" in content:
                found_cache_in_config = True
                break
        except OSError:
            pass

    if found_cache_in_config:
        items.append({"id": "4.1.2.§1-3", "status": "PASS", "description": "Cache paths use ~/.config/"})

    if not items:
        items.append({"id": "4.1", "status": "PASS", "description": "No cache issues detected"})

    return items


def _check_tom5(skill_path, prefix):
    """Tom 5: Shareability — no personal data in package."""
    items = []

    # Delegate to security scanner
    scan_result = security_scan(str(skill_path))
    if scan_result.get("ok"):
        data = scan_result["data"]
        personal_findings = [f for f in data.get("findings", [])
                            if f.get("tom") == 5]
        if not personal_findings:
            items.append({"id": "5.1.1-2", "status": "PASS", "description": "No personal data found in package"})
        else:
            for f in personal_findings[:5]:
                items.append({"id": "5.1.2", "status": "FAIL",
                               "description": f["description"],
                               "file": f["file"], "line": f["line"]})

    # Check no hardcoded profiles/choices
    for py_file in (skill_path / "scripts").glob("*.py"):
        try:
            content = py_file.read_text(errors="ignore")
            if re.search(r'choices\s*=\s*\[', content):
                items.append({"id": "5.1.3.§1", "status": "WARN",
                               "description": f"Hardcoded choices= in {py_file.name}",
                               "file": str(py_file)})
        except OSError:
            pass

    if not items:
        items.append({"id": "5.1", "status": "PASS", "description": "Package is shareable"})

    return items


def _check_tom6(skill_path, prefix):
    """Tom 6: Architectural uniformity."""
    items = []

    # §6.1.1 — Required files
    required = {
        f"{prefix}_api.py": "HTTP client",
        f"{prefix}_auth.py": "Credential management",
        f"{prefix}_memory.py": "Dual memory",
    }
    scripts_dir = skill_path / "scripts"
    for filename, desc in required.items():
        exists = (scripts_dir / filename).exists()
        items.append({
            "id": "6.1.1",
            "status": "PASS" if exists else "FAIL",
            "description": f"{filename} ({desc})" if exists else f"Missing {filename} ({desc})",
        })

    # config.json
    config_exists = (skill_path / "config" / "config.json").exists()
    items.append({"id": "6.1.1.§4", "status": "PASS" if config_exists else "FAIL",
                   "description": "config/config.json exists"})

    # SKILL.md
    skill_md_exists = (skill_path / "SKILL.md").exists()
    items.append({"id": "6.1.1.§5", "status": "PASS" if skill_md_exists else "FAIL",
                   "description": "SKILL.md exists"})

    # §6.1.3 — JSON output format
    for py_file in scripts_dir.glob("*.py"):
        try:
            content = py_file.read_text(errors="ignore")
            if '"ok"' in content and '"data"' in content:
                items.append({"id": "6.1.3.§1", "status": "PASS",
                               "description": f"JSON output format in {py_file.name}"})
                break
        except OSError:
            pass

    # §6.1.4 — Retry
    found_retry = False
    for py_file in scripts_dir.glob("*.py"):
        try:
            content = py_file.read_text(errors="ignore")
            if "RETRY_DELAYS" in content or "retry" in content.lower():
                found_retry = True
                break
        except OSError:
            pass
    items.append({"id": "6.1.4.§1-4", "status": "PASS" if found_retry else "WARN",
                   "description": "Retry mechanism" if found_retry else "No retry mechanism found"})

    return items


def _check_tom7(skill_path, prefix):
    """Tom 7: Functional correctness."""
    items = []

    scripts_dir = skill_path / "scripts"
    if not scripts_dir.exists():
        items.append({"id": "7.1", "status": "FAIL", "description": "No scripts/ directory"})
        return items

    # §7.1.1 — Syntax check
    for py_file in scripts_dir.glob("*.py"):
        try:
            content = py_file.read_text(errors="ignore")
            compile(content, str(py_file), "exec")
            items.append({"id": "7.1.1.§1", "status": "PASS",
                           "description": f"Valid Python: {py_file.name}"})
        except SyntaxError as e:
            items.append({"id": "7.1.1.§1", "status": "FAIL",
                           "description": f"Syntax error in {py_file.name}: {e}",
                           "file": str(py_file), "line": e.lineno})

    # §7.1.4 — __pycache__
    pycache_dirs = list(skill_path.rglob("__pycache__"))
    if pycache_dirs:
        items.append({"id": "7.1.4.§1", "status": "FAIL",
                       "description": f"__pycache__ found: {len(pycache_dirs)} dirs"})
    else:
        items.append({"id": "7.1.4.§1", "status": "PASS", "description": "No __pycache__ dirs"})

    # §7.1.3 — record_entry has private param
    memory_file = scripts_dir / f"{prefix}_memory.py"
    if memory_file.exists():
        content = memory_file.read_text(errors="ignore")
        if "private=False" in content:
            items.append({"id": "7.1.3.§2", "status": "PASS",
                           "description": "record_entry has private=False parameter"})
        elif "private=" in content:
            items.append({"id": "7.1.3.§2", "status": "PASS",
                           "description": "record_entry has private parameter"})
        else:
            items.append({"id": "7.1.3.§2", "status": "FAIL",
                           "description": "record_entry missing private parameter"})

    return items


def _detect_prefix(skill_path):
    """Detect the 2-letter prefix used by skill scripts."""
    scripts_dir = skill_path / "scripts"
    if not scripts_dir.exists():
        return skill_path.name[:2]

    for py_file in scripts_dir.glob("*_api.py"):
        return py_file.stem.split("_")[0]
    for py_file in scripts_dir.glob("*_memory.py"):
        return py_file.stem.split("_")[0]
    for py_file in scripts_dir.glob("*_auth.py"):
        return py_file.stem.split("_")[0]

    return skill_path.name[:2]


def audit(skill_path):
    """Phase A: Full 7-volume audit.

    Returns JSON report with per-tom results.
    """
    skill_path = Path(skill_path).resolve()
    if not skill_path.is_dir():
        return {"ok": False, "error": f"Not a directory: {skill_path}", "error_type": "bad_request"}

    prefix = _detect_prefix(skill_path)

    report = {}
    check_functions = {
        "tom_1": (_check_tom1, "Безопасность"),
        "tom_2": (_check_tom2, "Dual Memory"),
        "tom_3": (_check_tom3, "First-Install UX"),
        "tom_4": (_check_tom4, "Кеши и данные"),
        "tom_5": (_check_tom5, "Shareability"),
        "tom_6": (_check_tom6, "Архитектура"),
        "tom_7": (_check_tom7, "Код"),
    }

    total_pass = 0
    total_fail = 0
    total_warn = 0

    for tom_key, (check_fn, tom_name) in check_functions.items():
        items = check_fn(skill_path, prefix)
        passes = sum(1 for i in items if i["status"] == "PASS")
        fails = sum(1 for i in items if i["status"] == "FAIL")
        warns = sum(1 for i in items if i["status"] == "WARN")

        total_pass += passes
        total_fail += fails
        total_warn += warns

        if fails > 0:
            status = "FAIL"
        elif warns > 0:
            status = "WARN"
        else:
            status = "PASS"

        report[tom_key] = {
            "name": tom_name,
            "status": status,
            "pass": passes,
            "fail": fails,
            "warn": warns,
            "items": items,
        }

    return {
        "ok": True,
        "data": {
            "target": str(skill_path),
            "prefix": prefix,
            "summary": {
                "total_items": total_pass + total_fail + total_warn,
                "pass": total_pass,
                "fail": total_fail,
                "warn": total_warn,
                "overall": "FAIL" if total_fail > 0 else ("WARN" if total_warn > 0 else "PASS"),
            },
            "toms": report,
        },
    }


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(0 if obj.get("ok") else 1)


def main():
    parser = argparse.ArgumentParser(description="Skill deep analysis and audit")
    sub = parser.add_subparsers(dest="command")

    p_understand = sub.add_parser("deep-understand",
                                  help="A1: Deep skill understanding (static analysis)")
    p_understand.add_argument("target", help="Path to skill directory")

    p_audit = sub.add_parser("audit", help="A: Full 7-volume audit")
    p_audit.add_argument("target", help="Path to skill directory")

    args = parser.parse_args()

    if args.command == "deep-understand":
        result = deep_understand(args.target)
        out(result)
    elif args.command == "audit":
        result = audit(args.target)
        out(result)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
