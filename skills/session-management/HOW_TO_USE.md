# Session Management — How to Use

Session Management — набор из одной команды и трёх skills для управления контекстом сессии Claude Code.

## Зачем

Claude Code работает в контекстном окне (~200K токенов). Когда контекст заполняется — качество ответов падает, а затем сессия обрывается. Session Management решает эту проблему:

- **Session Start** — загружает контекст из памяти при начале новой сессии
- **Session Save** — сохраняет checkpoint текущей сессии перед уходом
- **Compress** — сжимает контекст на 60-70% когда окно заполняется
- **Continue Session** — восстанавливает checkpoint в новой сессии

## Жизненный цикл

```
┌─────────────────────────────────────────────────────┐
│                  SESSION LIFECYCLE                    │
│                                                      │
│  /session-start  ──→  РАБОТА  ──→  /session-save    │
│       ↑                                  │           │
│       │                                  ↓           │
│  /continue {name} ←── checkpoint file + memory       │
│                                                      │
│  /compress ──→ автоматически при context > 50%       │
│                                                      │
│  Context:  🟢 <50%  →  🟡 50-72%  →  🔴 >72%       │
│            работай     compress+save    HANDOFF       │
└─────────────────────────────────────────────────────┘
```

## Установка

### 1. Создайте директории

```bash
mkdir -p ~/.claude/commands
mkdir -p ~/.claude/skills/session-save
mkdir -p ~/.claude/skills/compress
mkdir -p ~/.claude/skills/continue-session
```

### 2. Скопируйте файлы

```bash
# Команда инициализации
cp commands/session-start.md ~/.claude/commands/

# Skills
cp skills/session-save/SKILL.md ~/.claude/skills/session-save/
cp skills/compress/SKILL.md ~/.claude/skills/compress/
cp skills/continue-session/SKILL.md ~/.claude/skills/continue-session/
```

### 3. Создайте хранилище для checkpoints

```bash
# Путь зависит от вашего проекта
# Claude Code кодирует / как - (например /home/user/project → -home-user-project)
PROJECT_MEMORY=~/.claude/projects/<YOUR-PROJECT-PATH>/memory
mkdir -p "$PROJECT_MEMORY/sessions"
```

### 4. Настройте файлы

Каждый файл содержит комментарии `<!-- 📌 НАСТРОЙТЕ: ... -->` — замените их на ваши данные:
- Пути к проекту
- Ваши MCP серверы
- Окружения (Server / PC / Mac)
- Список активных планов

## Использование

| Команда | Когда | Что делает |
|---------|-------|-----------|
| `/session-start` | Начало работы | Загружает memory, проверяет MCP, показывает планы |
| `/session-save my-task` | Перед уходом | Сохраняет checkpoint с именем `my-task` |
| `/session-save` | Перед уходом | Сохраняет checkpoint с автоименем |
| `/compress context` | Контекст > 50% | Сжимает весь разговор до ~30% |
| `/continue my-task` | Новая сессия | Восстанавливает checkpoint `my-task` |
| `/continue` | Новая сессия | Восстанавливает последний checkpoint |

## Требования

- **Claude Code** — CLI от Anthropic
- **MCP Memory Server** — для долговременной памяти между сессиями:
  ```bash
  claude mcp add memory -- npx -y @modelcontextprotocol/server-memory
  ```

## Кастомизация

Session Start — шаблон. Адаптируйте под свой проект:

1. **Step 0:** Добавьте ваши MCP серверы (telegram, email, GitHub и т.д.)
2. **Step 2-3:** Укажите пути к инструкциям и окружениям
3. **Step 5:** Создайте свой Active Plans Dashboard
4. **Step 7:** Определите категории задач и связанные skills

## Автор

Alexander Vasiliev — [github.com/alexfrmn](https://github.com/alexfrmn)
