---
name: compress
description: >
  Info-Compressor: compress text/context by 60-70% without losing meaning.
  Use when: (1) context pressure >50%, (2) user says "сжать", "compress",
  "compact", (3) need to fit more context into remaining window,
  (4) preparing handoff blob for next session.
argument-hint: "[target] — what to compress: 'context' | 'clipboard' | 'file <path>'"
---

# Info-Compressor — 70% Context Compression

Compress text/context to ~30% of original size without losing meaning.

## Compression Techniques (apply ALL)

### 1. Structural
- **Prose → Tables** where data has patterns (comparisons, lists, specs)
- **Paragraphs → Bullet points** with 3-7 words each
- **Nested lists → Flat lists** with `→` for hierarchy

### 2. Linguistic
- **Remove filler:** "it should be noted that" → cut
- **Remove hedging:** "I think", "perhaps", "it seems" → cut
- **Active voice:** "was done by X" → "X did"
- **Imperative mood:** "you should run" → "run"
- **Present tense** everywhere
- **Remove articles** where meaning is clear: "the server" → "server"

### 3. Symbolic
- `→` for causality/flow ("X causes Y" → "X → Y")
- `|` for alternatives ("either A or B" → "A | B")
- `+` for additions ("also includes" → "+ includes")
- `=` for equivalence ("is the same as" → "=")
- `>` for preference ("better than" → ">")
- `✓/✗` for yes/no, done/not done
- `~` for approximation

### 4. Abbreviation
- Standard: cfg, env, srv, dir, repo, fn, arg, param, cmd, msg, req, res
- Context-specific: define at top if non-obvious
- **Never abbreviate:** file paths, entity names, error messages, URLs

### 5. Deduplication
- State each fact ONCE
- Remove repeated context from multiple messages
- Merge related items into single statement

## Modes

### `/compress context`
Compress the current conversation context, output a compressed summary.
Use as a "reset point" — paste at start of new session.

**Steps:**
1. Review full conversation
2. Extract: goals, decisions, progress, pending, files, gotchas
3. Apply all compression techniques
4. Output compressed blob (target: <2KB)
5. Show compression ratio: "Compressed: {original}K → {compressed}K ({ratio}%)"

### `/compress clipboard`
User will paste text. Compress it and return.

### `/compress file <path>`
Read file, compress content, return compressed version.

## Quality Check

After compression, verify:
- [ ] All file paths preserved exactly
- [ ] All numeric values preserved
- [ ] All entity/variable names preserved
- [ ] All error messages preserved
- [ ] Meaning is fully recoverable by someone who didn't read the original
- [ ] No ambiguity introduced by abbreviation

## Example

**Before (312 chars):**
> It should be noted that the server configuration was modified by the team yesterday. The main change was updating the database connection string from the old PostgreSQL server to the new one. Additionally, they also updated the Redis cache timeout from 300 seconds to 600 seconds.

**After (89 chars, 71% reduction):**
> Server cfg updated yesterday: DB conn string → new PostgreSQL srv, Redis cache timeout 300s → 600s

## Auto-Trigger on Context Pressure

At 🟡 50-72% context — **автоматически:**
1. Compress context (все техники сжатия)
2. `/session-save <auto-name>` (сохранить checkpoint)
3. Показать: "Context 🟡 — сжал и сохранил `<name>`. `/continue <name>` в новой сессии."

At 🔴 >72% context (HANDOFF) — **немедленно:**
1. Compress + save checkpoint
2. **REFUSE further execution**
3. Output handoff blob with instructions to continue in new session
