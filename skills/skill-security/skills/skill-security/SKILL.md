---
name: skill-security
version: 1.0.0
description: >
  This skill activates when the user mentions "security audit", "skill audit",
  "проверка безопасности скилла", "аудит скилла", "skill-security",
  "проверить скилл", "пересобрать скилл", "rebuild skill",
  "security check", "dual memory audit", "credential isolation check".
  Also activates on /skill-security command.
  Use this skill when the user wants to audit, validate, or rebuild any
  Claude Code skill for security compliance.
argument-hint: <path-to-skill-directory>
allowed-tools: [Bash, Read, Edit, Write, Glob, Grep, WebSearch, WebFetch]
---

# skill-security — Global Security Meta-Skill

Audits and rebuilds any Claude Code skill against a 7-volume security checklist.
Ensures credential isolation, dual memory with sanitization, first-install UX,
cache isolation, shareability, architectural uniformity, and code correctness.

## Structure

```
skills/skill-security/
├── SKILL.md                    # This file
├── config/
│   └── config.json             # Token patterns, required files, categories
├── data/
│   ├── memory.json             # Shared memory (sanitized audit patterns)
│   └── checklist.json          # 7-volume checklist (machine format)
├── scripts/
│   ├── ss_memory.py            # Dual memory (check/record/list/confirm/promote)
│   ├── ss_security.py          # Secret scanner
│   ├── ss_templates.py         # Canonical file templates + gap analysis
│   ├── ss_analyze.py           # A1: deep-understand + A: audit
│   ├── ss_validate.py          # C: validation (syntax + structure + security + functional)
│   ├── ss_report.py            # Report generator (JSON → markdown)
│   └── ss_engine.py            # Pipeline orchestrator (A1→A→B→C↔D→E)
└── references/
    └── security-patterns.md    # All security patterns documentation
```

Scripts path:
```bash
cd /root/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-security/skills/skill-security/scripts
```

## Безопасность

**Этот мета-скилл НЕ имеет собственных API-credentials, но:**

- НИКОГДА не читать credentials.json целевых скиллов через Read/cat/head/tail
- Проверка credentials целевых скиллов: только через их `*_auth.py check-credentials`
- Токены целевых скиллов НИКОГДА не выводятся в контекст разговора
- Все пути в shared memory проходят sanitization

## Разделение данных (двойная память)

### В shared memory (data/memory.json) — деперсонализированное:
- Общие паттерны аудита: "скиллы без _sanitize_text() = утечка"
- Типовые исправления: "добавить chmod 600 при сохранении credentials"
- Паттерны архитектуры: "check-credentials должен возвращать {ok, data: {exists}}"

### В private memory (~/.config/skill-security/memory.json) — персональное:
- Пути к конкретным скиллам пользователя
- Результаты аудита конкретных скиллов
- Количество раундов, исправления для конкретного скилла

### НИКОГДА в shared:
- Абсолютные пути пользователя (/home/user/...)
- Названия приватных сервисов
- Реальные данные из целевых скиллов

## Algorithm

### Step 0 — Check memory (ОБЯЗАТЕЛЬНО)

```bash
python3 ss_memory.py check "<контекст запроса пользователя>"
```

Если есть релевантные записи — использовать как подсказку для аудита.

### Step 1 — Resolve target path

Parse user input to get absolute skill path. Validate:
- Path exists and is a directory
- Contains SKILL.md

### Step 2 — A1: Deep Understanding

```bash
python3 ss_analyze.py deep-understand "$SKILL_PATH"
```

Output: service profile (name, auth type, base_url, endpoints, credential fields).

If documentation research needed, use **WebSearch** to find:
- Service API documentation
- Auth flow details
- Required credential fields

### Step 3 — A: Deep Audit

```bash
python3 ss_analyze.py audit "$SKILL_PATH"
```

Output: 7-volume audit report with PASS/FAIL/WARN per check.

### Step 4 — B: Rebuild

```bash
python3 ss_engine.py run "$SKILL_PATH" --phase B
```

For automated gap-filling. For complex issues, manually fix using Read/Edit/Write.

### Step 5 — C↔D: Validation & Correction Loop

```bash
python3 ss_engine.py run "$SKILL_PATH" --phase all
```

Or manually:
1. Validate: `python3 ss_validate.py validate "$SKILL_PATH"`
2. If FAILs exist → fix → goto 1
3. Repeat until all PASS

### Step 6 — E: Self-learning

Record findings to memory:
- Shared (sanitized): generic patterns, fix recipes
- Private (as-is): specific paths, results, round counts

### Step 7 — Report

Present results to user:
- Summary table (7 volumes)
- Fixes applied
- Remaining manual issues (if any)

## Response Language

Respond in the same language as the user's request.
