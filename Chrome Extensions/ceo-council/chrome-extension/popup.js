(function () {
  const STORAGE_KEY = 'ceo-council-opinions';
  const BACKEND_URL = 'http://localhost:3001';
  const CEO_KEYS = ['jobs', 'zuckerberg', 'lebedev'];
  const CEO_NAMES = { jobs: 'Стив Джобс', zuckerberg: 'Марк Цукерберг', lebedev: 'Артемий Лебедев' };

  function $(id) { return document.getElementById(id); }
  function getOrigin(url) { try { return new URL(url).origin; } catch { return ''; } }
  function loadAll() {
    return new Promise(function (resolve) {
      chrome.storage.local.get([STORAGE_KEY], function (data) { resolve(data[STORAGE_KEY] || {}); });
    });
  }
  function saveForOrigin(origin, data) {
    return loadAll().then(function (all) {
      all[origin] = data;
      return new Promise(function (resolve) {
        chrome.storage.local.set({ [STORAGE_KEY]: all }, resolve);
      });
    });
  }
  function getFilledIndices(record) {
    return CEO_KEYS.map(function (k, i) { return i; }).filter(function (i) {
      return record && record[CEO_KEYS[i]] && record[CEO_KEYS[i]].trim();
    });
  }
  function showView(id) {
    ['view-opinion', 'view-analyze', 'view-error'].forEach(function (v) {
      $(v).classList.toggle('hidden', v !== id);
    });
  }
  function showOpinion(record, nextIndex) {
    var filled = getFilledIndices(record);
    if (filled.length === 0) { showView('view-analyze'); return; }
    var idx = typeof nextIndex === 'number' ? nextIndex : filled[0];
    var key = CEO_KEYS[idx];
    $('opinion-author').textContent = CEO_NAMES[key];
    $('opinion-text').textContent = (record[key] || '').trim();
    $('opinion-text').scrollTop = 0;
    showView('view-opinion');
  }

  var currentOrigin = '';
  var currentTab = { url: '', title: '' };

  function runAnalysis() {
    var statusEl = $('analyze-status');
    statusEl.textContent = 'Получаю текст страницы…';
    statusEl.classList.remove('hidden');
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (!tabs[0]) { statusEl.textContent = 'Открой вкладку с сайтом'; statusEl.className = 'status error'; return; }
      var tab = tabs[0];
      currentTab = { url: tab.url || '', title: tab.title || '' };
      currentOrigin = getOrigin(tab.url);
      if (!currentOrigin || currentOrigin === 'null') {
        statusEl.textContent = 'Не удалось определить сайт (например, chrome://)'; statusEl.className = 'status error'; return;
      }
      chrome.tabs.sendMessage(tab.id, { action: 'getPageContent' }, function (reply) {
        if (chrome.runtime.lastError || !reply) {
          statusEl.textContent = 'Обнови страницу и нажми снова'; statusEl.className = 'status error'; return;
        }
        statusEl.textContent = 'Анализирую… Джобс, Цукерберг, Лебедев'; statusEl.className = 'status';
        fetch(BACKEND_URL + '/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: currentTab.url, title: reply.title || currentTab.title, content: reply.text || '' })
        })
          .then(function (r) {
            if (!r.ok) return r.json().then(function (e) { throw new Error(e.error || r.status); });
            return r.json();
          })
          .then(function (data) {
            var record = {
              jobs: (data.jobs || '').trim(),
              zuckerberg: (data.zuckerberg || '').trim(),
              lebedev: (data.lebedev || '').trim(),
              lastIndex: -1
            };
            return saveForOrigin(currentOrigin, record).then(function () {
              statusEl.classList.add('hidden');
              record.lastIndex = getFilledIndices(record)[0];
              saveForOrigin(currentOrigin, record);
              showOpinion(record, record.lastIndex);
            });
          })
          .catch(function (err) {
            var msg = err.message || String(err);
            if (msg === 'Failed to fetch' || msg.indexOf('fetch') !== -1) {
              msg = 'Не удалось подключиться к бэкенду. Запусти backend (см. README в папке ceo-council) и повтори.';
            }
            $('error-text').textContent = msg;
            showView('view-error');
          });
      });
    });
  }

  chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
    if (!tabs[0]) { showView('view-analyze'); return; }
    currentTab = { url: tabs[0].url || '', title: tabs[0].title || '' };
    currentOrigin = getOrigin(tabs[0].url);
    if (!currentOrigin) { showView('view-analyze'); return; }
    loadAll().then(function (all) {
      var record = all[currentOrigin] || {};
      var filled = getFilledIndices(record);
      if (filled.length === 0) { showView('view-analyze'); return; }
      var lastIndex = typeof record.lastIndex === 'number' ? record.lastIndex : -1;
      var nextIdx = filled[(filled.indexOf(lastIndex) + 1) % filled.length];
      if (nextIdx === undefined) nextIdx = filled[0];
      record.lastIndex = nextIdx;
      saveForOrigin(currentOrigin, record);
      showOpinion(record, nextIdx);
    });
  });

  $('btn-analyze').addEventListener('click', runAnalysis);
  $('btn-retry').addEventListener('click', function () {
    showView('view-analyze');
    $('analyze-status').classList.add('hidden');
    runAnalysis();
  });
})();
