/* data.js - lop hoc & hoc sinh */
'use strict';

let ST = { page: 1, per: 50, q: '', cls: 0 };

route('students', async (v) => {
  crumb('Lớp & học sinh');
  const cls = await api('/api/classes');
  v.innerHTML = '';
  v.appendChild(el('div', { class: 'page-head' }, [
    el('div', {}, [el('h1', { text: 'Lớp & học sinh' }),
      el('div', { class: 'sub', text: cls.items.length + ' lớp' })]),
    el('div', { class: 'grow' }),
    el('button', { class: 'btn', onclick: () => window.open('/api/students/template', '_blank') }, '⭳ File mẫu'),
    el('button', { class: 'btn', onclick: importStudents }, '⭱ Nhập từ Excel/CSV'),
    el('button', { class: 'btn', onclick: () => editClass(null) }, '+ Lớp'),
    el('button', { class: 'btn btn-primary', onclick: () => editStudent(null, cls.items) }, '+ Học sinh')
  ]));

  const wrap = el('div', { class: 'split', style: 'grid-template-columns:290px minmax(0,1fr)' });
  // danh sach lop
  const cl = el('div');
  const mkC = (c) => el('div', {
    class: 'row', style: 'padding:8px 4px;border-bottom:1px solid var(--line);cursor:pointer' +
      (ST.cls === (c ? c.id : 0) ? ';background:var(--panel3);border-radius:8px' : ''),
    onclick: () => { ST.cls = c ? c.id : 0; ST.page = 1; render(); }
  }, [
    el('div', { style: 'flex:1;min-width:0' }, [
      el('b', { text: c ? (c.name || c.code) : 'Tất cả học sinh' }),
      el('div', { class: 'tiny muted', text: c ? [c.grade, c.school_year, c.teacher ? 'GV: ' + c.teacher : ''].filter(Boolean).join(' · ') : 'không lọc theo lớp' })
    ]),
    el('span', { class: 'badge', text: c ? c.n_students : '' }),
    c ? el('button', { class: 'btn btn-sm btn-ghost', onclick: e => { e.stopPropagation(); editClass(c); } }, '✎') : null,
    c ? el('button', {
      class: 'btn btn-sm btn-ghost', onclick: e => {
        e.stopPropagation();
        confirmBox('Xoá lớp “' + (c.name || c.code) + '”?', async () => {
          try { await api('/api/classes/' + c.id, { method: 'DELETE' }); ok('Đã xoá'); render(); }
          catch (x) {
            confirmBox(x.message + '\n\nVẫn xoá lớp và bỏ gán lớp cho học sinh?', async () => {
              await api('/api/classes/' + c.id + '?force=1', { method: 'DELETE' }); ok('Đã xoá'); render();
            }, { danger: true });
          }
        }, { danger: true });
      }
    }, '🗑') : null
  ]);
  cl.appendChild(mkC(null));
  cls.items.forEach(c => cl.appendChild(mkC(c)));
  wrap.appendChild(card('Lớp học', cl));

  const right = el('div', { id: 'st-box' });
  wrap.appendChild(right);
  v.appendChild(wrap);
  await loadStudents(cls.items);
});

async function loadStudents(classes) {
  const box = $('#st-box');
  box.innerHTML = '<div class="loading"><span class="spinner"></span></div>';
  const r = await api('/api/students?page=' + ST.page + '&per=' + ST.per + '&q=' + encodeURIComponent(ST.q) + '&class_id=' + ST.cls);
  const rows = r.items.map(s => ({
    code: el('span', { class: 'mono tiny', text: s.code || '—' }),
    name: el('b', { text: s.full_name }),
    dob: s.dob_txt || '—', gender: s.gender || '—',
    cls: s.class_name || '—',
    sbd: el('span', { class: 'mono', text: s.sbd || '—' }),
    contact: el('span', { class: 'tiny muted', text: [s.email, s.phone].filter(Boolean).join(' · ') }),
    act: el('div', { class: 'row tight' }, [
      el('button', { class: 'btn btn-sm btn-ghost', onclick: () => editStudent(s, classes) }, '✎'),
      el('button', {
        class: 'btn btn-sm btn-ghost', onclick: () => confirmBox('Xoá học sinh “' + s.full_name + '”?', async () => {
          await api('/api/students/' + s.id, { method: 'DELETE' }); ok('Đã xoá'); loadStudents(classes);
        }, { danger: true })
      }, '🗑')
    ])
  }));
  box.innerHTML = '';
  box.appendChild(card(null, el('div', {}, [
    el('div', { class: 'row', style: 'padding:0 0 12px' }, [
      el('input', { type: 'search', value: ST.q, placeholder: 'Tìm tên / mã HS / SBD…', style: 'max-width:260px', oninput: debounce(e => { ST.q = e.target.value; ST.page = 1; loadStudents(classes); }, 350) }),
      el('div', { class: 'grow' }),
      el('span', { class: 'small muted', text: num(r.total) + ' học sinh' })
    ]),
    tableEl([
      { t: 'Mã HS', k: 'code', w: '90px' }, { t: 'Họ và tên', k: 'name' },
      { t: 'Ngày sinh', k: 'dob', w: '100px' }, { t: 'Giới tính', k: 'gender', w: '85px' },
      { t: 'Lớp', k: 'cls', w: '110px' }, { t: 'SBD', k: 'sbd', w: '110px' },
      { t: 'Liên hệ', k: 'contact', w: '180px' }, { t: '', k: 'act', w: '90px' }
    ], rows, { emptyTitle: 'Chưa có học sinh', emptyText: 'Thêm tay hoặc nhập từ file Excel/CSV.' }),
    pager(ST.page, ST.per, r.total, p => { ST.page = p; loadStudents(classes); })
  ])));
}

function editClass(c) {
  promptBox(c ? 'Sửa lớp' : 'Thêm lớp', [
    { name: 'code', label: 'Mã lớp', value: c ? c.code : '' },
    { name: 'name', label: 'Tên lớp *', value: c ? c.name : '', ph: 'VD: 12A1' },
    { name: 'grade', label: 'Khối', value: c ? c.grade : '', ph: 'VD: 12' },
    { name: 'school_year', label: 'Năm học', value: c ? c.school_year : '', ph: 'VD: 2025-2026' },
    { name: 'note', label: 'Ghi chú', value: c ? c.note : '' }
  ], async v => {
    if (!v.name.trim()) { err('Nhập tên lớp'); return false; }
    if (c) await api('/api/classes/' + c.id, { method: 'PUT', body: Object.assign({ teacher_id: c.teacher_id }, v) });
    else await api('/api/classes', { method: 'POST', body: v });
    ok('Đã lưu'); render();
  });
}
function editStudent(s, classes) {
  promptBox(s ? 'Sửa học sinh' : 'Thêm học sinh', [
    { name: 'full_name', label: 'Họ và tên *', value: s ? s.full_name : '' },
    { name: 'code', label: 'Mã học sinh', value: s ? s.code : '' },
    { name: 'dob_txt', label: 'Ngày sinh', value: s ? s.dob_txt : '', hint: '(dd/mm/yyyy)' },
    { name: 'gender', label: 'Giới tính', type: 'select', value: s ? s.gender : '', options: [{ value: '', label: '—' }, { value: 'Nam', label: 'Nam' }, { value: 'Nữ', label: 'Nữ' }] },
    { name: 'class_id', label: 'Lớp', type: 'select', value: s ? s.class_id : ST.cls, options: [{ value: 0, label: '— Chưa gán —' }].concat((classes || []).map(c => ({ value: c.id, label: c.name || c.code }))) },
    { name: 'sbd', label: 'Số báo danh', value: s ? s.sbd : '', hint: '(dùng để khớp phiếu)' },
    { name: 'email', label: 'Email', value: s ? s.email : '' },
    { name: 'phone', label: 'Điện thoại', value: s ? s.phone : '' },
    { name: 'note', label: 'Ghi chú', value: s ? s.note : '' }
  ], async v => {
    if (!v.full_name.trim()) { err('Nhập họ tên'); return false; }
    v.class_id = parseInt(v.class_id, 10) || 0;
    if (s) await api('/api/students/' + s.id, { method: 'PUT', body: v });
    else await api('/api/students', { method: 'POST', body: v });
    ok('Đã lưu'); render();
  });
}

function importStudents() {
  const inp = el('input', { type: 'file', accept: '.xlsx,.xls,.csv,.txt' });
  const out = el('div', { style: 'margin-top:14px' });
  modal({
    title: 'Nhập học sinh từ Excel / CSV',
    size: 'wide',
    body: el('div', {}, [
      el('div', { class: 'infobox', html:
        'File cần có dòng tiêu đề. Hệ thống tự nhận các cột: <b>Mã học sinh, Họ và tên, Ngày sinh, Giới tính, Lớp, Số báo danh, Email, Điện thoại, Ghi chú</b>. ' +
        'Chỉ <b>Họ và tên</b> là bắt buộc. Lớp chưa có sẽ được tạo tự động. ' +
        '<a href="/api/students/template" target="_blank">Tải file mẫu</a>' }),
      el('div', { style: 'margin-top:14px' }, inp),
      out
    ]),
    buttons: [
      { text: 'Đóng', onClick: closeModal },
      { text: 'Xem trước', id: 'im-dry', onClick: () => run(true) },
      { text: 'Nhập vào hệ thống', class: 'btn-primary', id: 'im-go', onClick: () => run(false) }
    ]
  });
  async function run(dry) {
    if (!inp.files.length) { err('Chưa chọn file'); return; }
    const fd = new FormData();
    fd.append('file', inp.files[0]);
    fd.append('dry', dry ? '1' : '0');
    if (ST.cls) fd.append('class_id', String(ST.cls));
    out.innerHTML = '<div class="loading"><span class="spinner"></span> Đang đọc…</div>';
    try {
      const r = await api('/api/students/import', { method: 'POST', body: fd });
      out.innerHTML = '';
      out.appendChild(el('div', { class: r.n_new + r.n_update ? 'okbox' : 'warnbox' }, [
        el('b', { text: dry ? 'Xem trước: ' : 'Đã nhập: ' }),
        el('span', { text: 'thêm mới ' + r.n_new + ', cập nhật ' + r.n_update + ', bỏ qua ' + r.n_skip + (r.n_class_new ? ', tạo ' + r.n_class_new + ' lớp mới' : '') + ' (tổng ' + r.total_rows + ' dòng)' })
      ]));
      if (r.errors && r.errors.length) {
        const ul = el('ul');
        r.errors.slice(0, 20).forEach(e => ul.appendChild(el('li', { text: e })));
        out.appendChild(el('div', { class: 'warnbox', style: 'margin-top:10px' }, [el('b', { text: 'Cảnh báo:' }), ul]));
      }
      if (dry && r.preview && r.preview.length) {
        out.appendChild(el('div', { style: 'margin-top:12px' }, tableEl([
          { t: 'Dòng', k: 'row', w: '60px' }, { t: 'Mã HS', k: 'code', w: '90px' }, { t: 'Họ và tên', k: 'full_name' },
          { t: 'Ngày sinh', k: 'dob_txt', w: '100px' }, { t: 'GT', k: 'gender', w: '60px' },
          { t: 'Lớp', k: 'class', w: '100px' }, { t: 'SBD', k: 'sbd', w: '100px' },
          { t: 'Xử lý', k: 'action', w: '90px' }
        ], r.preview, { short: true })));
      }
      if (!dry) { ok('Đã nhập xong'); setTimeout(() => { closeModal(); render(); }, 800); }
    } catch (e) { out.innerHTML = ''; out.appendChild(el('div', { class: 'errbox', text: e.message })); }
  }
}
