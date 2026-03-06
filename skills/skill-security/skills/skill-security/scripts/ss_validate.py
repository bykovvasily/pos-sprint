#!/usr/bin/env python3
"""Validation engine for skill-security meta-skill.

Phase C: Multi-check validation:
  syntax    — compile all .py files
  structure — check required files exist
  validate  — full validation (syntax + structure + security re-scan + functional)
"""

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from ss_analyze import audit, _detect_prefix
from ss_security import scan as security_scan


def check_syntax(skill_path):
    """Check all .py files for syntax errors."""
    skill_path = Path(skill_path).resolve()
    scripts_dir = skill_path / "scripts"
    results = []

    if not scripts_dir.exists():
        return [{"file": str(scripts_dir), "status": "FAIL",
                 "description": "scripts/ directory not found"}]

    for py_file in sorted(scripts_dir.glob("*.py")):
        try:
            content = py_file.read_text(errors="ignore")
            compile(content, str(py_file), "exec")
            results.append({
                "file": str(py_file),
                "status": "PASS",
                "description": f"Valid syntax: {py_file.name}",
            })
        except SyntaxError as e:
            results.append({
                "file": str(py_file),
                "line": e.lineno,
                "status": "FAIL",
                "description": f"Syntax error in {py_file.name} line {e.lineno}: {e.msg}",
            })

    return results


def check_imports(skill_path):
    """Check that imports in .py files can be resolved."""
    skill_path = Path(skill_path).resolve()
    scripts_dir = skill_path / "scripts"
    results = []

    if not scripts_dir.exists():
        return results

    stdlib_modules = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else set()

    for py_file in sorted(scripts_dir.glob("*.py")):
        try:
            content = py_file.read_text(errors="ignore")
        except OSError:
            continue

        lines = content.split("\n")
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()
            if line_stripped.startswith("import ") or line_stripped.startswith("from "):
                # Extract module name
                if line_stripped.startswith("from "):
                    parts = line_stripped.split()
                    if len(parts) >= 2:
                        module = parts[1].split(".")[0]
                    else:
                        continue
                else:
                    parts = line_stripped.split()
                    if len(parts) >= 2:
                        module = parts[1].split(".")[0].rstrip(",")
                    else:
                        continue

                # Skip relative imports within the skill
                if module.startswith("."):
                    continue

                # Check if module exists
                if module in stdlib_modules:
                    continue

                # Check as local import within scripts/
                local_file = scripts_dir / f"{module}.py"
                if local_file.exists():
                    continue

                # Check if it's an installed package
                spec = importlib.util.find_spec(module)
                if spec is not None:
                    continue

                results.append({
                    "file": str(py_file),
                    "line": line_num,
                    "status": "WARN",
                    "description": f"Unresolved import '{module}' in {py_file.name}:{line_num}",
                })

    return results


def check_structure(skill_path):
    """Check required files and directories exist."""
    skill_path = Path(skill_path).resolve()
    prefix = _detect_prefix(skill_path)
    results = []

    required = {
        "SKILL.md": "Skill algorithm and rules",
        f"scripts/{prefix}_memory.py": "Dual memory system",
        f"scripts/{prefix}_auth.py": "Credential management",
        "config/config.json": "Universal settings",
        "data/memory.json": "Shared memory store",
    }

    for rel_path, description in required.items():
        full_path = skill_path / rel_path
        # Handle glob patterns
        if "*" in rel_path:
            import glob as glob_mod
            matches = list(skill_path.glob(rel_path))
            exists = len(matches) > 0
        else:
            exists = full_path.exists()

        results.append({
            "file": str(full_path),
            "status": "PASS" if exists else "FAIL",
            "description": f"{description}: {rel_path}" if exists else f"Missing: {rel_path} ({description})",
        })

    # Check for scripts/ directory
    if not (skill_path / "scripts").exists():
        results.append({
            "file": str(skill_path / "scripts"),
            "status": "FAIL",
            "description": "Missing scripts/ directory",
        })

    return results


def check_functional(skill_path):
    """Run basic CLI commands to check they don't crash."""
    skill_path = Path(skill_path).resolve()
    prefix = _detect_prefix(skill_path)
    scripts_dir = skill_path / "scripts"
    results = []

    # Test check-credentials (should not crash)
    auth_file = scripts_dir / f"{prefix}_auth.py"
    if auth_file.exists():
        try:
            proc = subprocess.run(
                [sys.executable, str(auth_file), "check-credentials"],
                capture_output=True, text=True, timeout=10,
                cwd=str(scripts_dir),
            )
            if proc.returncode in (0, 1):  # 0=ok, 1=not found (both valid)
                try:
                    output = json.loads(proc.stdout)
                    if "ok" in output:
                        results.append({
                            "file": str(auth_file),
                            "status": "PASS",
                            "description": "check-credentials runs without crash",
                        })
                    else:
                        results.append({
                            "file": str(auth_file),
                            "status": "WARN",
                            "description": "check-credentials output missing 'ok' field",
                        })
                except json.JSONDecodeError:
                    results.append({
                        "file": str(auth_file),
                        "status": "FAIL",
                        "description": f"check-credentials output is not JSON: {proc.stdout[:100]}",
                    })
            else:
                results.append({
                    "file": str(auth_file),
                    "status": "FAIL",
                    "description": f"check-credentials crashed: {proc.stderr[:200]}",
                })
        except (subprocess.TimeoutExpired, OSError) as e:
            results.append({
                "file": str(auth_file),
                "status": "FAIL",
                "description": f"check-credentials error: {e}",
            })

    # Test memory check (should not crash)
    memory_file = scripts_dir / f"{prefix}_memory.py"
    if memory_file.exists():
        try:
            proc = subprocess.run(
                [sys.executable, str(memory_file), "check", "test context"],
                capture_output=True, text=True, timeout=10,
                cwd=str(scripts_dir),
            )
            if proc.returncode == 0:
                results.append({
                    "file": str(memory_file),
                    "status": "PASS",
                    "description": "memory check runs without crash",
                })
            else:
                results.append({
                    "file": str(memory_file),
                    "status": "FAIL",
                    "description": f"memory check failed: {proc.stderr[:200]}",
                })
        except (subprocess.TimeoutExpired, OSError) as e:
            results.append({
                "file": str(memory_file),
                "status": "FAIL",
                "description": f"memory check error: {e}",
            })

    # Test memory record --help (should not crash)
    if memory_file.exists():
        try:
            proc = subprocess.run(
                [sys.executable, str(memory_file), "record", "--help"],
                capture_output=True, text=True, timeout=10,
                cwd=str(scripts_dir),
            )
            if proc.returncode == 0:
                results.append({
                    "file": str(memory_file),
                    "status": "PASS",
                    "description": "memory record --help works",
                })
        except (subprocess.TimeoutExpired, OSError):
            pass

    return results


def validate(skill_path):
    """Full validation: syntax + structure + security + functional + audit.

    Returns combined report suitable for correction loop.
    """
    skill_path = Path(skill_path).resolve()

    if not skill_path.is_dir():
        return {"ok": False, "error": f"Not a directory: {skill_path}", "error_type": "bad_request"}

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return {"ok": False, "error": f"Not a skill (no SKILL.md): {skill_path}", "error_type": "bad_request"}

    all_items = []

    # 1. Syntax
    syntax_results = check_syntax(skill_path)
    for r in syntax_results:
        r["check"] = "syntax"
    all_items.extend(syntax_results)

    # 2. Import resolution
    import_results = check_imports(skill_path)
    for r in import_results:
        r["check"] = "imports"
    all_items.extend(import_results)

    # 3. Structure
    structure_results = check_structure(skill_path)
    for r in structure_results:
        r["check"] = "structure"
    all_items.extend(structure_results)

    # 4. Security re-scan
    scan_result = security_scan(str(skill_path))
    if scan_result.get("ok"):
        data = scan_result["data"]
        if data["total_findings"] == 0:
            all_items.append({"check": "security", "status": "PASS",
                              "description": "No secrets found"})
        else:
            for f in data.get("findings", [])[:10]:
                all_items.append({
                    "check": "security",
                    "status": "FAIL" if f["severity"] == "CRITICAL" else "WARN",
                    "description": f["description"],
                    "file": f.get("file", ""),
                    "line": f.get("line", 0),
                })

    # 5. Functional tests
    functional_results = check_functional(skill_path)
    for r in functional_results:
        r["check"] = "functional"
    all_items.extend(functional_results)

    # 6. Full audit (7 toms)
    audit_result = audit(str(skill_path))
    if audit_result.get("ok"):
        for tom_key, tom_data in audit_result["data"]["toms"].items():
            for item in tom_data["items"]:
                all_items.append({
                    "check": "audit",
                    "tom": tom_key,
                    "tom_name": tom_data["name"],
                    "id": item.get("id", ""),
                    "status": item["status"],
                    "description": item["description"],
                    "file": item.get("file", ""),
                    "line": item.get("line", 0),
                })

    # Summary
    passes = sum(1 for i in all_items if i["status"] == "PASS")
    fails = sum(1 for i in all_items if i["status"] == "FAIL")
    warns = sum(1 for i in all_items if i["status"] == "WARN")

    return {
        "ok": True,
        "data": {
            "target": str(skill_path),
            "summary": {
                "total_items": len(all_items),
                "pass": passes,
                "fail": fails,
                "warn": warns,
                "overall": "FAIL" if fails > 0 else ("WARN" if warns > 0 else "PASS"),
            },
            "items": all_items,
            "failures": [i for i in all_items if i["status"] in ("FAIL", "WARN")],
        },
    }


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(0 if obj.get("ok") else 1)


def main():
    parser = argparse.ArgumentParser(description="Skill validation engine")
    sub = parser.add_subparsers(dest="command")

    p_syntax = sub.add_parser("syntax", help="Check Python syntax")
    p_syntax.add_argument("target", help="Path to skill directory")

    p_structure = sub.add_parser("structure", help="Check required files")
    p_structure.add_argument("target", help="Path to skill directory")

    p_validate = sub.add_parser("validate", help="Full validation (all checks)")
    p_validate.add_argument("target", help="Path to skill directory")

    args = parser.parse_args()

    if args.command == "syntax":
        results = check_syntax(args.target)
        out({"ok": True, "data": {"results": results}})
    elif args.command == "structure":
        results = check_structure(args.target)
        out({"ok": True, "data": {"results": results}})
    elif args.command == "validate":
        result = validate(args.target)
        out(result)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
