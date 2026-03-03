---
name: continue-session
description: >
  Restore context from a named or latest session checkpoint.
  Use when: (1) user says "продолжи", "continue", "что было в прошлой сессии",
  (2) starting work after a crash or context overflow,
  (3) "resume", "восстанови контекст", "где я остановился".
  Supports named sessions: /continue vpn-fix
argument-hint: "[name] — session name, or blank for latest"
---

# Continue Session — Named Context Recovery

Restore session context from named checkpoint + memory + git.

## Resolution Order

### If name provided: `/continue vpn-fix`
1. Look for `sessions/vpn-fix.md`
2. If not found → fuzzy search (grep session names)
3. If still not found → show available sessions and ask user

### If no name: `/continue`
1. Read `last-session.md` or `sessions/_latest.md`
2. If neither exists → fall through to memory search

## Sources (check in order)

### 1. Named Checkpoint File (primary)
<!-- 📌 НАСТРОЙТЕ: путь к вашему проекту -->
```
~/.claude/projects/<YOUR-PROJECT-PATH>/memory/sessions/{name}.md
```
Read fully. Contains: goal, done, pending, modified files, continuation prompt.

### 2. Memory MCP (enrichment)
```
mcp__memory__search_nodes("Session-Checkpoint-{name}")
mcp__memory__search_nodes("<keyword from checkpoint goal>")
```
Add recent observations that relate to the checkpoint topic.

### 3. Git State
```bash
git status --short
git log --oneline -5
git diff --stat
```

## Recovery Flow

1. **Resolve checkpoint** — by name or latest
2. **Read checkpoint file** — if exists and <7 days old → use as primary source
3. **Enrich from memory** — search for related entities/observations
4. **Check git** — verify files from checkpoint still match, no unexpected changes
5. **Present summary:**

```
## Session Recovered: {name}

**From:** <checkpoint timestamp>
**Goal:** <what was being done>
**Progress:** <X done, Y pending>

### Done:
- ...

### Next Steps:
- ...

### Modified Files:
- ...

### Key Context:
- ...

Продолжаем? (или скорректируй направление)
```

6. **Wait for user confirmation** before acting

## Rules

- NEVER start working without showing the recovery summary first
- If checkpoint is >7 days old — warn: "Checkpoint устарел ({N} дней). Проверь актуальность."
- If checkpoint is >24h old but <7 days — note age but proceed normally
- If no checkpoint AND no recent sessions — say so honestly
- If checkpoint mentions pending tasks — ask "Продолжаем с [first pending]?"
- Proactive: check if any pending items were completed by other sessions (git log)

## Fallback Chain

```
Named checkpoint → last-session.md → memory search → git log → Ask user
```

Each level adds context. Never skip to "ask user" if data exists.
