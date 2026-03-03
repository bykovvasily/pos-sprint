---
allowed-tools: Read, Glob, Grep, Bash, mcp__memory__search_nodes, mcp__memory__read_graph
description: "Session initialization - load context and memory state"
---

# SESSION INITIALIZATION

## Step 0: MCP Health Check (CRITICAL!)

### 0.1 Memory Server — Primary Source

**Ваш основной сервер = PRIMARY SOURCE для долговременной памяти!**

<!-- 📌 НАСТРОЙТЕ: укажите путь к вашей базе MCP memory -->
<!-- Пример: ~/.claude-mem/claude-mem.db или ~/.claude/memory.jsonl -->

При долгой работе на сервере — данные накапливаются здесь.
Если работаете с нескольких машин — определите source of truth.

---

### 0.2 MCP Troubleshooting Reference

**Проверьте MCP серверы при старте. Если всё OK — переходите к Step 1.**

**Если memory НЕ Connected:**
```
🚨 CRITICAL: MEMORY MCP MISSING!

Memory MCP отключён! Контекст между сессиями теряется.

FIX: claude mcp add memory -- npx -y @modelcontextprotocol/server-memory

После добавления нужна НОВАЯ СЕССИЯ (MCP грузятся при старте).
```

<!-- 📌 ДОБАВЬТЕ СВОИ MCP СЕРВЕРЫ НИЖЕ -->
<!-- Для каждого — блок "Если X НЕ Connected" с FIX командой -->
<!-- Примеры серверов: -->
<!-- - telegram (User API / MTProto) -->
<!-- - email (IMAP/SMTP или Graph API) -->
<!-- - exa (web search) -->
<!-- - github (GitHub API) -->
<!-- - filesystem (доступ к файлам) -->

---

### 0.3 Research Template

**⚠️ ПРАВИЛО:** Каждый research-запрос ДОЛЖЕН включать актуальную дату!

**Шаблон:**
```
"Проведи исследование лучших практик для [ПРОБЛЕМА]. Сегодня [DATE]."
```

**Почему важно:** Без даты LLM возвращает устаревшие результаты.

**Формат даты:** `March 2026` (широкий) | `Mar 3, 2026` (точный) | `2026-03-03` (ISO)

---

## Step 1: Check Claude Code Version and Date

Run in ONE bash call:
```bash
echo "VERSION: $(claude --version 2>/dev/null || echo 'N/A')" && echo "DATE: $(date '+%A, %Y-%m-%d')"
```

<!-- 📌 НАСТРОЙТЕ: путь к файлу отслеживания версии -->
Then Read `.claude/last_known_version.txt`. If NEW VERSION → update file.

## Step 2: Load Project Instructions

<!-- 📌 НАСТРОЙТЕ: путь к инструкциям вашего проекта -->
<!-- Пример: Read `.claude/instructions.md` -->
<!-- Содержит: naming conventions, теги, архитектура, принципы -->

## Step 3: Detect Environment

<!-- 📌 НАСТРОЙТЕ: ваши рабочие окружения -->
- `/home/user/project` → Server (Linux)
- `C:\Users\username\project` → Windows PC
- `/Users/username/project` → macOS

## Step 4: Load Memory Context (TARGETED!)

**ВАЖНО:** НЕ вызывай `read_graph` — граф растёт (10K+ токенов) и жрёт контекст.
Делай 3 targeted поиска параллельно:

```
mcp__memory__search_nodes("2026-03")     # текущий месяц
mcp__memory__search_nodes("CRITICAL")    # критичные баги/фиксы
mcp__memory__search_nodes("DEPLOYED")    # текущие деплои
```

Из результатов выбери 5-7 самых свежих/важных entity для summary.

**Правило:** долговременная память = НИКОГДА не удалять observations!

## Step 5: Check Active Plans

<!-- 📌 НАСТРОЙТЕ: путь к вашему dashboard активных планов/проектов -->
<!-- Пример: Read "Plans/Active Plans Dashboard.md" -->

## Step 6: Output Summary

**Определи день недели ТОЧНО через bash (НЕ угадывай!):**
```bash
date "+%A, %Y-%m-%d"
```

```
## SESSION INITIALIZED

**Environment:** [Server/Home PC/Mac]
**Date:** [WEEKDAY from bash], [YYYY-MM-DD]

### Context:
- instructions loaded
- memory: [summary of recent entities]
- Active Plans: [X active + Y frozen]

### Active Plans:
- **Project A:** status
- **Project B:** status

📊 Context: ~[X]K | 🟢 OK
```

---

## Step 7: Progressive Disclosure (УМНАЯ ПОДГРУЗКА)

После инициализации, ПЕРЕД началом работы, определи тип задачи и подгрузи нужное:

<!-- 📌 НАСТРОЙТЕ: категории задач и связанные skills/файлы -->

| Тип задачи | Что подгрузить |
|------------|---------------|
| Документы | Skills/правила документации |
| Код | Архитектурные принципы |
| Инфраструктура | Infra skills |
| Research | Web research skill + дата |
| Сложная/непонятная | Полные инструкции или `/interview` |

---

## Context Budget

| Уровень | Размер | Когда |
|---------|--------|-------|
| **Base** | ~5KB | Всегда при старте |
| **+Секция** | +2-5KB | По типу задачи |
| **+Skill** | +3-5KB | Автоактивация |
| **Full** | 30-60KB | Только если сложно |

**Цель:** Начинать с ~10-15K токенов, подгружать по необходимости.
