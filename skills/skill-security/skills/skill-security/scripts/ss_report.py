#!/usr/bin/env python3
"""Report generator for skill-security meta-skill.

Converts JSON audit/validation reports to human-readable markdown.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent


def _status_icon(status):
    if status == "PASS":
        return "PASS"
    elif status == "FAIL":
        return "FAIL"
    elif status == "WARN":
        return "WARN"
    return "????"


def generate_audit_report(audit_data):
    """Generate markdown report from audit JSON data."""
    if not audit_data.get("ok"):
        return f"# Audit Failed\n\nError: {audit_data.get('error', 'Unknown')}\n"

    data = audit_data["data"]
    target = data["target"]
    summary = data["summary"]
    toms = data["toms"]

    lines = []
    lines.append(f"# Security Audit Report")
    lines.append(f"")
    lines.append(f"**Target:** `{target}`")
    lines.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Prefix:** `{data.get('prefix', '??')}`")
    lines.append(f"")
    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total checks | {summary['total_items']} |")
    lines.append(f"| PASS | {summary['pass']} |")
    lines.append(f"| FAIL | {summary['fail']} |")
    lines.append(f"| WARN | {summary['warn']} |")
    lines.append(f"| **Overall** | **{summary['overall']}** |")
    lines.append(f"")

    # Tom-by-tom table
    lines.append(f"## Results by Volume")
    lines.append(f"")
    lines.append(f"| # | Volume | Status | Pass | Fail | Warn |")
    lines.append(f"|---|--------|--------|------|------|------|")

    for i in range(1, 8):
        tom_key = f"tom_{i}"
        if tom_key in toms:
            tom = toms[tom_key]
            lines.append(
                f"| {i} | {tom['name']} | {_status_icon(tom['status'])} "
                f"| {tom['pass']} | {tom['fail']} | {tom['warn']} |"
            )
    lines.append(f"")

    # Details for FAIL/WARN items
    failures = []
    for tom_key, tom_data in toms.items():
        for item in tom_data["items"]:
            if item["status"] in ("FAIL", "WARN"):
                failures.append({
                    "tom": tom_key,
                    "tom_name": tom_data["name"],
                    **item,
                })

    if failures:
        lines.append(f"## Issues ({len(failures)})")
        lines.append(f"")
        for f in failures:
            status = _status_icon(f["status"])
            lines.append(f"- [{status}] **{f['tom_name']}** ({f.get('id', '')}) — {f['description']}")
            if f.get("file"):
                lines.append(f"  - File: `{f['file']}`" + (f" line {f['line']}" if f.get("line") else ""))
        lines.append(f"")

    if not failures:
        lines.append(f"## All checks passed!")
        lines.append(f"")

    return "\n".join(lines)


def generate_validation_report(validation_data):
    """Generate markdown report from validation JSON data."""
    if not validation_data.get("ok"):
        return f"# Validation Failed\n\nError: {validation_data.get('error', 'Unknown')}\n"

    data = validation_data["data"]
    target = data["target"]
    summary = data["summary"]

    lines = []
    lines.append(f"# Validation Report")
    lines.append(f"")
    lines.append(f"**Target:** `{target}`")
    lines.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"")
    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"- Total: {summary['total_items']}")
    lines.append(f"- PASS: {summary['pass']}")
    lines.append(f"- FAIL: {summary['fail']}")
    lines.append(f"- WARN: {summary['warn']}")
    lines.append(f"- **Overall: {summary['overall']}**")
    lines.append(f"")

    # Group by check type
    by_check = {}
    for item in data.get("items", []):
        check = item.get("check", "unknown")
        if check not in by_check:
            by_check[check] = []
        by_check[check].append(item)

    for check_name, items in by_check.items():
        passes = sum(1 for i in items if i["status"] == "PASS")
        fails = sum(1 for i in items if i["status"] == "FAIL")
        warns = sum(1 for i in items if i["status"] == "WARN")
        lines.append(f"### {check_name.title()} ({passes}P / {fails}F / {warns}W)")
        lines.append(f"")
        for item in items:
            if item["status"] in ("FAIL", "WARN"):
                lines.append(f"- [{_status_icon(item['status'])}] {item['description']}")
                if item.get("file"):
                    lines.append(f"  - `{item['file']}`" + (f":{item['line']}" if item.get("line") else ""))
        if not any(i["status"] in ("FAIL", "WARN") for i in items):
            lines.append(f"- All {passes} checks passed")
        lines.append(f"")

    return "\n".join(lines)


def generate_pipeline_report(pipeline_data):
    """Generate markdown report for full pipeline run."""
    lines = []
    lines.append(f"# Pipeline Report")
    lines.append(f"")
    lines.append(f"**Target:** `{pipeline_data.get('target', '?')}`")
    lines.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Rounds:** {pipeline_data.get('rounds', 0)}")
    lines.append(f"**Total fixes:** {pipeline_data.get('total_fixes', 0)}")
    lines.append(f"")

    if pipeline_data.get("understand"):
        u = pipeline_data["understand"]
        lines.append(f"## A1: Understanding")
        lines.append(f"- Service: {u.get('service_name', '?')}")
        lines.append(f"- Auth type: {u.get('auth_type', '?')}")
        lines.append(f"- Base URL: {u.get('base_url', '?')}")
        lines.append(f"")

    if pipeline_data.get("audit_summary"):
        s = pipeline_data["audit_summary"]
        lines.append(f"## A: Initial Audit")
        lines.append(f"- Pass: {s.get('pass', 0)} / Fail: {s.get('fail', 0)} / Warn: {s.get('warn', 0)}")
        lines.append(f"")

    if pipeline_data.get("rounds_log"):
        lines.append(f"## C/D: Correction Rounds")
        lines.append(f"")
        lines.append(f"| Round | Pass | Fail | Warn | Fixes |")
        lines.append(f"|-------|------|------|------|-------|")
        for r in pipeline_data["rounds_log"]:
            lines.append(f"| {r['round']} | {r['pass']} | {r['fail']} | {r['warn']} | {r.get('fixes_applied', 0)} |")
        lines.append(f"")

    final = pipeline_data.get("final_status", "UNKNOWN")
    lines.append(f"## Final Status: **{final}**")
    lines.append(f"")

    return "\n".join(lines)


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(0 if obj.get("ok") else 1)


def main():
    parser = argparse.ArgumentParser(description="Report generator")
    sub = parser.add_subparsers(dest="command")

    p_audit = sub.add_parser("audit", help="Generate audit report from JSON")
    p_audit.add_argument("input", help="JSON file or '-' for stdin")
    p_audit.add_argument("--output", help="Output markdown file")

    p_validate = sub.add_parser("validate", help="Generate validation report from JSON")
    p_validate.add_argument("input", help="JSON file or '-' for stdin")
    p_validate.add_argument("--output", help="Output markdown file")

    p_pipeline = sub.add_parser("pipeline", help="Generate pipeline report from JSON")
    p_pipeline.add_argument("input", help="JSON file or '-' for stdin")
    p_pipeline.add_argument("--output", help="Output markdown file")

    args = parser.parse_args()

    if args.command in ("audit", "validate", "pipeline"):
        if args.input == "-":
            data = json.load(sys.stdin)
        else:
            with open(args.input) as f:
                data = json.load(f)

        generators = {
            "audit": generate_audit_report,
            "validate": generate_validation_report,
            "pipeline": generate_pipeline_report,
        }
        markdown = generators[args.command](data)

        if args.output:
            Path(args.output).write_text(markdown)
            out({"ok": True, "data": {"file": args.output, "size": len(markdown)}})
        else:
            print(markdown)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
