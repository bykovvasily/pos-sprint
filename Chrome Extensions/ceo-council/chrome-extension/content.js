(function () {
  const STORAGE_KEY = 'ceo-council-opinions';
  const CEO_NAMES = { jobs: 'Стив Джобс', zuckerberg: 'Марк Цукерберг', lebedev: 'Артемий Лебедев' };
  function getOrigin() { try { return window.location.origin; } catch { return ''; } }
  function showBadge(firstOpinion, author) {
    if (!firstOpinion || document.getElementById('ceo-council-badge')) return;
    var style = document.createElement('style');
    style.textContent = '.ceo-council-badge{position:fixed;top:12px;right:12px;width:24px;height:24px;background:#6366f1;color:#fff;border-radius:50%;font-size:11px;display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:999999;box-shadow:0 2px 8px rgba(0,0,0,.3);font-family:system-ui;}';
    document.head.appendChild(style);
    var badge = document.createElement('div');
    badge.id = 'ceo-council-badge';
    badge.className = 'ceo-council-badge';
    badge.title = 'Есть мнения CEO Council — открой расширение';
    badge.textContent = '3';
    badge.addEventListener('click', function () {
      var pop = window.open('', '_blank', 'width=380,height=320');
      pop.document.write(
        '<!DOCTYPE html><html><head><meta charset="utf-8"><title>CEO Council</title></head><body style="font-family:system-ui;padding:14px;background:#0f0f12;color:#e4e4e7;white-space:pre-wrap;font-size:13px;">' +
        '<p style="font-size:11px;color:#6366f1;font-weight:600;text-transform:uppercase;margin-bottom:8px;">' + escapeHtml(author) + '</p>' +
        escapeHtml(firstOpinion) + '</body></html>'
      );
    });
    document.body.appendChild(badge);
  }
  function escapeHtml(s) { var div = document.createElement('div'); div.textContent = s; return div.innerHTML; }
  chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
    if (msg.action === 'getPageContent') {
      sendResponse({ title: document.title || '', text: (document.body && document.body.innerText) ? document.body.innerText.slice(0, 30000) : '' });
    }
  });
  chrome.storage.local.get([STORAGE_KEY], function (data) {
    var all = data[STORAGE_KEY] || {};
    var origin = getOrigin();
    var record = all[origin];
    if (!record) return;
    var text = (record.jobs && record.jobs.trim()) || (record.zuckerberg && record.zuckerberg.trim()) || (record.lebedev && record.lebedev.trim());
    var author = record.jobs && record.jobs.trim() ? CEO_NAMES.jobs : (record.zuckerberg && record.zuckerberg.trim() ? CEO_NAMES.zuckerberg : CEO_NAMES.lebedev);
    if (text) showBadge(text, author);
  });
})();
