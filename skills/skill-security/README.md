# skill-security — Global Security Meta-Skill

A Claude Code plugin that audits and rebuilds any skill for security compliance.

## What it does

Takes any Claude Code skill (anywhere on disk) and:

1. **A1: Deep Understanding** — analyzes the skill structure, detects service type, auth patterns, endpoints
2. **A: Deep Audit** — runs 7-volume security checklist (100+ checks)
3. **B: Rebuild** — applies canonical templates for dual memory, credential isolation, setup UX
4. **C: Validation** — syntax, structure, security re-scan, functional tests
5. **D: Correction Loop** — iterates C→B until 100% compliance
6. **E: Self-learning** — records patterns to dual memory for future audits

## Installation

Already installed as a global Claude Code plugin at:
```
/root/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-security/
```

## Usage

### Via slash command
```
/skill-security /path/to/any/skill
```

### Via direct script execution
```bash
cd /root/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-security/skills/skill-security/scripts

# Deep understanding
python3 ss_analyze.py deep-understand /path/to/skill

# Full audit
python3 ss_analyze.py audit /path/to/skill

# Full pipeline
python3 ss_engine.py run /path/to/skill --phase all

# Individual phases
python3 ss_engine.py run /path/to/skill --phase A1
python3 ss_engine.py run /path/to/skill --phase A
python3 ss_engine.py run /path/to/skill --phase B
python3 ss_engine.py run /path/to/skill --phase C

# Memory
python3 ss_memory.py check "dual memory sanitization"
python3 ss_memory.py list
python3 ss_memory.py list --private
```

## 7-Volume Checklist

| # | Volume | What it checks |
|---|--------|----------------|
| 1 | Security | Credential isolation, no secrets in package, check-credentials format |
| 2 | Dual Memory | Shared + private stores, sanitization, check_memory searches both |
| 3 | First-Install UX | check-credentials + setup_hint, Step 0 in SKILL.md |
| 4 | Caches | Cache paths in ~/.config/, placeholders in data/ |
| 5 | Shareability | No personal data, no hardcoded profiles |
| 6 | Architecture | File structure, JSON format, retry, SKILL.md sections |
| 7 | Code | Python syntax, imports, consistency, no __pycache__ |

## Architecture

- **ss_memory.py** — dual memory (shared sanitized + private as-is)
- **ss_security.py** — secret scanner with configurable patterns
- **ss_templates.py** — canonical templates for *_memory.py, *_auth.py, SKILL.md sections
- **ss_analyze.py** — Phase A1 (understanding) + Phase A (audit)
- **ss_validate.py** — Phase C (validation)
- **ss_report.py** — JSON to markdown reports
- **ss_engine.py** — full pipeline orchestrator
