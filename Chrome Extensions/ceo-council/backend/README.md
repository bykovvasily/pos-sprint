# CEO Council API

Бэкенд для расширения CEO Council. По содержимому страницы вызывает Claude (Anthropic) и возвращает три мнения на русском — Стив Джобс, Марк Цукерберг, Артемий Лебедев.

**Требования:** Node.js 18+, ключ [console.anthropic.com](https://console.anthropic.com/).

**Запуск:**

1. В папке `backend` создай файл `.env` с одной строкой: `ANTHROPIC_API_KEY=sk-ant-твой_ключ`
2. Выполни: `node server.js`

Сервер: **http://localhost:3001**. Расширение отправляет POST `/analyze` с `{ url, title, content }`.
