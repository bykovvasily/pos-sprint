---
name: session-save
description: >
  Compress and save current session context for handoff to next session.
  Use when: (1) context pressure >50%, (2) user says "сохрани сессию",
  "session save", "checkpoint", (3) before ending a long productive session,
  (4) switching to a different task mid-session.
  Supports named sessions: /session-save vpn-fix
argument-hint: "[name] — optional session name (slug, e.g. vpn-fix, feature-auth)"
---

# Session Save — Named Context Checkpoints

Compress current session state → save to named checkpoint file.

## Storage

<!-- 📌 НАСТРОЙТЕ: путь к вашему проекту (Claude Code кодирует / как -) -->
```
~/.claude/projects/<YOUR-PROJECT-PATH>/memory/sessions/
  {name}.md          ← named checkpoints
  _latest.md         ← always points to last saved
~/.claude/projects/<YOUR-PROJECT-PATH>/memory/last-session.md  ← legacy compat
```

## Naming Rules

- If user provides name: use as-is (slug, lowercase, hyphens). Example: `vpn-fix`, `auth-refactor`
- If no name: auto-generate from goal. Pattern: `{topic}-{MMDD}`. Example: `insights-0303`
- Sanitize: `[^a-z0-9-]` → `-`, max 40 chars

## Compression Format (InfoCompressor)

Use imperative, terse, scannable style. 40-60% reduction. Zero redundancy.

### Template

```markdown
# Session: {name}
saved: YYYY-MM-DDTHH:MM
context: XX% (XXK tokens)
branch: <git branch>
name: {name}

## Goal
<1-2 sentences: what user wanted to achieve>

## Done
- <completed step 1>
- <completed step 2>

## Pending
- <next step 1>
- <next step 2>

## Modified Files
- `path/to/file1` — what changed
- `path/to/file2` — what changed

## Key Decisions
- <decision 1: chosen → reason>

## Context (carry forward)
<2-5 lines of critical context that next session MUST know>

## Continuation Prompt
<Ready-to-paste prompt for next session to resume work>
```

## Steps

1. **Determine name** — from argument or auto-generate from goal
2. **Analyze session** — review conversation history, identify goal/progress/pending
3. **Check git** — `git status`, `git diff --stat`, current branch
4. **Compress** using InfoCompressor principles:
   - Imperative mood, present tense, active voice
   - 3-7 words per statement
   - `→` for causality, `|` for alternatives
   - Cut filler words, state each fact once
5. **Write checkpoint** to `sessions/{name}.md`
6. **Copy to legacy** — also write to `last-session.md`
7. **Save to memory** — `mcp__memory__add_observations` on entity `Session-Checkpoint-{name}`:
   - goal, done count, pending, files, timestamp
8. **Confirm** — show:
   ```
   ✅ Session saved: {name}
   📁 sessions/{name}.md
   🔄 Resume: /continue {name}
   ```

## Rules

- Never lose: file paths, entity names, error messages, numeric values
- Checkpoint must be self-contained — readable without original session
- Continuation prompt must be specific enough to resume without questions
- Keep under 2KB (aim for 1KB)
- Overwrite existing checkpoint with same name (warn user first)

## Context Pressure Auto-Trigger

When context > 50% (🟡 WARNING):
1. Announce: "Context pressure 🟡 — saving checkpoint"
2. Run this skill automatically (auto-generate name)
3. Suggest: "Рекомендую `/continue {name}` в новой сессии"

When context > 72% (🔴 CRITICAL):
1. Save checkpoint immediately
2. **HANDOFF MODE** — refuse further execution
3. Write handoff blob
