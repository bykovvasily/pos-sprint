---
description: Security audit and rebuild for any Claude Code skill. Analyzes against 7-volume checklist, rebuilds with dual memory and credential isolation, validates until 100% compliance.
argument-hint: <path-to-skill> [--phase A1|A|B|C|D|all]
allowed-tools: [Bash, Read, Edit, Write, Glob, Grep, WebSearch, WebFetch]
---

# /skill-security — Security Audit & Rebuild

Target skill path: `$ARGUMENTS`

## Overview

This command runs a comprehensive security audit and rebuild pipeline on any Claude Code skill.

## Instructions

### Step 1: Resolve the target path

Parse `$ARGUMENTS` to extract:
- **skill_path** — first argument (required), resolve to absolute path
- **--phase** — optional, one of: A1, A, B, C, D, all (default: all)

If no path provided, ask the user for the skill path.

### Step 2: Validate the target

```bash
ls "$skill_path/SKILL.md" 2>/dev/null
```

If SKILL.md doesn't exist, inform the user this doesn't appear to be a valid skill directory.

### Step 3: Run the pipeline

The pipeline has these phases:
- **A1** — Deep Understanding: static analysis of the skill
- **A** — Deep Audit: 7-volume checklist verification
- **B** — Rebuild: apply template-based fixes
- **C** — Validation: full re-check
- **D** — Correction Loop: C→B cycle until 100%
- **all** — Run all phases sequentially

#### Phase A1: Deep Understanding

```bash
cd /root/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-security/skills/skill-security/scripts && python3 ss_analyze.py deep-understand "$skill_path"
```

Review the output. Use **WebSearch** to find the service's API documentation if needed.
Understand the service's auth flow, required credentials, and API patterns.

#### Phase A: Deep Audit

```bash
cd /root/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-security/skills/skill-security/scripts && python3 ss_analyze.py audit "$skill_path"
```

Review the 7-volume audit report. Note all FAIL and WARN items.

#### Phase B: Rebuild

For automated fixes:
```bash
cd /root/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-security/skills/skill-security/scripts && python3 ss_engine.py run "$skill_path" --phase B
```

For issues that require manual intervention, use Read/Edit/Write tools to:
1. Fix security issues (remove hardcoded tokens, add credential isolation)
2. Add/fix dual memory (shared + private, sanitization)
3. Add/fix auth script (check-credentials, save-token, setup_hint)
4. Add missing SKILL.md sections (security, dual memory, Step 0)

#### Phase C: Validation

```bash
cd /root/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-security/skills/skill-security/scripts && python3 ss_validate.py validate "$skill_path"
```

#### Phase D: Correction Loop

If Phase C shows failures, fix them and re-validate. Repeat until all checks pass.

#### Full Pipeline (all phases):

```bash
cd /root/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-security/skills/skill-security/scripts && python3 ss_engine.py run "$skill_path" --phase all
```

### Step 4: Self-learning

After each significant finding or fix, record to memory:

```bash
cd /root/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-security/skills/skill-security/scripts && python3 ss_memory.py record --problem "..." --solution "..." --tags "..." --category "audit_finding"
```

For private context (specific paths, service names):
```bash
cd /root/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-security/skills/skill-security/scripts && python3 ss_memory.py record --problem "..." --solution "..." --tags "..." --category "audit_finding" --private
```

### Step 5: Report

Present the final report to the user with:
- Summary table (7 volumes × PASS/FAIL/WARN)
- List of fixes applied
- Any remaining issues that need manual attention
- Total rounds of correction

## Important Notes

- All paths MUST be absolute
- NEVER read credentials files directly
- Always use check-credentials for credential verification
- Record learnings to memory for future audits
- The correction loop has no round limit — it runs until 100% or until no more automated fixes are possible
