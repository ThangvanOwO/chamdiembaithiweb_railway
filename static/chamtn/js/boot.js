/* boot.js - khoi dong, dang nhap, gan su kien chung */
'use strict';

applyTheme(localStorage.getItem('ctn_theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

/* ---------------- dang nhap ---------------- */
$('#login-form').addEventListener('submit', async e => {
  e.preventDefault();
  const b = $('#lg-btn'), er = $('#lg-err');
  er.classList.add('hidden');
  b.disabled = true; b.textContent = 'Đang đăng nhập…';
  try {
    const r = await api('/api/login', {
      method: 'POST', noAuthRedirect: true,
      body: { username: $('#lg-user').value.trim(), password: $('#lg-pass').value }
    });
    CTN.user = r.user;
    await enterApp();
  } catch (x) {
    er.textContent = x.message; er.classList.remove('hidden');
    $('#lg-pass').select();
  } finally { b.disabled = false; b.textContent = 'Đăng nhập'; }
});
$('#lg-eye').addEventListener('click', () => {
  const i = $('#lg-pass');
  i.type = i.type === 'password' ? 'text' : 'password';
});

async function enterApp() {
  const me = await api('/api/me');
  CTN.user = me.user;
  CTN.settings = me.settings || {};
  applyBrand();
  $('#login').classList.add('hidden');
  $('#app').classList.remove('hidden');
  const ini = (CTN.user.full_name || CTN.user.username || '?').trim().split(/\s+/).map(w => w[0]).slice(-2).join('').toUpperCase();
  $('#user-ini').textContent = ini || '?';
  $('#dd-name').textContent = CTN.user.full_name || CTN.user.username;
  $('#dd-role').textContent = (CTN.user.role === 'admin' ? 'Quản trị viên' : 'Giáo viên') + ' · ' + CTN.user.username;
  $('#sb-user').textContent = CTN.user.full_name || CTN.user.username;
  if (me.version_line) {
    CTN.version = me.version_line;
    $('#sb-ver').textContent = me.version_line;
    $('#sb-ver').title = 'Phiên bản ' + (me.version || '') + ' · build ' + (me.build || '') + ' · biên dịch ' + (me.build_date || '');
  }
  $$('.admin-only').forEach(e => e.classList.toggle('hidden', CTN.user.role !== 'admin'));
  startSSE();
  try {
    const lg = await api('/api/logs?n=200');
    CTN.logs = lg.items || [];
    $('#con-count').textContent = CTN.logs.length;
  } catch (e) { }
  if (!location.hash || location.hash === '#') location.hash = '#/dashboard';
  await render();
  if (CTN.user.must_change) {
    setTimeout(() => {
      warn('Bạn đang dùng mật khẩu mặc định. Hãy đổi mật khẩu ngay!', 'Bảo mật');
      changePassword(true);
    }, 700);
  }
}

/* ---------------- đổi mật khẩu ---------------- */
function changePassword(force) {
  promptBox('Đổi mật khẩu', [
    { name: 'old', label: 'Mật khẩu hiện tại', type: 'password' },
    { name: 'n1', label: 'Mật khẩu mới', type: 'password', hint: '(tối thiểu 6 ký tự)' },
    { name: 'n2', label: 'Nhập lại mật khẩu mới', type: 'password' }
  ], async v => {
    if (v.n1.length < 6) { err('Mật khẩu mới phải từ 6 ký tự'); return false; }
    if (v.n1 !== v.n2) { err('Hai mật khẩu không khớp'); return false; }
    await api('/api/me/password', { method: 'POST', body: { old: v.old, new: v.n1 } });
    ok('Đã đổi mật khẩu');
    CTN.user.must_change = false;
  }, { submit: 'Đổi mật khẩu' });
}

/* ---------------- su kien chung ---------------- */
$('#btn-theme').addEventListener('click', () =>
  applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
$('#btn-console').addEventListener('click', () => toggleConsole());
$('#con-close').addEventListener('click', () => toggleConsole(false));
$('#con-clear').addEventListener('click', () => { CTN.logs = []; $('#console-body').innerHTML = ''; $('#con-count').textContent = '0'; });
$('#con-level').addEventListener('change', e => { CTN.logLevel = e.target.value; redrawConsole(); });
$('#btn-user').addEventListener('click', e => { e.stopPropagation(); $('#user-drop').classList.toggle('hidden'); });
document.addEventListener('click', () => $('#user-drop').classList.add('hidden'));
$('#user-drop').addEventListener('click', async e => {
  const a = e.target.dataset.act;
  if (!a) return;
  $('#user-drop').classList.add('hidden');
  if (a === 'passwd') changePassword();
  if (a === 'logout') {
    try { await api('/api/logout', { method: 'POST' }); } catch (x) { }
    logoutLocal();
    location.hash = '';
  }
});
$('#sb-open').addEventListener('click', () => $('#sidebar').classList.add('open'));
$('#sb-close').addEventListener('click', () => $('#sidebar').classList.remove('open'));
$('#nav').addEventListener('click', () => $('#sidebar').classList.remove('open'));
$('#modal-back').addEventListener('click', closeModal);
$('#lightbox').addEventListener('click', () => $('#lightbox').classList.add('hidden'));
window.addEventListener('hashchange', render);
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (!$('#lightbox').classList.contains('hidden')) $('#lightbox').classList.add('hidden');
    else if (!$('#modal-root').classList.contains('hidden')) closeModal();
    else if (CTN.consoleOpen) toggleConsole(false);
  }
  if (e.key === 'F2') { e.preventDefault(); toggleConsole(); }
});

/* ---------------- khoi dong ---------------- */
(async function init() {
  try {
    const h = await api('/api/health', { noAuthRedirect: true });
    if (h && h.app) {
      $('#login-title').textContent = h.app.length > 34 ? h.app.slice(0, 34) + '…' : h.app;
      document.title = h.app;
    }
    if (h && h.version_line) $('#login-copy').textContent = h.version_line;
  } catch (e) { }
  try {
    await api('/api/me', { noAuthRedirect: true });
    await enterApp();
  } catch (e) {
    $('#login').classList.remove('hidden');
    try {
      const s = await api('/api/health', { noAuthRedirect: true });
      $('#login-sub').textContent = 'Hệ thống chấm trắc nghiệm · ' + (s.db === 'mysql' ? 'MySQL' : 'SQLite');
    } catch (x) { }
  }
})();
