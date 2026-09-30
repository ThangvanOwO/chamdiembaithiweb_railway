/* core.js - nen tang: goi API, dinh tuyen, tien ich DOM, thong bao, hop thoai, SSE */
'use strict';
const CTN = {
  user: null, settings: {}, view: null, sse: null, jobs: {}, cache: {},
  logs: [], logLevel: 'INFO', consoleOpen: false
};

/* ---------------- tien ich ---------------- */
const $  = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
function el(tag, attrs, kids) {
  const e = document.createElement(tag);
  if (attrs) for (const k in attrs) {
    if (k === 'class') e.className = attrs[k];
    else if (k === 'html') e.innerHTML = attrs[k];
    else if (k === 'text') e.textContent = attrs[k];
    else if (k.startsWith('on') && typeof attrs[k] === 'function') e.addEventListener(k.slice(2), attrs[k]);
    else if (attrs[k] !== null && attrs[k] !== undefined && attrs[k] !== false) e.setAttribute(k, attrs[k]);
  }
  if (kids) (Array.isArray(kids) ? kids : [kids]).forEach(k => {
    if (k === null || k === undefined || k === false) return;
    e.appendChild(typeof k === 'string' ? document.createTextNode(k) : k);
  });
  return e;
}
const esc = s => String(s === null || s === undefined ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
const num = (v, d) => {
  const n = Number(v);
  if (!isFinite(n)) return '0';
  return n.toLocaleString('vi-VN', { minimumFractionDigits: d === undefined ? 0 : d, maximumFractionDigits: d === undefined ? 2 : d });
};
const sc2 = v => (Math.round((Number(v) || 0) * 100) / 100).toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1');
function bytes(n) {
  n = Number(n) || 0;
  if (n < 1024) return n + ' B';
  if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
  if (n < 1073741824) return (n / 1048576).toFixed(1) + ' MB';
  return (n / 1073741824).toFixed(2) + ' GB';
}
function secs(s) {
  s = Math.max(0, Math.round(Number(s) || 0));
  if (s < 60) return s + ' giây';
  const m = Math.floor(s / 60), r = s % 60;
  if (m < 60) return m + 'p' + (r ? ' ' + r + 's' : '');
  return Math.floor(m / 60) + 'g ' + (m % 60) + 'p';
}
function debounce(fn, ms) {
  let t;
  return function () { clearTimeout(t); const a = arguments, s = this; t = setTimeout(() => fn.apply(s, a), ms || 300); };
}
function todayVN() {
  const d = new Date(Date.now() + (7 * 60 + new Date().getTimezoneOffset()) * 60000);
  return ('0' + d.getDate()).slice(-2) + '/' + ('0' + (d.getMonth() + 1)).slice(-2) + '/' + d.getFullYear();
}

/* ---------------- goi API ---------------- */
async function api(path, opts) {
  opts = opts || {};
  const init = { method: opts.method || 'GET', headers: {}, credentials: 'same-origin' };
  const csrf = document.cookie.split('; ').find(value => value.startsWith('csrftoken='));
  if (csrf) init.headers['X-CSRFToken'] = decodeURIComponent(csrf.split('=')[1]);
  if (opts.body !== undefined && !(opts.body instanceof FormData)) {
    init.headers['Content-Type'] = 'application/json';
    init.body = typeof opts.body === 'string' ? opts.body : JSON.stringify(opts.body);
  } else if (opts.body instanceof FormData) init.body = opts.body;
  if (opts.onProgress && init.body instanceof FormData) return xhrUpload(path, init.body, opts.onProgress);
  let res;
  try { res = await fetch(path, init); }
  catch (e) { throw new Error('Không kết nối được máy chủ'); }
  if (res.status === 401 && !opts.noAuthRedirect) { logoutLocal(); throw new Error('Phiên đăng nhập đã hết hạn'); }
  const ct = res.headers.get('content-type') || '';
  let data = null;
  if (ct.includes('json')) { try { data = await res.json(); } catch (e) { data = null; } }
  else data = await res.text();
  if (!res.ok) throw new Error((data && data.error) || ('Lỗi ' + res.status));
  return data;
}
function xhrUpload(path, form, onProgress) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open('POST', path, true);
    x.withCredentials = true;
    const csrf = document.cookie.split('; ').find(value => value.startsWith('csrftoken='));
    if (csrf) x.setRequestHeader('X-CSRFToken', decodeURIComponent(csrf.split('=')[1]));
    x.upload.onprogress = e => { if (e.lengthComputable) onProgress(e.loaded / e.total, e.loaded, e.total); };
    x.onload = () => {
      let d = null;
      try { d = JSON.parse(x.responseText); } catch (e) { }
      if (x.status === 401) { logoutLocal(); reject(new Error('Phiên đã hết hạn')); return; }
      if (x.status >= 200 && x.status < 300) resolve(d);
      else reject(new Error((d && d.error) || ('Lỗi ' + x.status)));
    };
    x.onerror = () => reject(new Error('Lỗi mạng khi tải tệp lên'));
    x.send(form);
  });
}

/* ---------------- thong bao ---------------- */
function toast(msg, kind, title) {
  const t = el('div', { class: 'toast ' + (kind || '') },
    [title ? el('b', { text: title }) : null, el('span', { html: esc(msg).replace(/\n/g, '<br>') })]);
  $('#toasts').appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(20px)'; t.style.transition = '.25s'; }, kind === 'err' ? 6500 : 3600);
  setTimeout(() => t.remove(), kind === 'err' ? 6800 : 3900);
  return t;
}
const ok  = (m, t) => toast(m, 'ok', t);
const err = (m, t) => toast(m, 'err', t || 'Lỗi');
const warn = (m, t) => toast(m, 'warn', t);

/* ---------------- hop thoai ---------------- */
function modal(opts) {
  const root = $('#modal-root'), box = $('#modal');
  box.className = 'modal' + (opts.size === 'wide' ? ' wide' : opts.size === 'xwide' ? ' xwide' : '');
  box.innerHTML = '';
  const head = el('div', { class: 'modal-head' }, [
    el('h3', { text: opts.title || '' }), el('div', { class: 'grow' }),
    el('button', { class: 'icon-btn', onclick: closeModal, title: 'Đóng' }, '✕')
  ]);
  const body = el('div', { class: 'modal-body' });
  if (typeof opts.body === 'string') body.innerHTML = opts.body;
  else if (opts.body) body.appendChild(opts.body);
  box.appendChild(head); box.appendChild(body);
  if (opts.buttons) {
    const foot = el('div', { class: 'modal-foot' });
    opts.buttons.forEach(b => foot.appendChild(el('button', {
      class: 'btn ' + (b.class || ''), onclick: b.onClick || closeModal, id: b.id || null
    }, b.text)));
    box.appendChild(foot);
  }
  root.classList.remove('hidden');
  if (opts.onOpen) setTimeout(() => opts.onOpen(body), 10);
  setTimeout(() => { const f = box.querySelector('input:not([type=hidden]),select,textarea'); if (f && opts.focus !== false) f.focus(); }, 60);
  return { root, box, body };
}
function closeModal() { $('#modal-root').classList.add('hidden'); $('#modal').innerHTML = ''; }
function confirmBox(msg, onYes, opts) {
  opts = opts || {};
  modal({
    title: opts.title || 'Xác nhận',
    body: '<p style="margin:0;font-size:14px">' + esc(msg).replace(/\n/g, '<br>') + '</p>' +
      (opts.warn ? '<div class="warnbox" style="margin-top:12px">' + esc(opts.warn) + '</div>' : ''),
    buttons: [
      { text: 'Huỷ', class: '', onClick: closeModal },
      { text: opts.yes || 'Đồng ý', class: opts.danger ? 'btn-danger' : 'btn-primary', onClick: () => { closeModal(); onYes(); } }
    ]
  });
}
function promptBox(title, fields, onSubmit, opts) {
  opts = opts || {};
  const form = el('div');
  fields.forEach(f => {
    if (f.type === 'html') { form.appendChild(el('div', { html: f.html })); return; }
    const lab = el('label', { class: 'field' }, [
      el('span', { html: esc(f.label) + (f.hint ? ' <span class="hint">' + esc(f.hint) + '</span>' : '') })
    ]);
    let inp;
    if (f.type === 'select') {
      inp = el('select', { id: 'f_' + f.name });
      (f.options || []).forEach(o => inp.appendChild(el('option', { value: o.value, selected: String(o.value) === String(f.value) ? 'selected' : null }, o.label)));
    } else if (f.type === 'textarea') {
      inp = el('textarea', { id: 'f_' + f.name, rows: f.rows || 3 }, f.value || '');
    } else if (f.type === 'checkbox') {
      inp = el('input', { type: 'checkbox', id: 'f_' + f.name, checked: f.value ? 'checked' : null });
      lab.className = 'check'; lab.innerHTML = '';
      lab.appendChild(inp); lab.appendChild(el('span', { text: f.label }));
      form.appendChild(lab); return;
    } else {
      inp = el('input', { type: f.type || 'text', id: 'f_' + f.name, value: f.value === undefined || f.value === null ? '' : f.value, placeholder: f.ph || '' });
      if (f.step) inp.step = f.step;
    }
    lab.appendChild(inp);
    form.appendChild(lab);
  });
  const get = () => {
    const o = {};
    fields.forEach(f => {
      if (f.type === 'html') return;
      const e = $('#f_' + f.name);
      if (!e) return;
      o[f.name] = f.type === 'checkbox' ? e.checked : e.value;
    });
    return o;
  };
  modal({
    title, body: form, size: opts.size,
    buttons: [{ text: 'Huỷ', onClick: closeModal },
    { text: opts.submit || 'Lưu', class: 'btn-primary', id: 'pb-save', onClick: async () => {
        const b = $('#pb-save'); b.disabled = true;
        try { const r = await onSubmit(get()); if (r !== false) closeModal(); }
        catch (e) { err(e.message); }
        finally { const b2 = $('#pb-save'); if (b2) b2.disabled = false; }
      } }]
  });
  return get;
}
function lightbox(src) {
  $('#lightbox-img').src = src;
  $('#lightbox').classList.remove('hidden');
}

/* ---------------- dinh tuyen ---------------- */
const ROUTES = {};
function route(name, fn) { ROUTES[name] = fn; }
function go(hash) { location.hash = hash; }
async function render() {
  const h = (location.hash || '#/dashboard').slice(2);
  const parts = h.split('/');
  const name = parts[0] || 'dashboard';
  const fn = ROUTES[name] || ROUTES.dashboard;
  $$('#nav a').forEach(a => a.classList.toggle('on', a.dataset.nav === name));
  const v = $('#view');
  v.innerHTML = '<div class="loading"><span class="spinner"></span> Đang tải…</div>';
  window.scrollTo(0, 0);
  try { await fn(v, parts.slice(1)); }
  catch (e) {
    v.innerHTML = '';
    v.appendChild(el('div', { class: 'card card-pad' }, [
      el('h3', { text: 'Không tải được trang' }),
      el('p', { class: 'muted', text: e.message }),
      el('button', { class: 'btn', onclick: () => render() }, 'Thử lại')
    ]));
  }
}
function crumb(t) { $('#crumb').textContent = t; document.title = t + ' · ' + (CTN.settings.app_short || 'ChamTN'); }

/* ---------------- SSE: log + tien trinh ---------------- */
function startSSE() {
  if (CTN.sse) { try { CTN.sse.close(); } catch (e) { } }
  const s = new EventSource('/api/stream');
  CTN.sse = s;
  s.onopen = () => { $('#conn').className = 'conn live'; $('#conn-txt').textContent = 'trực tuyến'; };
  s.onerror = () => {
    $('#conn').className = 'conn dead'; $('#conn-txt').textContent = 'mất kết nối';
    setTimeout(() => { if (CTN.user) startSSE(); }, 5000);
    try { s.close(); } catch (e) { }
  };
  s.addEventListener('log', e => { try { addLog(JSON.parse(e.data)); } catch (x) { } });
  s.addEventListener('job', e => {
    try {
      const j = JSON.parse(e.data);
      CTN.jobs[j.id] = j;
      renderJobFloat();
      if (typeof onJobUpdate === 'function') onJobUpdate(j);
    } catch (x) { }
  });
}
const LV_ORDER = { TRACE: 0, DEBUG: 1, INFO: 2, WARN: 3, ERROR: 4 };
function addLog(r) {
  CTN.logs.push(r);
  if (CTN.logs.length > 3000) CTN.logs.splice(0, 800);
  $('#con-count').textContent = CTN.logs.length;
  if (!CTN.consoleOpen) return;
  if (LV_ORDER[r.lv] < LV_ORDER[CTN.logLevel]) return;
  appendLogLine(r);
}
function appendLogLine(r) {
  const b = $('#console-body');
  const line = el('div', { class: 'logline' }, [
    el('span', { class: 't', text: r.t || '' }),
    el('span', { class: 'lv lv-' + r.lv, text: r.lv || '' }),
    el('span', { class: 'tg', text: r.tag || '' }),
    el('span', { class: 'm', text: r.msg || '' })
  ]);
  b.appendChild(line);
  while (b.children.length > 1200) b.removeChild(b.firstChild);
  if ($('#con-auto').checked) b.scrollTop = b.scrollHeight;
}
function redrawConsole() {
  const b = $('#console-body');
  b.innerHTML = '';
  CTN.logs.filter(r => LV_ORDER[r.lv] >= LV_ORDER[CTN.logLevel]).slice(-800).forEach(appendLogLine);
  b.scrollTop = b.scrollHeight;
}
function toggleConsole(force) {
  CTN.consoleOpen = force === undefined ? !CTN.consoleOpen : force;
  $('#console').classList.toggle('hidden', !CTN.consoleOpen);
  if (CTN.consoleOpen) redrawConsole();
}
function renderJobFloat() {
  const running = Object.values(CTN.jobs).filter(j => j.status === 'running' || j.status === 'queued');
  const box = $('#jobfloat');
  if (!running.length || location.hash.indexOf('#/exams/') === 0) { box.classList.add('hidden'); return; }
  const j = running[running.length - 1];
  box.classList.remove('hidden');
  box.innerHTML = '';
  box.appendChild(el('div', { class: 'jf-top' }, [
    el('span', { class: 'spinner' }), el('span', { text: 'Đang chấm: ' + (j.name || 'lô #' + j.id) })
  ]));
  const p = el('div', { class: 'progress' }); p.appendChild(el('div', { style: 'width:' + (j.percent || 0) + '%' }));
  box.appendChild(p);
  box.appendChild(el('div', { class: 'jf-sub' }, [
    el('span', { text: j.done + '/' + j.total + ' phiếu' + (j.failed ? ' · ' + j.failed + ' lỗi' : '') }),
    el('span', { text: j.eta ? 'còn ~' + secs(j.eta) : '' })
  ]));
  box.appendChild(el('div', { style: 'margin-top:8px;display:flex;gap:6px' }, [
    el('button', { class: 'btn btn-sm', onclick: () => go('#/exams/' + j.exam_id + '/grade') }, 'Xem chi tiết'),
    el('button', { class: 'btn btn-sm', onclick: () => api('/api/batches/' + j.id + '/cancel', { method: 'POST' }).then(() => warn('Đã yêu cầu dừng')) }, 'Dừng')
  ]));
}

/* ---------------- giao dien chung ---------------- */
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  localStorage.setItem('ctn_theme', t);
}
function applyBrand() {
  const s = CTN.settings || {};
  const nm = s.app_short || s.app_name || 'ChamTN';
  $('#brand-name').textContent = nm;
  $('#sb-copy').textContent = s.copyright || '';
  if (s.primary_color && /^#[0-9a-fA-F]{6}$/.test(s.primary_color)) {
    document.documentElement.style.setProperty('--brand', s.primary_color);
    document.documentElement.style.setProperty('--brand-d', shade(s.primary_color, -18));
  }
  document.title = nm;
}
function shade(hex, pct) {
  const n = parseInt(hex.slice(1), 16);
  let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const f = (1 + pct / 100);
  r = Math.max(0, Math.min(255, Math.round(r * f)));
  g = Math.max(0, Math.min(255, Math.round(g * f)));
  b = Math.max(0, Math.min(255, Math.round(b * f)));
  return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
}
function logoutLocal() {
  CTN.user = null;
  if (CTN.sse) { try { CTN.sse.close(); } catch (e) { } CTN.sse = null; }
  $('#app').classList.add('hidden');
  $('#login').classList.remove('hidden');
  $('#lg-pass').value = '';
}

/* ---------------- thanh phan dung lai ---------------- */
function statCard(k, v, d, cls) {
  return el('div', { class: 'stat ' + (cls || '') }, [
    el('div', { class: 'k', text: k }), el('div', { class: 'v', text: v }),
    d ? el('div', { class: 'd', text: d }) : null
  ]);
}
function card(title, bodyEl, actions, opts) {
  opts = opts || {};
  const c = el('div', { class: 'card' });
  if (title || actions) {
    const h = el('div', { class: 'card-head' }, [el('h3', { text: title || '' }), el('div', { class: 'grow' })]);
    (actions || []).forEach(a => h.appendChild(a));
    c.appendChild(h);
  }
  const b = el('div', { class: 'card-body' + (opts.tight ? ' tight' : '') });
  if (typeof bodyEl === 'string') b.innerHTML = bodyEl; else if (bodyEl) b.appendChild(bodyEl);
  c.appendChild(b);
  return c;
}
function tableEl(cols, rows, opts) {
  opts = opts || {};
  const wrap = el('div', { class: 'table-wrap' + (opts.short ? ' short' : '') });
  const t = el('table');
  const thead = el('thead');
  const tr = el('tr');
  cols.forEach(c => tr.appendChild(el('th', { style: c.w ? 'width:' + c.w : null, class: c.align === 'right' ? 'right' : (c.align === 'center' ? 'center' : null) }, c.t)));
  thead.appendChild(tr); t.appendChild(thead);
  const tb = el('tbody');
  if (!rows.length) {
    tb.appendChild(el('tr', {}, el('td', { colspan: cols.length }, el('div', { class: 'empty' }, [
      el('b', { text: opts.emptyTitle || 'Chưa có dữ liệu' }),
      el('span', { text: opts.emptyText || '' })
    ]))));
  }
  rows.forEach(r => {
    const row = el('tr', { class: r.__cls || null });
    if (r.__click) row.addEventListener('click', r.__click);
    if (r.__click) row.style.cursor = 'pointer';
    cols.forEach(c => {
      const td = el('td', { class: c.align === 'right' ? 'right' : (c.align === 'center' ? 'center' : null) });
      const v = c.render ? c.render(r) : r[c.k];
      if (v instanceof Node) td.appendChild(v);
      else if (c.html) td.innerHTML = v === undefined || v === null ? '' : v;
      else td.textContent = v === undefined || v === null ? '' : v;
      row.appendChild(td);
    });
    tb.appendChild(row);
  });
  t.appendChild(tb);
  wrap.appendChild(t);
  return wrap;
}
function tabsEl(items, active, onPick) {
  const t = el('div', { class: 'tabs' });
  items.forEach(i => t.appendChild(el('button', {
    class: i.id === active ? 'on' : '', onclick: () => onPick(i.id)
  }, i.label + (i.badge !== undefined && i.badge !== null && i.badge !== 0 ? '  (' + i.badge + ')' : ''))));
  return t;
}
function statusBadge(st, txt) {
  const m = { ok: 'ok', warn: 'warn', review: 'info', error: 'err', manual: 'brand', dup: 'warn' };
  return el('span', { class: 'badge ' + (m[st] || ''), text: txt || st });
}
function scoreEl(v, max) {
  const n = Number(v) || 0;
  const good = max ? n >= max / 2 : n >= 5;
  return el('span', { class: 'sc ' + (good ? 'hi' : 'lo'), text: sc2(n) });
}
function pager(page, per, total, onGo) {
  const pages = Math.max(1, Math.ceil(total / per));
  if (pages <= 1) return el('div');
  const w = el('div', { class: 'pager' });
  const mk = (t, p, dis) => el('button', { class: 'btn btn-sm' + (p === page ? ' btn-primary' : ''), disabled: dis ? 'disabled' : null, onclick: () => onGo(p) }, t);
  w.appendChild(mk('‹', page - 1, page <= 1));
  const from = Math.max(1, page - 2), to = Math.min(pages, from + 4);
  for (let p = from; p <= to; p++) w.appendChild(mk(String(p), p, false));
  w.appendChild(mk('›', page + 1, page >= pages));
  w.appendChild(el('span', { class: 'small muted', text: 'Trang ' + page + '/' + pages + ' · ' + num(total) + ' dòng' }));
  return w;
}
function download(url) {
  const a = el('a', { href: url, download: '' });
  document.body.appendChild(a); a.click(); a.remove();
}
async function copyText(t) {
  try { await navigator.clipboard.writeText(t); ok('Đã sao chép'); }
  catch (e) { warn('Không sao chép được'); }
}
