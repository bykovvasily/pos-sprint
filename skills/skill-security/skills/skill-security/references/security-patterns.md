# Security Patterns Reference

## 1. Credential Isolation

### Storage Pattern
```
~/.config/<service>/
├── credentials.json    ← chmod 600, NEVER in skill package
├── memory.json         ← private memory (not shared)
└── *_cache.json        ← user-specific caches
```

### Platform-Aware Path
```python
def _get_config_dir():
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", "~")) / "<service>"
    else:
        base = Path.home() / ".config" / "<service>"
    base.mkdir(parents=True, exist_ok=True)
    return base
```

### chmod 600
```python
if sys.platform != "win32":
    os.chmod(cred_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
```

## 2. check-credentials Pattern

### Response Format
```json
{
  "ok": true,
  "data": {
    "exists": true,
    "path": "/home/user/.config/service/credentials.json"
  }
}
```

### When Not Found
```json
{
  "ok": true,
  "data": {
    "exists": false,
    "path": "/home/user/.config/service/credentials.json",
    "setup_hint": "Step-by-step instructions..."
  }
}
```

### Rules
- ONLY checks file existence and size > 2 bytes
- NEVER reads file contents to stdout
- NEVER outputs token values

## 3. Dual Memory Architecture

### Two Stores
| Store | Path | Content | Shared? |
|-------|------|---------|---------|
| Shared | `<skill>/data/memory.json` | Sanitized patterns | Yes |
| Private | `~/.config/<service>/memory.json` | As-is personal data | No |

### ID Format
- Shared: `mem_001`, `mem_002`, ...
- Private: `prv_001`, `prv_002`, ...

### Sanitization Rules
- ALL shared entries pass through `_sanitize_text()`
- Private entries stored as-is
- Exact-string: replace credential values with `***`
- Regex: replace service-specific patterns (tokens, IDs)

### Scoring Algorithm
```
+2.0  per tag found in context
+1.0  per token >3 chars found in problem
+0.5  per token >3 chars found in solution
```

## 4. Known Token Patterns

| Service | Pattern | Replacement |
|---------|---------|-------------|
| Figma PAT | `figd_[A-Za-z0-9_-]{10,}` | `***` |
| Figma File | `figma\.com/(?:file\|design\|proto)/[A-Za-z0-9_-]{10,}` | `***` |
| YaTrack | `y0__[A-Za-z0-9_-]{10,}` | `***` |
| TickTick | `[0-9a-f]{24}` (ObjectId) | `***` |
| GitHub PAT | `ghp_[A-Za-z0-9]{36}` | `***` |
| Slack | `xox[baprs]-[A-Za-z0-9-]{10,}` | `***` |
| AWS | `AKIA[0-9A-Z]{16}` | `***` |
| Generic Bearer | `Bearer\s+[A-Za-z0-9._~+/=-]{20,}` | `***` |

## 5. SKILL.md Required Sections

### Security Section
```markdown
## Безопасность
- НИКОГДА не читать credentials.json через Read/cat/head/tail
- Проверка: только через `*_auth.py check-credentials`
- Сохранение: только через `*_auth.py save-token`
- Токены НИКОГДА не выводятся в контекст разговора
```

### Dual Memory Section
```markdown
## Разделение данных (двойная память)
### В shared memory — деперсонализированное
### В private memory — персональное
### НИКОГДА в shared: токены, org_id, имена, URLs
```

### Step 0 Section
```markdown
### Step 0 — Проверка credentials (ОБЯЗАТЕЛЬНО)
1. Вызвать *_auth.py check-credentials
2. Если exists=false → показать setup_hint → СТОП
3. Если exists=true → продолжить
```

## 6. JSON Output Format

### Success
```json
{"ok": true, "data": {...}, "meta": {"api_calls": 1}}
```

### Error
```json
{"ok": false, "error": "...", "error_type": "auth|forbidden|not_found|bad_request|server|unknown", "memory_hint": "..."}
```

## 7. Retry Pattern
```python
RETRY_DELAYS = [1, 3, 10]
# 429 → read Retry-After header, sleep, retry
# 5xx → retry with backoff
# ConnectionError → retry
```
