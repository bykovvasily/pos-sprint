/**
 * API для расширения CEO Council: по URL + тексту страницы возвращает
 * три мнения (Джобс, Цукерберг, Лебедев) через Anthropic Claude. Ответы на русском.
 * Ключ: из .env в этой папке (ANTHROPIC_API_KEY=sk-ant-...).
 */

import http from 'http';
import { readFileSync, existsSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

function loadEnv() {
  const dir = dirname(fileURLToPath(import.meta.url));
  const envPath = existsSync(join(dir, '.env')) ? join(dir, '.env') : existsSync(join(dir, '.env.txt')) ? join(dir, '.env.txt') : null;
  if (!envPath) {
    console.warn('.env not found. Create file:', join(dir, '.env'), 'with line: ANTHROPIC_API_KEY=sk-ant-...');
    return;
  }
  let text = readFileSync(envPath, 'utf8').replace(/\uFEFF/g, '');
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.replace(/\uFEFF/g, '').trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq <= 0) continue;
    const key = trimmed.slice(0, eq).trim().replace(/\uFEFF/g, '');
    if (key !== 'ANTHROPIC_API_KEY') continue;
    let val = trimmed.slice(eq + 1).trim().replace(/\r/g, '').replace(/^["'`]|["'`]$/g, '');
    if (val && val.startsWith('sk-ant-')) {
      process.env.ANTHROPIC_API_KEY = val;
      return;
    }
  }
  console.warn('.env found but no valid ANTHROPIC_API_KEY=sk-ant-... line');
}
loadEnv();

const PORT = 3001;
const ANTHROPIC_API = 'https://api.anthropic.com/v1/messages';
const MODEL = 'claude-sonnet-4-20250514';
const MAX_TOKENS = 600;

function buildDataBlock(payload) {
  const { url, title, content } = payload;
  const text = (content || '').slice(0, 25000);
  return [`URL: ${url || ''}`, `Заголовок: ${title || ''}`, '', 'Текст страницы (начало):', text || '(пусто)'].join('\n');
}

const PROMPTS = {
  jobs: (dataBlock) => `You are Steve Jobs evaluating the following website. Focus on: simplicity, design integrity, what to remove. Keep it short: one praise, one criticism, one verdict. Отвечай обязательно на русском языке.

Data:
${dataBlock}`,

  zuckerberg: (dataBlock) => `You are Mark Zuckerberg evaluating the following website from growth perspective. Focus on: what would make this spread, what to measure, one risk. Отвечай обязательно на русском языке.

Data:
${dataBlock}`,

  lebedev: (dataBlock) => `You are Artemy Lebedev reviewing the following website. Be blunt. Focus on: design/typography, UX, copy. One thing done well, 2–3 concrete criticisms. Отвечай обязательно на русском языке.

Data:
${dataBlock}`
};

async function callClaude(apiKey, userPrompt) {
  const res = await fetch(ANTHROPIC_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' },
    body: JSON.stringify({ model: MODEL, max_tokens: MAX_TOKENS, messages: [{ role: 'user', content: userPrompt }] })
  });
  if (!res.ok) {
    const err = await res.text();
    if (res.status === 403) throw new Error('Anthropic 403: регион или ключ. Попробуй VPN или новый ключ в console.anthropic.com');
    throw new Error(`Anthropic: ${res.status} ${err}`);
  }
  const data = await res.json();
  return (data.content?.[0]?.text ?? '').trim();
}

async function analyze(payload, apiKey) {
  const block = buildDataBlock(payload);
  const [jobs, zuckerberg, lebedev] = await Promise.all([
    callClaude(apiKey, PROMPTS.jobs(block)),
    callClaude(apiKey, PROMPTS.zuckerberg(block)),
    callClaude(apiKey, PROMPTS.lebedev(block))
  ]);
  return { jobs, zuckerberg, lebedev };
}

const cors = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' };

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') { res.writeHead(204, cors); res.end(); return; }
  if (req.method === 'GET' && (req.url === '/' || req.url === '/health')) {
    res.writeHead(200, { ...cors, 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, service: 'ceo-council-api' }));
    return;
  }
  if (req.method !== 'POST' || req.url !== '/analyze') {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
    return;
  }
  let apiKey = (process.env.ANTHROPIC_API_KEY || '').trim().replace(/\r/g, '').replace(/^["'`\s]+|["'`\s]+$/g, '');
  if (!apiKey) {
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'ANTHROPIC_API_KEY not set. Add to .env' }));
    return;
  }
  if (!apiKey.startsWith('sk-ant-')) {
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'ANTHROPIC_API_KEY must start with sk-ant-' }));
    return;
  }
  let body = '';
  for await (const chunk of req) body += chunk;
  let payload;
  try { payload = JSON.parse(body); } catch {
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Invalid JSON' }));
    return;
  }
  try {
    const result = await analyze(payload, apiKey);
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify(result));
  } catch (e) {
    res.writeHead(500, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify({ error: e.message }));
  }
});

server.listen(PORT, () => {
  let key = (process.env.ANTHROPIC_API_KEY || '').trim().replace(/\r/g, '').replace(/^["'`\s]+|["'`\s]+$/g, '');
  if (key) process.env.ANTHROPIC_API_KEY = key;
  console.log(`CEO Council API: http://localhost:${PORT}`);
  if (!key) console.warn('ANTHROPIC_API_KEY is not set');
  else if (!key.startsWith('sk-ant-')) console.warn('ANTHROPIC_API_KEY should start with sk-ant-');
  else console.log('API key loaded, length:', key.length);
});
