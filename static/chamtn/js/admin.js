/* admin.js - nguoi dung, cai dat, mau phieu, cham thu, nhat ky */
'use strict';

/* ==================================================== CHẤM THỬ ==================================================== */
route('try', async (v) => {
  crumb('Chấm thử');
  v.innerHTML = '';
  v.appendChild(el('div', { class: 'page-head' }, [
    el('div', {}, [el('h1', { text: 'Chấm thử một phiếu' }),
      el('div', { class: 'sub', text: 'Kiểm tra chất lượng ảnh và độ chính xác nhận dạng, không lưu vào kỳ thi nào.' })])
  ]));
  const tpls = await api('/api/templates');
  const left = el('div');
  const fi = el('input', { type: 'file', accept: 'image/*,.jpg,.jpeg,.png,.bmp,.tif,.tiff,.webp', class: 'hidden' });
  const drop = el('div', { class: 'drop' }, [
    el('div', { class: 'big', text: '◎' }),
    el('div', { html: '<b>Chọn hoặc kéo một ảnh phiếu vào đây</b>' }),
    el('div', { class: 'small muted', style: 'margin-top:4px', text: 'ảnh scan hoặc ảnh chụp bằng điện thoại đều được' })
  ]);
  drop.addEventListener('click', () => fi.click());
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', e => { e.preventDefault(); drop.classList.remove('over'); if (e.dataTransfer.files[0]) run(e.dataTransfer.files[0]); });
  fi.addEventListener('change', () => { if (fi.files[0]) run(fi.files[0]); });
  left.appendChild(drop);
  left.appendChild(fi);
  left.appendChild(el('div', { class: 'inline-fields', style: 'margin-top:14px' }, [
    el('label', { class: 'field' }, [el('span', { text: 'Mẫu phiếu' }),
      el('select', { id: 't-tpl' }, tpls.items.map(t => el('option', { value: t.id }, t.name)))]),
    el('label', { class: 'field' }, [el('span', { html: 'Ngưỡng “đã tô” <span class="hint">(mặc định 0.30)</span>' }), el('input', { id: 't-fill', type: 'number', step: '0.01', placeholder: '0.30' })]),
    el('label', { class: 'field' }, [el('span', { html: 'Chênh lệch tối thiểu <span class="hint">(mặc định 0.10)</span>' }), el('input', { id: 't-margin', type: 'number', step: '0.01', placeholder: '0.10' })]),
    el('label', { class: 'field' }, [el('span', { text: 'Loại nét in hồng' }),
      el('select', { id: 't-pink' }, [el('option', { value: '' }, 'Tự động'), el('option', { value: '1' }, 'Luôn bật'), el('option', { value: '0' }, 'Tắt')])])
  ]));
  v.appendChild(card('Ảnh phiếu', left));
  v.appendChild(el('div', { style: 'height:16px' }));
  v.appendChild(el('div', { id: 't-out' }));

  async function run(file) {
    const out = $('#t-out');
    out.innerHTML = '<div class="loading"><span class="spinner"></span> Đang nhận dạng…</div>';
    const fd = new FormData();
    fd.append('file', file);
    fd.append('template_id', $('#t-tpl').value);
    if ($('#t-fill').value) fd.append('fill_threshold', $('#t-fill').value);
    if ($('#t-margin').value) fd.append('margin', $('#t-margin').value);
    if ($('#t-pink').value) fd.append('pink_dropout', $('#t-pink').value);
    try {
      const r = await api('/api/try', { method: 'POST', body: fd });
      out.innerHTML = '';
      if (!r.ok) {
        out.appendChild(el('div', { class: 'errbox' }, [el('b', { text: 'Không đọc được phiếu: ' }), el('span', { text: r.error })]));
        return;
      }
      out.appendChild(el('div', { class: 'grid g5', style: 'margin-bottom:14px' }, [
        statCard('Chất lượng ảnh', Math.round(r.quality) + '/100', r.size, r.quality >= 70 ? 'g' : r.quality >= 45 ? 'w' : 'r'),
        statCard('Độ tin cậy', Math.round(r.confidence * 100) + '%', 'mức chắc chắn', r.confidence >= 0.8 ? 'g' : 'w'),
        statCard('Số báo danh', r.ans.sbd || '—', 'mã đề ' + (r.ans.made || '—'), 'b'),
        statCard('Thời gian', r.ms + ' ms', r.method === 'fiducial' ? 'định vị bằng ô mốc' : r.method, ''),
        statCard('Xoay ảnh', (r.rotation * 90) + '°', 'tự phát hiện', '')
      ]));
      if (r.warns && r.warns.length) {
        const ul = el('ul');
        r.warns.forEach(w => ul.appendChild(el('li', { text: w })));
        out.appendChild(el('div', { class: 'warnbox', style: 'margin-bottom:14px' }, [el('b', { text: 'Cảnh báo:' }), ul]));
      }
      const sp = el('div', { class: 'split' });
      const ans = el('div');
      const mk = (title, arr, cls, bycol, cw) => {
        if (!arr || !arr.length) return;
        ans.appendChild(el('h4', { style: 'margin-top:12px', text: title }));
        const g = el('div', { class: 'ansgrid' + (bycol ? ' bycol' : ''),
                              style: (bycol ? '--cw:' + cw : cls) || '' });
        arr.forEach((x, i) => g.appendChild(el('div', { class: 'ansitem ' + (x && x !== '-'.repeat(4) ? '' : 'b') }, [
          el('span', { class: 'n', text: (i + 1) + '.' }),
          el('span', { class: 'v', text: (x || '—').replace(/D/g, 'Đ') })
        ])));
        ans.appendChild(g);
      };
      mk('PHẦN I', r.ans.p1, '', true, '92px');
      mk('PHẦN II', r.ans.p2, 'grid-template-columns:repeat(auto-fill,minmax(104px,1fr))');
      mk('PHẦN III', r.ans.p3, 'grid-template-columns:repeat(auto-fill,minmax(104px,1fr))');
      ans.appendChild(el('div', { class: 'kv', style: 'margin-top:14px' }, [
        el('dt', { text: 'Tương phản' }), el('dd', { text: sc2(r.contrast) }),
        el('dt', { text: 'Độ nét' }), el('dd', { text: sc2(r.sharpness) }),
        el('dt', { text: 'Tách biệt ô tô' }), el('dd', { text: sc2(r.separation) }),
        el('dt', { text: 'Khớp lưới ô tròn' }), el('dd', { text: sc2(r.grid) }),
        el('dt', { text: 'Kênh đọc vết bút' }), el('dd', { text: r.mark_channel === 'loai-hong' ? 'loại nét in hồng' : 'kênh mực (min RGB)' })
      ]));
      sp.appendChild(card('Kết quả đọc được', ans));
      if (r.preview) sp.appendChild(card('Ảnh đã chỉnh + đánh dấu ô đã tô',
        el('div', { class: 'imgbox' }, el('img', { src: r.preview, onclick: () => lightbox(r.preview) }))));
      out.appendChild(sp);
    } catch (e) { out.innerHTML = ''; out.appendChild(el('div', { class: 'errbox', text: e.message })); }
  }
});

/* ==================================================== MẪU PHIẾU ==================================================== */
route('templates', async (v) => {
  crumb('Mẫu phiếu');
  const r = await api('/api/templates');
  v.innerHTML = '';
  v.appendChild(el('div', { class: 'page-head' }, [
    el('div', {}, [el('h1', { text: 'Mẫu phiếu trả lời' }),
      el('div', { class: 'sub', text: 'Toạ độ từng ô tròn được lấy chính xác từ mẫu phiếu của Bộ GD&ĐT (CV 1239/BGDĐT-QLCL).' })])
  ]));
  const st = el('div', { class: 'stack' });
  r.items.forEach(t => {
    const c = t.counts || {};
    const body = el('div', {}, [
      el('div', { class: 'kv' }, [
        el('dt', { text: 'Mã mẫu' }), el('dd', { class: 'mono', text: t.id }),
        el('dt', { text: 'Phần I' }), el('dd', { text: c.p1 + ' câu × 4 lựa chọn' }),
        el('dt', { text: 'Phần II' }), el('dd', { text: c.p2 + ' câu × 4 ý Đúng/Sai' }),
        el('dt', { text: 'Phần III' }), el('dd', { text: c.p3 + ' câu trả lời ngắn (4 ký tự)' }),
        el('dt', { text: 'Số báo danh' }), el('dd', { text: c.sbd + ' chữ số' }),
        el('dt', { text: 'Mã đề' }), el('dd', { text: c.made + ' chữ số' }),
        el('dt', { text: 'Tổng số ô tròn' }), el('dd', { text: num(t.n_bubbles) }),
        el('dt', { text: 'Cập nhật' }), el('dd', { text: t.updated_at_txt || '—' })
      ]),
      el('div', { class: 'row', style: 'margin-top:14px' }, [
        el('button', { class: 'btn btn-sm btn-primary', onclick: () => window.open('/api/templates/' + t.id + '/blank.pdf?count=1', '_blank') }, 'Xem/In 1 phiếu trống'),
        el('button', { class: 'btn btn-sm', onclick: () => printBlank(t.id) }, 'In nhiều phiếu…'),
        el('button', { class: 'btn btn-sm btn-ghost', onclick: () => window.open('/api/templates/' + t.id, '_blank') }, 'Xem JSON toạ độ')
      ])
    ]);
    st.appendChild(card(t.name + (t.builtin ? '  ·  mặc định' : ''), body));
  });
  st.appendChild(card('Lưu ý khi in phiếu', el('div', { class: 'small muted' }, [
    el('p', { style: 'margin:0 0 6px', html: '• In ở tỉ lệ <b>100%</b> (không “fit to page”), giấy A4, mực đen rõ. 4 ô vuông đen ở 4 góc là mốc định vị – <b>không được che, gấp hoặc làm mờ</b>.' }),
    el('p', { style: 'margin:0 0 6px', html: '• Học sinh tô bằng bút chì 2B hoặc bút mực đậm, tô kín ô tròn.' }),
    el('p', { style: 'margin:0', html: '• Khi chụp bằng điện thoại: đặt phiếu phẳng, thấy đủ 4 góc, đủ sáng, tránh bóng tay. Hệ thống tự chỉnh nghiêng, phối cảnh và xoay ảnh.' })
  ])));
  v.appendChild(st);
  function printBlank(id) {
    promptBox('In phiếu trống', [
      { name: 'count', label: 'Số phiếu', type: 'number', value: 30, hint: '(tối đa 500)' }
    ], v2 => { window.open('/api/templates/' + id + '/blank.pdf?count=' + (parseInt(v2.count, 10) || 1) + '&dl=1', '_blank'); });
  }
});

/* ==================================================== NGƯỜI DÙNG ==================================================== */
route('users', async (v) => {
  crumb('Người dùng');
  const r = await api('/api/users');
  const ex = await api('/api/exams');
  const cls = await api('/api/classes');
  v.innerHTML = '';
  v.appendChild(el('div', { class: 'page-head' }, [
    el('div', {}, [el('h1', { text: 'Người dùng & phân quyền' }),
      el('div', { class: 'sub', text: r.items.length + ' tài khoản' })]),
    el('div', { class: 'grow' }),
    el('button', { class: 'btn btn-primary', onclick: () => editUser(null) }, '+ Tài khoản')
  ]));
  const rows = r.items.map(u => ({
    user: el('div', {}, [el('b', { text: u.username }), el('div', { class: 'tiny muted', text: u.full_name || '' })]),
    role: el('span', { class: 'badge ' + (u.role === 'admin' ? 'brand' : ''), text: u.role === 'admin' ? 'Quản trị' : 'Giáo viên' }),
    contact: el('span', { class: 'tiny muted', text: [u.email, u.phone].filter(Boolean).join(' · ') || '—' }),
    active: u.active ? el('span', { class: 'badge ok', text: 'hoạt động' }) : el('span', { class: 'badge err', text: 'đã khoá' }),
    ex: num(u.n_exams),
    last: el('span', { class: 'tiny muted', text: u.last_login_txt || 'chưa đăng nhập' }),
    act: el('div', { class: 'row tight' }, [
      el('button', { class: 'btn btn-sm', onclick: () => editUser(u) }, 'Sửa'),
      u.role !== 'admin' ? el('button', { class: 'btn btn-sm', onclick: () => assign(u) }, 'Phân công') : null,
      u.id !== CTN.user.id ? el('button', {
        class: 'btn btn-sm btn-ghost', onclick: () => confirmBox('Xoá tài khoản “' + u.username + '”?', async () => {
          await api('/api/users/' + u.id, { method: 'DELETE' }); ok('Đã xoá'); render();
        }, { danger: true })
      }, '🗑') : null
    ])
  }));
  v.appendChild(card(null, tableEl([
    { t: 'Tài khoản', k: 'user' }, { t: 'Vai trò', k: 'role', w: '110px' },
    { t: 'Liên hệ', k: 'contact', w: '210px' }, { t: 'Trạng thái', k: 'active', w: '110px' },
    { t: 'Kỳ thi', k: 'ex', w: '80px', align: 'right' },
    { t: 'Đăng nhập cuối', k: 'last', w: '150px' }, { t: '', k: 'act', w: '210px' }
  ], rows), null, { tight: true }));
  v.appendChild(el('div', { style: 'height:14px' }));
  v.appendChild(card('Về phân quyền', el('div', { class: 'small muted' }, [
    el('p', { style: 'margin:0 0 5px', html: '<b>Quản trị viên:</b> toàn quyền – quản lý tài khoản, cài đặt hệ thống, cơ sở dữ liệu, xem mọi kỳ thi.' }),
    el('p', { style: 'margin:0', html: '<b>Giáo viên:</b> chỉ thấy kỳ thi do mình tạo hoặc được phân công, và lớp mình chủ nhiệm/được phân công.' })
  ])));

  function editUser(u) {
    promptBox(u ? 'Sửa tài khoản' : 'Thêm tài khoản', [
      { name: 'username', label: 'Tên đăng nhập *', value: u ? u.username : '', hint: u ? '(không đổi được)' : '(chữ, số, . _ -)' },
      { name: 'full_name', label: 'Họ và tên', value: u ? u.full_name : '' },
      { name: 'password', label: u ? 'Đặt lại mật khẩu' : 'Mật khẩu *', type: 'password', hint: u ? '(để trống nếu không đổi)' : '(tối thiểu 6 ký tự)' },
      { name: 'role', label: 'Vai trò', type: 'select', value: u ? u.role : 'teacher', options: [{ value: 'teacher', label: 'Giáo viên' }, { value: 'admin', label: 'Quản trị viên' }] },
      { name: 'email', label: 'Email', value: u ? u.email : '' },
      { name: 'phone', label: 'Điện thoại', value: u ? u.phone : '' },
      { name: 'note', label: 'Ghi chú', value: u ? u.note : '' },
      { name: 'active', label: 'Cho phép đăng nhập', type: 'checkbox', value: u ? u.active : true }
    ], async v2 => {
      if (u) { if ($('#f_username')) $('#f_username').disabled = true; await api('/api/users/' + u.id, { method: 'PUT', body: v2 }); }
      else await api('/api/users', { method: 'POST', body: v2 });
      ok('Đã lưu'); render();
    });
    if (u) setTimeout(() => { const e = $('#f_username'); if (e) e.disabled = true; }, 50);
  }
  async function assign(u) {
    const cur = await api('/api/assignments/' + u.id);
    const exSet = new Set(cur.exams || []), clSet = new Set(cur.classes || []);
    const box = el('div');
    box.appendChild(el('h4', { text: 'Kỳ thi được phân công' }));
    const c1 = el('div', { class: 'chips' });
    ex.items.forEach(e => {
      const ch = el('div', { class: 'chip' + (exSet.has(e.id) ? ' on' : ''), onclick: () => { ch.classList.toggle('on'); exSet.has(e.id) ? exSet.delete(e.id) : exSet.add(e.id); } }, e.name);
      c1.appendChild(ch);
    });
    box.appendChild(c1);
    box.appendChild(el('h4', { style: 'margin-top:14px', text: 'Lớp được phân công' }));
    const c2 = el('div', { class: 'chips' });
    cls.items.forEach(c => {
      const ch = el('div', { class: 'chip' + (clSet.has(c.id) ? ' on' : ''), onclick: () => { ch.classList.toggle('on'); clSet.has(c.id) ? clSet.delete(c.id) : clSet.add(c.id); } }, c.name || c.code);
      c2.appendChild(ch);
    });
    box.appendChild(c2);
    modal({
      title: 'Phân công cho ' + u.username, body: box, size: 'wide',
      buttons: [{ text: 'Huỷ', onClick: closeModal }, {
        text: 'Lưu', class: 'btn-primary', onClick: async () => {
          await api('/api/assignments/' + u.id, { method: 'PUT', body: { exams: Array.from(exSet), classes: Array.from(clSet) } });
          ok('Đã lưu phân công'); closeModal();
        }
      }]
    });
  }
});

/* ==================================================== CÀI ĐẶT ==================================================== */
route('settings', async (v) => {
  crumb('Cài đặt');
  const s = (await api('/api/settings')).settings;
  const dbc = await api('/api/dbconfig');
  v.innerHTML = '';
  v.appendChild(el('div', { class: 'page-head' }, [el('div', {}, [el('h1', { text: 'Cài đặt hệ thống' })])]));
  const st = el('div', { class: 'stack' });

  // thuong hieu
  const br = el('div');
  br.appendChild(el('div', { class: 'inline-fields' }, [
    fld('app_name', 'Tên ứng dụng (đầy đủ)', s.app_name),
    fld('app_short', 'Tên ngắn (hiện ở menu)', s.app_short),
    fld('org_name', 'Tên đơn vị / trường', s.org_name),
    fld('primary_color', 'Màu chủ đạo', s.primary_color, '(mã hex, VD #2563eb)')
  ]));
  br.appendChild(el('label', { class: 'field' }, [el('span', { text: 'Dòng bản quyền (hiện trên giao diện và các file xuất ra)' }),
    el('input', { id: 'set_copyright', value: s.copyright || '' })]));
  br.appendChild(el('label', { class: 'field' }, [el('span', { text: 'Ghi chú chân trang (tuỳ chọn)' }),
    el('input', { id: 'set_footer_note', value: s.footer_note || '' })]));
  st.appendChild(card('Thương hiệu & bản quyền', br, [
    el('button', { class: 'btn btn-primary btn-sm', onclick: () => save(['app_name', 'app_short', 'org_name', 'primary_color', 'copyright', 'footer_note']) }, 'Lưu')
  ]));

  // nhan dang mac dinh
  const om = el('div');
  om.appendChild(el('p', { class: 'small muted', style: 'margin:0 0 12px', text: 'Áp dụng cho mọi kỳ thi chưa có thiết lập riêng.' }));
  om.appendChild(el('div', { class: 'inline-fields' }, [
    fld('omr_fill_threshold', 'Ngưỡng nhận “đã tô”', s.omr_fill_threshold, '(0.10 – 0.60)'),
    fld('omr_margin', 'Chênh lệch tối thiểu', s.omr_margin, '(0.03 – 0.30)'),
    fld('omr_bubble_shrink', 'Tỉ lệ vùng lấy mẫu', s.omr_bubble_shrink, '(0.5 – 0.95)'),
    fld('omr_search_radius', 'Bán kính dò lệch (px)', s.omr_search_radius),
    fld('omr_jpeg_quality', 'Chất lượng ảnh overlay', s.omr_jpeg_quality, '(50 – 95)'),
    el('label', { class: 'field' }, [el('span', { text: 'Loại nét in hồng' }),
      el('select', { id: 'set_omr_pink_dropout' }, [
        el('option', { value: '2', selected: s.omr_pink_dropout == 2 ? 'selected' : null }, 'Tự động'),
        el('option', { value: '1', selected: s.omr_pink_dropout == 1 ? 'selected' : null }, 'Luôn bật'),
        el('option', { value: '0', selected: s.omr_pink_dropout == 0 ? 'selected' : null }, 'Tắt')])]),
    el('label', { class: 'field' }, [el('span', { text: 'Mức ghi nhật ký' }),
      el('select', { id: 'set_log_level' }, ['trace', 'debug', 'info', 'warn', 'error'].map(l =>
        el('option', { value: l, selected: (s.log_level || 'info') === l ? 'selected' : null }, l.toUpperCase())))]),
    fld('session_days', 'Số ngày giữ đăng nhập', s.session_days)
  ]));
  om.appendChild(el('label', { class: 'check' }, [
    el('input', { type: 'checkbox', id: 'set_omr_detect_rotation', checked: s.omr_detect_rotation == 1 ? 'checked' : null }),
    el('span', { text: 'Tự động phát hiện & xoay ảnh' })]));
  om.appendChild(el('label', { class: 'check' }, [
    el('input', { type: 'checkbox', id: 'set_auto_overlay', checked: s.auto_overlay == 1 ? 'checked' : null }),
    el('span', { text: 'Tạo ảnh overlay đúng/sai khi chấm (tắt sẽ chấm nhanh hơn nhưng không xem được đánh dấu)' })]));
  st.appendChild(card('Nhận dạng & hệ thống', om, [
    el('button', { class: 'btn btn-primary btn-sm', onclick: () => save(['omr_fill_threshold', 'omr_margin', 'omr_bubble_shrink', 'omr_search_radius', 'omr_jpeg_quality', 'omr_pink_dropout', 'log_level', 'session_days', 'omr_detect_rotation', 'auto_overlay']) }, 'Lưu')
  ]));

  // CSDL
  const dj = dbc.config || {};
  const dbx = el('div');
  dbx.appendChild(el('div', { class: dbc.active === 'mysql' ? 'infobox' : 'okbox', style: 'margin-bottom:14px' }, [
    el('b', { text: 'Đang dùng: ' }),
    el('span', { text: dbc.active === 'mysql' ? ('MySQL ' + dj.user + '@' + dj.host + ':' + dj.port + '/' + dj.dbname) : ('SQLite – tệp duy nhất: ' + dj.sqlite_path + (dbc.sqlite_size > 0 ? ' (' + bytes(dbc.sqlite_size) + ')' : '')) })
  ]));
  const kindSel = el('select', { id: 'db_kind', onchange: () => tog() }, [
    el('option', { value: 'sqlite', selected: dbc.active === 'sqlite' ? 'selected' : null }, 'SQLite – một tệp duy nhất (đơn giản, không cần cài gì)'),
    el('option', { value: 'mysql', selected: dbc.active === 'mysql' ? 'selected' : null }, 'MySQL / MariaDB (nhiều người dùng, dữ liệu lớn)')
  ]);
  dbx.appendChild(el('label', { class: 'field' }, [el('span', { text: 'Loại cơ sở dữ liệu' }), kindSel]));
  dbx.appendChild(el('div', { id: 'db-sqlite' }, [fld('db_sqlite_path', 'Đường dẫn tệp SQLite', dj.sqlite_path, '(sẽ tự tạo nếu chưa có)')]));
  dbx.appendChild(el('div', { id: 'db-mysql', class: 'inline-fields' }, [
    fld('db_host', 'Máy chủ', dj.host), fld('db_port', 'Cổng', dj.port),
    fld('db_user', 'Tài khoản', dj.user),
    el('label', { class: 'field' }, [el('span', { text: 'Mật khẩu' }), el('input', { type: 'password', id: 'set_db_pass', value: dj.pass || '' })]),
    fld('db_dbname', 'Tên cơ sở dữ liệu', dj.dbname, '(tự tạo nếu chưa có)'),
    fld('db_pool', 'Số kết nối đồng thời', dj.pool_size)
  ]));
  dbx.appendChild(el('div', { id: 'db-test', style: 'margin-top:10px' }));
  const tog = () => {
    const my = $('#db_kind').value === 'mysql';
    $('#db-mysql').classList.toggle('hidden', !my);
    $('#db-sqlite').classList.toggle('hidden', my);
  };
  st.appendChild(card('Cơ sở dữ liệu', dbx, [
    el('button', { class: 'btn btn-sm', onclick: testDb }, 'Kiểm tra kết nối'),
    el('button', { class: 'btn btn-primary btn-sm', onclick: saveDb }, 'Lưu cấu hình'),
    dbc.active === 'sqlite' ? el('button', { class: 'btn btn-sm', onclick: () => download('/api/dbconfig/download') }, '⭳ Tải bản sao lưu') : null
  ]));
  setTimeout(tog, 10);

  // bao tri
  const mt = el('div', { class: 'row' }, [
    el('button', { class: 'btn btn-sm', onclick: () => maint('vacuum') }, 'Tối ưu cơ sở dữ liệu'),
    el('button', { class: 'btn btn-sm', onclick: () => maint('purge-tmp') }, 'Xoá tệp tạm'),
    el('button', { class: 'btn btn-sm', onclick: () => maint('purge-sessions') }, 'Xoá phiên hết hạn'),
    el('button', { class: 'btn btn-sm', onclick: () => maint('reload-settings') }, 'Tải lại cài đặt')
  ]);
  st.appendChild(card('Bảo trì', el('div', {}, [
    el('p', { class: 'small muted', style: 'margin:0 0 10px', text: 'Thư mục dữ liệu: ' + dbc.data_dir + ' · Tệp cấu hình: ' + dbc.config_file }),
    mt
  ])));
  v.appendChild(st);

  function fld(id, label, val, hint) {
    return el('label', { class: 'field' }, [
      el('span', { html: esc(label) + (hint ? ' <span class="hint">' + esc(hint) + '</span>' : '') }),
      el('input', { id: 'set_' + id, value: val === undefined || val === null ? '' : val })
    ]);
  }
  async function save(keys) {
    const body = {};
    keys.forEach(k => {
      const e = $('#set_' + k);
      if (!e) return;
      body[k] = e.type === 'checkbox' ? (e.checked ? '1' : '0') : e.value;
    });
    try {
      const r = await api('/api/settings', { method: 'PUT', body });
      CTN.settings = r.settings;
      applyBrand();
      ok('Đã lưu cài đặt');
    } catch (e) { err(e.message); }
  }
  function dbBody() {
    return {
      kind: $('#db_kind').value, sqlite_path: $('#set_db_sqlite_path').value,
      host: $('#set_db_host').value, port: parseInt($('#set_db_port').value, 10) || 3306,
      user: $('#set_db_user').value, pass: $('#set_db_pass').value,
      dbname: $('#set_db_dbname').value, pool_size: parseInt($('#set_db_pool').value, 10) || 6
    };
  }
  async function testDb() {
    const o = $('#db-test');
    o.innerHTML = '<span class="spinner"></span> Đang kiểm tra…';
    try { const r = await api('/api/dbconfig/test', { method: 'POST', body: dbBody() }); o.innerHTML = ''; o.appendChild(el('div', { class: 'okbox', text: 'Kết nối thành công · ' + r.info })); }
    catch (e) { o.innerHTML = ''; o.appendChild(el('div', { class: 'errbox', text: e.message })); }
  }
  async function saveDb() {
    confirmBox('Lưu cấu hình cơ sở dữ liệu mới?', async () => {
      try {
        const r = await api('/api/dbconfig', { method: 'PUT', body: dbBody() });
        modal({
          title: 'Đã lưu cấu hình',
          body: '<div class="okbox">Kết nối thử thành công: ' + esc(r.info) + '</div>' +
            '<p style="margin-top:12px">Cấu hình đã được ghi vào tệp <b>' + esc(dbc.config_file) + '</b>. ' +
            'Hãy <b>khởi động lại ứng dụng</b> để bắt đầu dùng cơ sở dữ liệu mới.</p>' +
            '<p class="small muted">Lưu ý: dữ liệu không tự chuyển giữa hai loại CSDL. Nếu cần chuyển, hãy xuất Excel trước rồi nhập lại.</p>',
          buttons: [{ text: 'Đã hiểu', class: 'btn-primary', onClick: closeModal }]
        });
      } catch (e) { err(e.message); }
    });
  }
  async function maint(what) {
    try { const r = await api('/api/maintenance/' + what, { method: 'POST' }); ok(r.msg || 'Xong'); }
    catch (e) { err(e.message); }
  }
});

/* ==================================================== NHẬT KÝ ==================================================== */
route('audit', async (v) => {
  crumb('Nhật ký hệ thống');
  const r = await api('/api/audit?limit=500');
  v.innerHTML = '';
  v.appendChild(el('div', { class: 'page-head' }, [
    el('div', {}, [el('h1', { text: 'Nhật ký hoạt động' }),
      el('div', { class: 'sub', text: '500 hoạt động gần nhất (giờ Việt Nam)' })]),
    el('div', { class: 'grow' }),
    el('button', { class: 'btn', onclick: () => toggleConsole(true) }, 'Nhật ký kỹ thuật (log)')
  ]));
  const ACT = {
    login: 'Đăng nhập', logout: 'Đăng xuất', change_password: 'Đổi mật khẩu',
    create_user: 'Tạo tài khoản', update_user: 'Sửa tài khoản', delete_user: 'Xoá tài khoản',
    create_class: 'Tạo lớp', update_class: 'Sửa lớp', delete_class: 'Xoá lớp',
    create_student: 'Thêm học sinh', update_student: 'Sửa học sinh', delete_student: 'Xoá học sinh',
    import_students: 'Nhập học sinh', bulk_students: 'Xử lý nhiều học sinh',
    create_exam: 'Tạo kỳ thi', update_exam: 'Sửa kỳ thi', delete_exam: 'Xoá kỳ thi',
    save_keys: 'Lưu đáp án', build_candidates: 'Lập danh sách thi',
    grade_batch: 'Chấm lô ảnh', cancel_batch: 'Dừng lô', delete_batch: 'Xoá lô',
    edit_sheet: 'Sửa tay phiếu', delete_sheet: 'Xoá phiếu', regrade_exam: 'Chấm lại kỳ thi',
    export: 'Xuất dữ liệu', update_settings: 'Đổi cài đặt', update_dbconfig: 'Đổi cấu hình CSDL',
    download_db: 'Tải sao lưu CSDL', maintenance: 'Bảo trì', assign: 'Phân công', save_template: 'Lưu mẫu phiếu'
  };
  const rows = r.items.map(a => ({
    at: el('span', { class: 'tiny', text: a.at_txt }),
    user: el('b', { text: a.username || '—' }),
    act: ACT[a.action] || a.action,
    target: el('span', { class: 'tiny', text: a.target || '' }),
    detail: el('span', { class: 'tiny muted', text: a.detail || '' }),
    ip: el('span', { class: 'tiny mono muted', text: a.ip || '' })
  }));
  v.appendChild(card(null, tableEl([
    { t: 'Thời điểm', k: 'at', w: '150px' }, { t: 'Người dùng', k: 'user', w: '130px' },
    { t: 'Hoạt động', k: 'act', w: '170px' }, { t: 'Đối tượng', k: 'target', w: '190px' },
    { t: 'Chi tiết', k: 'detail' }, { t: 'IP', k: 'ip', w: '120px' }
  ], rows), null, { tight: true }));
});
