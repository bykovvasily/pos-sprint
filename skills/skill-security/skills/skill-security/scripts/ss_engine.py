#!/usr/bin/env python3
"""Pipeline orchestrator for skill-security meta-skill.

Full pipeline: A1 → A → B → C↔D(infinite) → E

CLI: python3 ss_engine.py run <skill_path> [--phase A1|A|B|C|D|all]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from ss_memory import check_memory, record_entry
from ss_analyze import deep_understand, audit, _detect_prefix
from ss_templates import analyze_gaps, generate_file, generate_section, _detect_service_info
from ss_validate import validate, check_syntax
from ss_report import generate_pipeline_report


def _apply_fix(skill_path, gap):
    """Apply a single fix based on gap analysis.

    Returns description of what was fixed, or None if not fixable.
    """
    skill_path = Path(skill_path).resolve()
    info = _detect_service_info(str(skill_path))
    fix_type = gap.get("type", "")
    action = gap.get("action", "")
    target_file = Path(gap.get("file", ""))

    if action == "generate_from_template":
        template = gap.get("template", "")
        content = generate_file(template, info)
        if content:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(content)
            return f"Generated {target_file.name} from {template} template"

    elif action == "create_empty":
        target_file.parent.mkdir(parents=True, exist_ok=True)
        if target_file.suffix == ".json":
            target_file.write_text("[]")
        else:
            target_file.write_text("")
        return f"Created empty {target_file.name}"

    elif action == "add_section":
        section = gap.get("section", "")
        section_content = generate_section(section, info)
        if section_content and target_file.exists():
            existing = target_file.read_text(errors="ignore")
            # Add section before the last line or at the end
            if existing.rstrip().endswith("---"):
                existing = existing.rstrip()[:-3]
            new_content = existing.rstrip() + "\n\n---\n\n" + section_content + "\n"
            target_file.write_text(new_content)
            return f"Added {section} section to {target_file.name}"

    elif action == "remove_secret":
        field = gap.get("field", "")
        if target_file.exists():
            try:
                with open(target_file) as f:
                    cfg = json.load(f)
                if field in cfg:
                    del cfg[field]
                    with open(target_file, "w") as f:
                        json.dump(cfg, f, ensure_ascii=False, indent=2)
                    return f"Removed secret field '{field}' from {target_file.name}"
            except (json.JSONDecodeError, OSError):
                pass

    elif action == "create_skill_md":
        prefix = info.get("prefix", "xx")
        service = info.get("service_name", "service")
        content = f"""---
name: {service}
version: 0.1.0
description: >
  Skill for {service} integration.
argument-hint: <command>
allowed-tools: [Bash, Read, Edit]
---

# {service}

"""
        # Add required sections
        for section in ("security", "dual_memory", "step0"):
            sec_content = generate_section(section, info)
            if sec_content:
                content += sec_content + "\n\n"

        target_file.write_text(content)
        return f"Created SKILL.md with security, dual memory, and Step 0 sections"

    return None


def phase_a1(skill_path):
    """Phase A1: Deep Understanding."""
    result = deep_understand(str(skill_path))
    if result.get("ok"):
        data = result["data"]
        # Record to memory
        record_entry(
            problem=f"Understanding {data.get('service_name', '?')}: {data.get('auth_type', '?')} auth, {len(data.get('endpoints_found', []))} endpoints",
            solution=json.dumps(data.get("wizard_blueprint", {}), ensure_ascii=False)[:500],
            tags=["deep-understand", data.get("service_name", ""), data.get("auth_type", "")],
            category="wizard_insight",
            private=True,
        )
    return result


def phase_a(skill_path):
    """Phase A: Deep Audit."""
    result = audit(str(skill_path))
    if result.get("ok"):
        data = result["data"]
        summary = data["summary"]
        # Record audit summary to memory
        record_entry(
            problem=f"Audit: {summary['pass']}P/{summary['fail']}F/{summary['warn']}W — {summary['overall']}",
            solution=f"Key issues in toms: " + ", ".join(
                f"{k}={v['status']}" for k, v in data["toms"].items() if v["status"] != "PASS"
            ),
            tags=["audit", "summary"],
            category="audit_finding",
            private=True,
        )
    return result


def phase_b(skill_path, audit_report=None):
    """Phase B: Rebuild — apply template-based fixes."""
    gaps_result = analyze_gaps(str(skill_path))
    gaps = gaps_result.get("gaps", [])

    fixes_applied = []
    for gap in gaps:
        fix_desc = _apply_fix(skill_path, gap)
        if fix_desc:
            fixes_applied.append({
                "gap": gap["description"],
                "fix": fix_desc,
                "tom": gap.get("tom", 0),
            })
            # Record each fix to shared memory (sanitized)
            record_entry(
                problem=gap["description"],
                solution=fix_desc,
                tags=[f"tom_{gap.get('tom', 0)}", gap.get("type", "fix")],
                category="fix_pattern",
                private=False,
            )

    return {
        "ok": True,
        "data": {
            "total_gaps": gaps_result.get("total_gaps", 0),
            "fixes_applied": len(fixes_applied),
            "fixes": fixes_applied,
        },
    }


def phase_cd_loop(skill_path, max_stale_rounds=3):
    """Phase C↔D: Infinite correction loop until 100% PASS.

    Returns when all items pass, or provides detailed report on stale progress.
    """
    rounds_log = []
    total_fixes = 0
    prev_fail_count = float("inf")
    stale_counter = 0

    current_round = 0
    while True:
        # Phase C: Validate
        report = validate(str(skill_path))
        if not report.get("ok"):
            return {"rounds": current_round, "rounds_log": rounds_log,
                    "total_fixes": total_fixes, "error": report.get("error")}

        data = report["data"]
        summary = data["summary"]
        failures = data.get("failures", [])

        round_info = {
            "round": current_round,
            "total_items": summary["total_items"],
            "pass": summary["pass"],
            "fail": summary["fail"],
            "warn": summary["warn"],
            "fixes_applied": 0,
        }

        if not failures:
            # ALL PASS — exit loop
            rounds_log.append(round_info)
            record_entry(
                problem=f"Pipeline C/D loop completed in {current_round} rounds",
                solution=f"All {summary['total_items']} checks passed. Total fixes: {total_fixes}",
                tags=["pipeline", "complete"],
                category="audit_finding",
                private=True,
            )
            return {
                "rounds": current_round,
                "rounds_log": rounds_log,
                "total_fixes": total_fixes,
                "final_status": "PASS",
            }

        # Check for stale progress
        fail_count = len(failures)
        if fail_count >= prev_fail_count:
            stale_counter += 1
            if stale_counter >= max_stale_rounds:
                # Output detailed report but DON'T stop
                sys.stderr.write(
                    f"\n[WARN] No progress for {stale_counter} rounds. "
                    f"Remaining {fail_count} failures may need manual intervention.\n"
                    f"Failures:\n"
                )
                for f in failures[:10]:
                    sys.stderr.write(f"  - {f.get('description', '?')}\n")
                sys.stderr.write("\n")
        else:
            stale_counter = 0
        prev_fail_count = fail_count

        # Phase D: Analyze failures and apply fixes
        current_round += 1
        gaps_result = analyze_gaps(str(skill_path))
        gaps = gaps_result.get("gaps", [])

        fixes_this_round = 0
        for gap in gaps:
            # Check memory for known fix
            mem_hits, solution = check_memory(f"fix {gap['description']}")
            if solution and "Generated" in solution:
                # Known fix — apply directly
                pass

            fix_desc = _apply_fix(skill_path, gap)
            if fix_desc:
                fixes_this_round += 1
                total_fixes += 1
                record_entry(
                    problem=gap["description"],
                    solution=fix_desc,
                    tags=[f"tom_{gap.get('tom', 0)}", "correction_loop", f"round_{current_round}"],
                    category="fix_pattern",
                    private=False,
                )

        round_info["fixes_applied"] = fixes_this_round
        rounds_log.append(round_info)

        # If no fixes were applied but there are still failures,
        # these are issues that need manual intervention via Claude agent
        if fixes_this_round == 0 and failures:
            record_entry(
                problem=f"Round {current_round}: {len(failures)} unfixable issues remain",
                solution="These require manual fixes by Claude agent: " +
                         "; ".join(f["description"] for f in failures[:5]),
                tags=["pipeline", "manual_needed"],
                category="audit_finding",
                private=True,
            )
            return {
                "rounds": current_round,
                "rounds_log": rounds_log,
                "total_fixes": total_fixes,
                "final_status": "PARTIAL",
                "remaining_failures": failures,
                "message": "Some issues require manual Claude agent intervention",
            }


def run_pipeline(skill_path, phase="all"):
    """Run the full pipeline or a specific phase."""
    skill_path = Path(skill_path).resolve()

    if not skill_path.is_dir():
        return {"ok": False, "error": f"Not a directory: {skill_path}", "error_type": "bad_request"}

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists() and phase != "all":
        return {"ok": False, "error": f"Not a skill (no SKILL.md): {skill_path}",
                "error_type": "bad_request"}

    pipeline_data = {
        "target": str(skill_path),
        "phase": phase,
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # E: Pre-load memory
    context = f"audit security {skill_path.name}"
    mem_hits, _ = check_memory(context)
    if mem_hits:
        pipeline_data["memory_hits"] = len(mem_hits)

    if phase in ("A1", "all"):
        result = phase_a1(skill_path)
        if result.get("ok"):
            pipeline_data["understand"] = {
                "service_name": result["data"].get("service_name", "?"),
                "auth_type": result["data"].get("auth_type", "?"),
                "base_url": result["data"].get("base_url", "?"),
                "endpoints": len(result["data"].get("endpoints_found", [])),
            }
        if phase == "A1":
            pipeline_data["final_status"] = "A1_COMPLETE"
            return {"ok": True, "data": pipeline_data}

    if phase in ("A", "all"):
        result = phase_a(skill_path)
        if result.get("ok"):
            pipeline_data["audit_summary"] = result["data"]["summary"]
            pipeline_data["audit_toms"] = {
                k: v["status"] for k, v in result["data"]["toms"].items()
            }
        if phase == "A":
            pipeline_data["final_status"] = "AUDIT_COMPLETE"
            return {"ok": True, "data": pipeline_data}

    if phase in ("B", "all"):
        result = phase_b(skill_path)
        if result.get("ok"):
            pipeline_data["rebuild"] = result["data"]
        if phase == "B":
            pipeline_data["final_status"] = "REBUILD_COMPLETE"
            return {"ok": True, "data": pipeline_data}

    if phase in ("C", "all"):
        result = validate(str(skill_path))
        if result.get("ok"):
            pipeline_data["validation"] = result["data"]["summary"]
        if phase == "C":
            pipeline_data["final_status"] = result["data"]["summary"]["overall"]
            return {"ok": True, "data": pipeline_data}

    if phase in ("D", "all"):
        loop_result = phase_cd_loop(skill_path)
        pipeline_data["rounds_log"] = loop_result.get("rounds_log", [])
        pipeline_data["rounds"] = loop_result.get("rounds", 0)
        pipeline_data["total_fixes"] = loop_result.get("total_fixes", 0)
        pipeline_data["final_status"] = loop_result.get("final_status", "UNKNOWN")

        if loop_result.get("remaining_failures"):
            pipeline_data["remaining_failures"] = [
                {"description": f["description"], "check": f.get("check", "")}
                for f in loop_result["remaining_failures"][:10]
            ]

    # E: Final memory record
    record_entry(
        problem=f"Pipeline '{phase}' for {skill_path.name}",
        solution=f"Status: {pipeline_data.get('final_status', '?')}, "
                 f"Rounds: {pipeline_data.get('rounds', 0)}, "
                 f"Fixes: {pipeline_data.get('total_fixes', 0)}",
        tags=["pipeline", phase, skill_path.name],
        category="audit_finding",
        private=True,
    )

    pipeline_data["finished_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Generate markdown report
    pipeline_data["report_md"] = generate_pipeline_report(pipeline_data)

    return {"ok": True, "data": pipeline_data}


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(0 if obj.get("ok") else 1)


def main():
    parser = argparse.ArgumentParser(description="Skill-security pipeline orchestrator")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="Run pipeline")
    p_run.add_argument("target", help="Path to skill directory")
    p_run.add_argument("--phase", choices=["A1", "A", "B", "C", "D", "all"],
                       default="all", help="Pipeline phase (default: all)")

    args = parser.parse_args()

    if args.command == "run":
        result = run_pipeline(args.target, args.phase)
        out(result)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
