#!/usr/bin/env python3
"""Secret scanner for skill-security meta-skill.

Scans a target skill directory for:
- Hardcoded tokens and credentials
- Personal data (emails, names, org IDs)
- .env files and credential files
- Real project data that shouldn't be shared
"""

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_ROOT / "config" / "config.json"


def _load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _compile_patterns(config):
    """Compile token and personal data regex patterns from config."""
    patterns = []
    for p in config.get("known_token_patterns", []):
        try:
            patterns.append({
                "name": p["name"],
                "regex": re.compile(p["regex"]),
                "severity": "CRITICAL",
                "tom": 1,
            })
        except re.error:
            pass

    for p in config.get("personal_data_patterns", []):
        try:
            patterns.append({
                "name": p["name"],
                "regex": re.compile(p["regex"]),
                "severity": "HIGH",
                "tom": 5,
            })
        except re.error:
            pass

    return patterns


def _should_scan(filepath):
    """Decide if a file should be scanned."""
    skip_dirs = {"__pycache__", ".git", "node_modules", ".venv", "venv"}
    for part in filepath.parts:
        if part in skip_dirs:
            return False

    skip_suffixes = {".pyc", ".pyo", ".so", ".dll", ".exe", ".bin",
                     ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
                     ".woff", ".woff2", ".ttf", ".eot"}
    if filepath.suffix.lower() in skip_suffixes:
        return False

    return True


def _is_placeholder(line, match_text):
    """Check if a match is a placeholder/documentation rather than a real secret."""
    line_lower = line.lower()
    placeholder_markers = [
        "placeholder", "example", "xxx", "your_", "<your",
        "regex", "pattern", "re.compile", "r'", 'r"',
        "# ", "comment", "documentation", "template",
        "setup_hint", "instructions", "replace with",
    ]
    for marker in placeholder_markers:
        if marker in line_lower:
            return True
    # Check if inside a regex string (common in security scanners themselves)
    if "re.compile" in line or "regex" in line_lower:
        return True
    return False


def scan(target_path, verbose=False):
    """Scan a skill directory for secrets and personal data.

    Returns:
        dict with findings grouped by severity
    """
    target = Path(target_path).resolve()
    if not target.is_dir():
        return {"ok": False, "error": f"Not a directory: {target}", "error_type": "bad_request"}

    config = _load_config()
    patterns = _compile_patterns(config)

    findings = []

    # 1. Check for credential/env files in package
    dangerous_files = [
        "credentials.json", ".env", ".env.local", ".env.production",
        "*.token", "*.key", "*.pem", ".oauth_state",
    ]
    for pattern in dangerous_files:
        for fp in target.rglob(pattern):
            if _should_scan(fp):
                findings.append({
                    "file": str(fp),
                    "line": 0,
                    "pattern": "dangerous_file",
                    "match": fp.name,
                    "severity": "CRITICAL",
                    "tom": 1,
                    "description": f"Credential/secret file found in package: {fp.name}",
                })

    # 2. Scan file contents
    for fp in target.rglob("*"):
        if not fp.is_file() or not _should_scan(fp):
            continue

        try:
            content = fp.read_text(errors="ignore")
        except (OSError, PermissionError):
            continue

        lines = content.split("\n")
        for line_num, line in enumerate(lines, 1):
            for pat in patterns:
                for match in pat["regex"].finditer(line):
                    match_text = match.group()
                    if _is_placeholder(line, match_text):
                        continue
                    findings.append({
                        "file": str(fp),
                        "line": line_num,
                        "pattern": pat["name"],
                        "match": match_text[:50] + "..." if len(match_text) > 50 else match_text,
                        "severity": pat["severity"],
                        "tom": pat["tom"],
                        "description": f"Pattern '{pat['name']}' matched",
                    })

    # 3. Check for __pycache__ directories
    for d in target.rglob("__pycache__"):
        if d.is_dir():
            findings.append({
                "file": str(d),
                "line": 0,
                "pattern": "pycache",
                "match": "__pycache__",
                "severity": "WARN",
                "tom": 7,
                "description": "__pycache__ directory should be removed from package",
            })

    # Deduplicate
    seen = set()
    unique = []
    for f in findings:
        key = (f["file"], f["line"], f["pattern"])
        if key not in seen:
            seen.add(key)
            unique.append(f)

    critical = [f for f in unique if f["severity"] == "CRITICAL"]
    high = [f for f in unique if f["severity"] == "HIGH"]
    warn = [f for f in unique if f["severity"] == "WARN"]

    return {
        "ok": True,
        "data": {
            "target": str(target),
            "total_findings": len(unique),
            "critical": len(critical),
            "high": len(high),
            "warn": len(warn),
            "findings": unique if verbose else unique[:20],
            "status": "FAIL" if critical else ("WARN" if high or warn else "PASS"),
        },
    }


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(0 if obj.get("ok") else 1)


def main():
    parser = argparse.ArgumentParser(description="Skill security scanner")
    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser("scan", help="Scan skill directory for secrets")
    p_scan.add_argument("target", help="Path to skill directory")
    p_scan.add_argument("--verbose", action="store_true", help="Show all findings")

    args = parser.parse_args()

    if args.command == "scan":
        result = scan(args.target, verbose=args.verbose)
        out(result)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
