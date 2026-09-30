/* exams.js - ky thi: danh sach, thong tin, dap an, phong thi, cham bai, ket qua, thong ke */
'use strict';

/* ==================================================== DANH SÁCH ==================================================== */
route('exams', async (v, p) => {
  if (p && p[0]) return examDetail(v, p[0], p[1] || 'info');
  crumb('Kỳ thi & chấm bài');
  const r = await api('/api/exams');
  v.innerHTML = '';
  v.appendChild(el('div', { class: 'page-head' }, [
    el('div', {}, [el('h1', { text: 'Kỳ thi & chấm bài' }),
      el('div', { class: 'sub', text: r.items.length + ' kỳ thi' })]),
    el('div', { class: 'grow' }),
    el('input', { type: 'search', id: 'ex-q', placeholder: 'Tìm kỳ thi…', style: 'max-width:220px' }),
    el('button', { class: 'btn btn-primary', onclick: () => newExam() }, '+ Kỳ thi mới')
  ]));

  const draw = (kw) => {
    const list = r.items.filter(e => !kw || (e.name + ' ' + e.code + ' ' + e.subject).toLowerCase().includes(kw.toLowerCase()));
    const rows = list.map(e => ({
      __click: () => go('#/exams/' + e.id),
      name: el('div', {}, [el('b', { text: e.name }), e.note ? el('div', { class: 'tiny muted', text: e.note }) : null]),
      code: e.code || '—',
      subject: e.subject || '—',
      date: e.exam_date_txt || '—',
      keys: e.n_keys ? el('span', { class: 'badge ok', text: e.n_keys + ' mã đề' }) : el('span', { class: 'badge warn', text: 'chưa có' }),
      cand: num(e.n_cand),
      sheets: num(e.n_sheets),
      warn: e.n_warn ? el('span', { class: 'badge warn', text: num(e.n_warn) }) : el('span', { class: 'muted', text: '—' }),
      owner: e.owner || '—',
      act: el('div', { class: 'row tight', onclick: ev => ev.stopPropagation() }, [
        el('button', { class: 'btn btn-sm', onclick: () => go('#/exams/' + e.id + '/grade'), title: 'Chấm bài' }, 'Chấm'),
        el('button', { class: 'btn btn-sm', onclick: () => go('#/exams/' + e.id + '/results'), title: 'Kết quả' }, 'Kết quả'),
        el('button', { class: 'btn btn-sm btn-ghost', onclick: () => delExam(e) }, '🗑')
      ])
    }));
    const t = tableEl([
      { t: 'Kỳ thi', k: 'name' }, { t: 'Mã', k: 'code', w: '90px' }, { t: 'Môn', k: 'subject', w: '110px' },
      { t: 'Ngày thi', k: 'date', w: '96px' }, { t: 'Đáp án', k: 'keys', w: '96px' },
      { t: 'Thí sinh', k: 'cand', align: 'right', w: '80px' },
      { t: 'Đã chấm', k: 'sheets', align: 'right', w: '84px' },
      { t: 'Cần soát', k: 'warn', align: 'center', w: '84px' },
      { t: 'Người tạo', k: 'owner', w: '100px' },
      { t: '', k: 'act', w: '190px' }
    ], rows, { emptyTitle: 'Chưa có kỳ thi', emptyText: 'Tạo kỳ thi để bắt đầu chấm bài' });
    const old = $('#ex-table');
    if (old) old.replaceWith(el('div', { id: 'ex-table' }, card(null, t, null, { tight: true })));
    else v.appendChild(el('div', { id: 'ex-table' }, card(null, t, null, { tight: true })));
  };
  draw('');
  $('#ex-q').addEventListener('input', debounce(e => draw(e.target.value), 200));
});

function newExam() {
  const presets = [
    { value: 'khac', label: 'Tốt nghiệp THPT 2025 – Lý/Hoá/Sinh/Sử/Địa/GDKT-PL/Tin/CN (P3 = 0,25đ)' },
    { value: 'toan', label: 'Tốt nghiệp THPT 2025 – Toán (P3 = 0,5đ)' },
    { value: 'ngoaingu', label: 'Ngoại ngữ / chỉ Phần I – 40 câu × 0,25đ' },
    { value: 'thang10', label: 'Chỉ Phần I – quy đổi về thang 10' }
  ];
  promptBox('Tạo kỳ thi mới', [
    { name: 'name', label: 'Tên kỳ thi *', ph: 'VD: Kiểm tra giữa kỳ I – Vật lí 12' },
    { name: 'code', label: 'Mã kỳ thi', ph: 'VD: GK1-LY12' },
    { name: 'subject', label: 'Môn thi', ph: 'VD: Vật lí' },
    { name: 'exam_date_txt', label: 'Ngày thi', value: todayVN(), hint: '(dd/mm/yyyy)' },
    { name: 'preset', label: 'Cách tính điểm', type: 'select', options: presets, value: 'khac' },
    { name: 'note', label: 'Ghi chú', type: 'textarea', rows: 2 }
  ], async v => {
    if (!v.name.trim()) { err('Nhập tên kỳ thi'); return false; }
    const r = await api('/api/exams', { method: 'POST', body: v });
    ok('Đã tạo kỳ thi');
    go('#/exams/' + r.id + '/keys');
  }, { submit: 'Tạo kỳ thi' });
}
function delExam(e) {
  confirmBox('Xoá kỳ thi “' + e.name + '”?', async () => {
    try { await api('/api/exams/' + e.id, { method: 'DELETE' }); ok('Đã xoá'); render(); }
    catch (x) { err(x.message); }
  }, { danger: true, yes: 'Xoá vĩnh viễn', warn: 'Toàn bộ phiếu đã chấm, đáp án, danh sách thí sinh và ảnh của kỳ thi này sẽ bị xoá.' });
}

/* ==================================================== CHI TIẾT ==================================================== */
let EX = null;   // ky thi hien tai

async function examDetail(v, id, tab) {
  const r = await api('/api/exams/' + id);
  EX = r.exam; EX.presets = r.presets;
  crumb(EX.name);
  v.innerHTML = '';
  v.appendChild(el('div', { class: 'page-head' }, [
    el('div', {}, [
      el('div', { class: 'row tight', style: 'margin-bottom:2px' }, [
        el('a', { href: '#/exams', class: 'small' }, '‹ Kỳ thi'),
        el('span', { class: 'badge ' + (EX.status === 'open' ? 'ok' : ''), text: EX.status === 'open' ? 'đang mở' : 'đã đóng' })
      ]),
      el('h1', { text: EX.name }),
      el('div', { class: 'sub', text: [EX.code, EX.subject, EX.exam_date_txt, 'Mẫu: ' + EX.template_name].filter(Boolean).join(' · ') })
    ]),
    el('div', { class: 'grow' }),
    el('button', { class: 'btn', onclick: () => window.open('/api/templates/' + EX.template_id + '/blank.pdf?count=1&exam_id=' + EX.id, '_blank') }, 'In phiếu trống'),
    el('button', { class: 'btn btn-primary', onclick: () => go('#/exams/' + EX.id + '/grade') }, 'Chấm bài')
  ]));
  const tabs = [
    { id: 'info', label: 'Thông tin & thang điểm' },
    { id: 'keys', label: 'Đáp án', badge: EX.keys.length },
    { id: 'cands', label: 'Phòng thi & thí sinh', badge: EX.n_cand },
    { id: 'grade', label: 'Chấm bài' },
    { id: 'results', label: 'Kết quả', badge: EX.n_sheets },
    { id: 'stats', label: 'Thống kê' }
  ];
  v.appendChild(tabsEl(tabs, tab, t => go('#/exams/' + EX.id + '/' + t)));
  const body = el('div', { id: 'tab-body' });
  v.appendChild(body);
  const fns = { info: tabInfo, keys: tabKeys, cands: tabCands, grade: tabGrade, results: tabResults, stats: tabStats };
  await (fns[tab] || tabInfo)(body);
}

/* ---------------- TAB: thông tin ---------------- */
async function tabInfo(b) {
  const sc = EX.scoring || {};
  const oo = EX.omr_opts || {};
  const f = (name, label, val, hint, type) => el('label', { class: 'field' }, [
    el('span', { html: esc(label) + (hint ? ' <span class="hint">' + esc(hint) + '</span>' : '') }),
    el('input', { type: type || 'text', id: name, value: val === undefined || val === null ? '' : val, step: type === 'number' ? '0.01' : null })
  ]);
  const left = el('div', { class: 'stack' });
  const g = el('div');
  g.appendChild(el('div', { class: 'inline-fields' }, [
    f('e-name', 'Tên kỳ thi', EX.name),
    f('e-code', 'Mã kỳ thi', EX.code),
    f('e-subject', 'Môn thi', EX.subject),
    f('e-date', 'Ngày thi', EX.exam_date_txt, '(dd/mm/yyyy)')
  ]));
  g.appendChild(el('label', { class: 'field' }, [el('span', { text: 'Ghi chú' }), el('textarea', { id: 'e-note', rows: 2 }, EX.note || '')]));
  g.appendChild(el('div', { class: 'inline-fields' }, [
    el('label', { class: 'field' }, [el('span', { text: 'Trạng thái' }),
      el('select', { id: 'e-status' }, [
        el('option', { value: 'open', selected: EX.status === 'open' ? 'selected' : null }, 'Đang mở (cho phép chấm)'),
        el('option', { value: 'closed', selected: EX.status !== 'open' ? 'selected' : null }, 'Đã đóng')])]),
    el('label', { class: 'field' }, [el('span', { text: 'Mẫu phiếu' }),
      el('select', { id: 'e-tpl' }, [el('option', { value: EX.template_id, selected: 'selected' }, EX.template_name)])])
  ]));
  left.appendChild(card('Thông tin kỳ thi', g, [
    el('button', { class: 'btn btn-primary btn-sm', onclick: saveInfo }, 'Lưu thông tin')
  ]));

  // thang diem
  const s = el('div');
  const PRESET_VALS = {
    toan:     { p1: 0.25, lad: [0.1, 0.25, 0.5, 1], p3: 0.5,  on: [1, 1, 1], scale: false },
    khac:     { p1: 0.25, lad: [0.1, 0.25, 0.5, 1], p3: 0.25, on: [1, 1, 1], scale: false },
    ngoaingu: { p1: 0.25, lad: [0.1, 0.25, 0.5, 1], p3: 0.25, on: [1, 0, 0], scale: false },
    thang10:  { p1: 0.25, lad: [0.1, 0.25, 0.5, 1], p3: 0.25, on: [1, 0, 0], scale: true }
  };
  const presetSel = el('select', { id: 'sc-preset' }, [el('option', { value: '' }, '— Áp dụng mẫu có sẵn —')]
    .concat((EX.presets || []).map(p => el('option', { value: p.id }, p.name))));
  presetSel.addEventListener('change', e => {
    const v = PRESET_VALS[e.target.value];
    e.target.value = '';
    if (!v) return;
    $('#sc-p1on').checked = !!v.on[0]; $('#sc-p2on').checked = !!v.on[1]; $('#sc-p3on').checked = !!v.on[2];
    $('#sc-p1per').value = v.p1; $('#sc-p3per').value = v.p3;
    $('#sc-p2scheme').value = 'ladder';
    $('#sc-l1').value = v.lad[0]; $('#sc-l2').value = v.lad[1]; $('#sc-l3').value = v.lad[2]; $('#sc-l4').value = v.lad[3];
    $('#sc-scale').checked = v.scale; $('#sc-scalemax').value = 10;
    ok('Đã nạp mẫu vào biểu mẫu · bấm “Lưu & chấm lại” để áp dụng');
  });
  s.appendChild(el('div', { class: 'infobox', style: 'margin-bottom:14px', html:
    '<b>Cách tính điểm kỳ thi tốt nghiệp THPT 2025:</b> Phần I mỗi câu 0,25đ · Phần II theo bậc thang (đúng 1 ý = 0,1đ; 2 ý = 0,25đ; 3 ý = 0,5đ; 4 ý = 1,0đ) · Phần III mỗi câu 0,5đ (môn Toán) hoặc 0,25đ (các môn khác).' }));
  const sgrid = el('div', { class: 'inline-fields' }, [
    el('label', { class: 'check' }, [el('input', { type: 'checkbox', id: 'sc-p1on', checked: sc.p1_on !== false ? 'checked' : null }), el('span', { text: 'Tính điểm Phần I' })]),
    el('label', { class: 'check' }, [el('input', { type: 'checkbox', id: 'sc-p2on', checked: sc.p2_on !== false ? 'checked' : null }), el('span', { text: 'Tính điểm Phần II' })]),
    el('label', { class: 'check' }, [el('input', { type: 'checkbox', id: 'sc-p3on', checked: sc.p3_on !== false ? 'checked' : null }), el('span', { text: 'Tính điểm Phần III' })])
  ]);
  s.appendChild(sgrid);
  s.appendChild(el('div', { class: 'inline-fields' }, [
    f('sc-p1per', 'Phần I – điểm mỗi câu', sc.p1_per, '', 'number'),
    f('sc-p3per', 'Phần III – điểm mỗi câu', sc.p3_per, '', 'number'),
    el('label', { class: 'field' }, [el('span', { text: 'Phần II – cách tính' }),
      el('select', { id: 'sc-p2scheme' }, [
        el('option', { value: 'ladder', selected: (sc.p2_scheme || 'ladder') === 'ladder' ? 'selected' : null }, 'Bậc thang theo số ý đúng (chuẩn Bộ)'),
        el('option', { value: 'per_sub', selected: sc.p2_scheme === 'per_sub' ? 'selected' : null }, 'Điểm cố định mỗi ý đúng'),
        el('option', { value: 'all_or_nothing', selected: sc.p2_scheme === 'all_or_nothing' ? 'selected' : null }, 'Đúng cả 4 ý mới có điểm')])])
  ]));
  const lad = sc.p2_ladder || [0.1, 0.25, 0.5, 1];
  s.appendChild(el('div', { class: 'inline-fields', id: 'sc-ladder-box' }, [
    f('sc-l1', 'Đúng 1 ý', lad[0], '', 'number'), f('sc-l2', 'Đúng 2 ý', lad[1], '', 'number'),
    f('sc-l3', 'Đúng 3 ý', lad[2], '', 'number'), f('sc-l4', 'Đúng 4 ý', lad[3], '', 'number'),
    f('sc-p2sub', 'Điểm mỗi ý (chế độ cố định)', sc.p2_per_sub, '', 'number')
  ]));
  s.appendChild(el('hr'));
  s.appendChild(el('div', { class: 'inline-fields' }, [
    f('sc-pen', 'Trừ điểm mỗi câu sai (Phần I)', sc.wrong_penalty || 0, '(0 = không trừ)', 'number'),
    el('label', { class: 'field' }, [el('span', { text: 'Làm tròn điểm' }),
      el('select', { id: 'sc-round' }, [
        el('option', { value: '2', selected: (sc.round_dec === undefined ? 2 : sc.round_dec) == 2 ? 'selected' : null }, '2 chữ số thập phân'),
        el('option', { value: '1', selected: sc.round_dec == 1 ? 'selected' : null }, '1 chữ số thập phân'),
        el('option', { value: '0', selected: sc.round_dec == 0 ? 'selected' : null }, 'Số nguyên'),
        el('option', { value: '3', selected: sc.round_dec == 3 ? 'selected' : null }, '3 chữ số thập phân')])]),
    el('label', { class: 'field' }, [el('span', { text: 'Kiểu làm tròn' }),
      el('select', { id: 'sc-rmode' }, [
        el('option', { value: 'half_up', selected: (sc.round_mode || 'half_up') === 'half_up' ? 'selected' : null }, 'Làm tròn thường'),
        el('option', { value: 'floor', selected: sc.round_mode === 'floor' ? 'selected' : null }, 'Làm tròn xuống'),
        el('option', { value: 'ceil', selected: sc.round_mode === 'ceil' ? 'selected' : null }, 'Làm tròn lên'),
        el('option', { value: 'none', selected: sc.round_mode === 'none' ? 'selected' : null }, 'Không làm tròn')])])
  ]));
  s.appendChild(el('div', { class: 'inline-fields' }, [
    el('label', { class: 'check' }, [el('input', { type: 'checkbox', id: 'sc-scale', checked: sc.scale_on ? 'checked' : null }), el('span', { text: 'Quy đổi về thang điểm cố định' })]),
    f('sc-scalemax', 'Thang điểm', sc.scale_max || 10, '', 'number'),
    el('label', { class: 'check' }, [el('input', { type: 'checkbox', id: 'sc-multi', checked: sc.multi_is_wrong !== false ? 'checked' : null }), el('span', { text: 'Tô nhiều đáp án = sai' })]),
    el('label', { class: 'check' }, [el('input', { type: 'checkbox', id: 'sc-p3strict', checked: sc.p3_strict !== false ? 'checked' : null }), el('span', { text: 'Phần III so khớp chính xác chuỗi' })])
  ]));
  left.appendChild(card('Cách tính điểm', s, [
    presetSel,
    el('button', { class: 'btn btn-primary btn-sm', onclick: () => saveScoring(true) }, 'Lưu & chấm lại')
  ]));

  // tuy chon nhan dang
  const o = el('div');
  o.appendChild(el('p', { class: 'small muted', style: 'margin:0 0 12px', text: 'Chỉ nên thay đổi khi phiếu in mờ, ảnh kém hoặc học sinh tô rất nhạt. Để trống sẽ dùng cấu hình chung của hệ thống.' }));
  o.appendChild(el('div', { class: 'inline-fields' }, [
    f('o-fill', 'Ngưỡng nhận “đã tô”', oo.fill_threshold, '(0.10 – 0.60)', 'number'),
    f('o-margin', 'Chênh lệch tối thiểu', oo.margin, '(0.03 – 0.30)', 'number'),
    el('label', { class: 'field' }, [el('span', { text: 'Loại nét in hồng' }),
      el('select', { id: 'o-pink' }, [
        el('option', { value: '2', selected: (oo.pink_dropout === undefined ? 2 : oo.pink_dropout) == 2 ? 'selected' : null }, 'Tự động'),
        el('option', { value: '1', selected: oo.pink_dropout == 1 ? 'selected' : null }, 'Luôn bật'),
        el('option', { value: '0', selected: oo.pink_dropout == 0 ? 'selected' : null }, 'Tắt')])]),
    f('o-shrink', 'Tỉ lệ vùng lấy mẫu', oo.bubble_shrink, '(0.5 – 0.95)', 'number'),
    f('o-search', 'Bán kính dò lệch (px)', oo.search_radius, '', 'number'),
    f('o-jpq', 'Chất lượng ảnh overlay', oo.jpeg_quality, '(50 – 95)', 'number')
  ]));
  o.appendChild(el('label', { class: 'check' }, [
    el('input', { type: 'checkbox', id: 'o-rot', checked: oo.detect_rotation !== false ? 'checked' : null }),
    el('span', { text: 'Tự động phát hiện & xoay ảnh (90°/180°/270°)' })]));
  left.appendChild(card('Tuỳ chọn nhận dạng ảnh (nâng cao)', o, [
    el('button', { class: 'btn btn-primary btn-sm', onclick: saveOmr }, 'Lưu')
  ]));

  b.appendChild(left);
}
async function saveInfo() {
  try {
    await api('/api/exams/' + EX.id, {
      method: 'PUT', body: Object.assign({}, EX, {
        name: $('#e-name').value, code: $('#e-code').value, subject: $('#e-subject').value,
        exam_date_txt: $('#e-date').value, note: $('#e-note').value, status: $('#e-status').value,
        template_id: $('#e-tpl').value, scoring: EX.scoring, omr_opts: EX.omr_opts
      })
    });
    ok('Đã lưu thông tin kỳ thi'); render();
  } catch (e) { err(e.message); }
}
async function saveScoring(regrade) {
  const sc = {
    mode: 'custom',
    p1_on: $('#sc-p1on').checked, p2_on: $('#sc-p2on').checked, p3_on: $('#sc-p3on').checked,
    p1_per: parseFloat($('#sc-p1per').value) || 0,
    p3_per: parseFloat($('#sc-p3per').value) || 0,
    p2_scheme: $('#sc-p2scheme').value,
    p2_ladder: [parseFloat($('#sc-l1').value) || 0, parseFloat($('#sc-l2').value) || 0, parseFloat($('#sc-l3').value) || 0, parseFloat($('#sc-l4').value) || 0],
    p2_per_sub: parseFloat($('#sc-p2sub').value) || 0,
    p2_per_q: parseFloat($('#sc-l4').value) || 1,
    wrong_penalty: parseFloat($('#sc-pen').value) || 0,
    round_dec: parseInt($('#sc-round').value, 10),
    round_mode: $('#sc-rmode').value,
    scale_on: $('#sc-scale').checked,
    scale_max: parseFloat($('#sc-scalemax').value) || 10,
    multi_is_wrong: $('#sc-multi').checked,
    p3_strict: $('#sc-p3strict').checked
  };
  try {
    const r = await api('/api/exams/' + EX.id, { method: 'PUT', body: Object.assign({}, EX, { scoring: sc, regrade: !!regrade }) });
    ok('Đã lưu cách tính điểm' + (r.regraded ? ' · đã chấm lại ' + r.regraded + ' phiếu' : ''));
    render();
  } catch (e) { err(e.message); }
}
async function saveOmr() {
  const oo = {
    fill_threshold: parseFloat($('#o-fill').value) || 0.3,
    margin: parseFloat($('#o-margin').value) || 0.1,
    pink_dropout: parseInt($('#o-pink').value, 10),
    bubble_shrink: parseFloat($('#o-shrink').value) || 0.74,
    search_radius: parseInt($('#o-search').value, 10) || 3,
    jpeg_quality: parseInt($('#o-jpq').value, 10) || 84,
    detect_rotation: $('#o-rot').checked
  };
  try {
    await api('/api/exams/' + EX.id, { method: 'PUT', body: Object.assign({}, EX, { omr_opts: oo }) });
    ok('Đã lưu tuỳ chọn nhận dạng'); render();
  } catch (e) { err(e.message); }
}

/* ---------------- TAB: đáp án ---------------- */
let KEYS = [];
async function tabKeys(b) {
  KEYS = JSON.parse(JSON.stringify(EX.keys || []));
  const C = EX.counts;
  b.innerHTML = '';
  b.appendChild(el('div', { class: 'row', style: 'margin-bottom:14px' }, [
    el('button', { class: 'btn btn-primary', onclick: () => { addKey(); } }, '+ Thêm mã đề'),
    el('button', { class: 'btn', onclick: pasteKeys }, 'Dán nhanh đáp án'),
    el('button', { class: 'btn', onclick: importKeys }, 'Nhập từ Excel/CSV'),
    el('button', { class: 'btn btn-ghost', onclick: () => window.open('/api/exams/' + EX.id + '/keys/template', '_blank') }, 'Tải file mẫu'),
    el('div', { class: 'grow' }),
    el('button', { class: 'btn btn-ok', onclick: () => saveKeys(true) }, 'Lưu đáp án & chấm lại')
  ]));
  const wrap = el('div', { class: 'stack', id: 'keys-wrap' });
  b.appendChild(wrap);
  drawKeys();

  function drawKeys() {
    const w = $('#keys-wrap');
    w.innerHTML = '';
    if (!KEYS.length) {
      w.appendChild(el('div', { class: 'card card-pad' }, el('div', { class: 'empty' }, [
        el('b', { text: 'Chưa có đáp án' }),
        el('span', { text: 'Thêm mã đề rồi nhập đáp án, hoặc dán nhanh / nhập từ Excel.' })
      ])));
      return;
    }
    KEYS.forEach((k, ki) => w.appendChild(keyCard(k, ki)));
  }
  function keyCard(k, ki) {
    const bd = el('div');
    // Phan I
    const p1 = el('div', { class: 'ansgrid bycol', style: '--cw:158px' });
    for (let i = 0; i < C.p1; i++) {
      const cur = (k.p1 && k.p1[i]) || '';
      const btns = el('div', { class: 'abcd' });
      'ABCD'.split('').forEach(L => btns.appendChild(el('button', {
        class: cur === L ? 'on' : '', onclick: e => {
          k.p1[i] = (k.p1[i] === L) ? '' : L;
          Array.from(e.target.parentNode.children).forEach(c => c.classList.toggle('on', c.textContent === k.p1[i]));
        }
      }, L)));
      p1.appendChild(el('div', { class: 'ansitem' }, [el('span', { class: 'n', text: (i + 1) + '.' }), btns]));
    }
    bd.appendChild(el('h4', { text: 'PHẦN I – Trắc nghiệm nhiều lựa chọn (' + C.p1 + ' câu)' }));
    bd.appendChild(p1);
    // Phan II
    if (C.p2 > 0) {
      bd.appendChild(el('h4', { style: 'margin-top:16px', text: 'PHẦN II – Đúng/Sai (' + C.p2 + ' câu × ' + C.p2_subs + ' ý) · Đ = Đúng, S = Sai, – = không dùng' }));
      const p2 = el('div', { class: 'ansgrid', style: 'grid-template-columns:repeat(auto-fill,minmax(252px,1fr))' });
      for (let i = 0; i < C.p2; i++) {
        let cur = ((k.p2 && k.p2[i]) || '').padEnd(C.p2_subs, '-');
        const row = el('div', { class: 'ansitem' }, [el('span', { class: 'n', text: 'Câu ' + (i + 1) })]);
        for (let j = 0; j < C.p2_subs; j++) {
          const bt = el('button', {
            class: 'btn btn-sm', style: 'min-width:34px;padding:3px 6px',
            onclick: e => {
              const order = ['D', 'S', '-'];
              let c = k.p2[i].padEnd(C.p2_subs, '-');
              const nx = order[(order.indexOf(c[j]) + 1) % 3];
              k.p2[i] = c.substring(0, j) + nx + c.substring(j + 1);
              e.target.textContent = 'abcd'[j] + ':' + (nx === 'D' ? 'Đ' : nx);
              e.target.className = 'btn btn-sm' + (nx === 'D' ? ' btn-ok' : nx === 'S' ? ' btn-danger' : '');
            }
          }, 'abcd'[j] + ':' + (cur[j] === 'D' ? 'Đ' : cur[j]));
          bt.className = 'btn btn-sm' + (cur[j] === 'D' ? ' btn-ok' : cur[j] === 'S' ? ' btn-danger' : '');
          row.appendChild(bt);
        }
        p2.appendChild(row);
      }
      bd.appendChild(p2);
    }
    // Phan III
    if (C.p3 > 0) {
      bd.appendChild(el('h4', { style: 'margin-top:16px', text: 'PHẦN III – Trả lời ngắn (' + C.p3 + ' câu) · dùng dấu phẩy thập phân, tối đa ' + C.p3_slots + ' ký tự' }));
      const p3 = el('div', { class: 'ansgrid', style: 'grid-template-columns:repeat(auto-fill,minmax(150px,1fr))' });
      for (let i = 0; i < C.p3; i++) {
        p3.appendChild(el('div', { class: 'ansitem' }, [
          el('span', { class: 'n', text: (i + 1) + '.' }),
          el('input', {
            type: 'text', value: (k.p3 && k.p3[i]) || '', maxlength: 8, placeholder: '—',
            oninput: e => { k.p3[i] = e.target.value.replace('.', ','); }
          })
        ]));
      }
      bd.appendChild(p3);
    }
    return card('Mã đề: ' + (k.made || '(dùng chung cho mọi mã đề)'), bd, [
      el('span', { class: 'small muted', text: k.updated_at_txt ? 'cập nhật ' + k.updated_at_txt : 'chưa lưu' }),
      el('button', { class: 'btn btn-sm', onclick: () => { const m = prompt('Mã đề (để trống = dùng chung):', k.made || ''); if (m !== null) { k.made = m.trim(); drawKeys(); } } }, 'Sửa mã đề'),
      el('button', { class: 'btn btn-sm', onclick: () => { if (KEYS.length > 1) { const c = JSON.parse(JSON.stringify(k)); c.made = (k.made || '') + '-copy'; KEYS.push(c); } else { const c = JSON.parse(JSON.stringify(k)); c.made = ''; KEYS.push(c); } drawKeys(); } }, 'Nhân bản'),
      el('button', { class: 'btn btn-sm btn-ghost', onclick: () => { KEYS.splice(ki, 1); drawKeys(); } }, '🗑 Xoá')
    ]);
  }
  function blankKey(made) {
    return { made: made || '', p1: new Array(C.p1).fill(''), p2: new Array(C.p2).fill('-'.repeat(C.p2_subs)), p3: new Array(C.p3).fill('') };
  }
  function addKey() {
    const m = prompt('Mã đề (để trống nếu chỉ có một đề dùng chung):', KEYS.length ? String(1000 + KEYS.length + 1).slice(1) : '');
    if (m === null) return;
    KEYS.push(blankKey(m.trim()));
    drawKeys();
  }
  function pasteKeys() {
    promptBox('Dán nhanh đáp án', [
      { type: 'html', html: '<div class="infobox" style="margin-bottom:12px">Dán chuỗi đáp án. Ví dụ Phần I: <b>ABCDABCD…</b> hoặc <b>1.A 2.B 3.C</b>. Phần II: mỗi câu 4 ký tự Đ/S cách nhau bằng dấu cách, ví dụ <b>DSDS SDDS</b>. Phần III: các giá trị cách nhau bằng dấu cách, ví dụ <b>-1,5 3 12,5</b>.</div>' },
      { name: 'made', label: 'Mã đề', value: KEYS.length ? '' : '' , ph: '(để trống = dùng chung)' },
      { name: 'p1', label: 'Phần I', type: 'textarea', rows: 3 },
      { name: 'p2', label: 'Phần II', type: 'textarea', rows: 2 },
      { name: 'p3', label: 'Phần III', type: 'textarea', rows: 2 }
    ], v => {
      const k = blankKey(v.made.trim());
      const a1 = (v.p1.toUpperCase().match(/[ABCD]/g) || []);
      for (let i = 0; i < Math.min(a1.length, C.p1); i++) k.p1[i] = a1[i];
      const a2 = (v.p2.toUpperCase().replace(/[^DSTF\-\s01]/g, '').trim().split(/\s+/).filter(Boolean));
      for (let i = 0; i < Math.min(a2.length, C.p2); i++) {
        let s = a2[i].replace(/T|1/g, 'D').replace(/F|0/g, 'S').slice(0, C.p2_subs).padEnd(C.p2_subs, '-');
        k.p2[i] = s;
      }
      const a3 = v.p3.trim().split(/[\s;]+/).filter(Boolean);
      for (let i = 0; i < Math.min(a3.length, C.p3); i++) k.p3[i] = a3[i].replace('.', ',');
      const ex = KEYS.findIndex(x => (x.made || '') === k.made);
      if (ex >= 0) KEYS[ex] = k; else KEYS.push(k);
      ok('Đã nạp ' + a1.length + ' câu Phần I, ' + a2.length + ' câu Phần II, ' + a3.length + ' câu Phần III. Nhớ bấm Lưu.');
      drawKeys();
    }, { submit: 'Nạp', size: 'wide' });
  }
  function importKeys() {
    const inp = el('input', { type: 'file', accept: '.xlsx,.xls,.csv', style: 'margin-bottom:10px' });
    modal({
      title: 'Nhập đáp án từ Excel/CSV',
      body: el('div', {}, [
        el('div', { class: 'infobox', style: 'margin-bottom:12px', html: 'File cần có cột đầu là <b>Mã đề</b>, tiếp theo là các cột <b>I.1…I.' + C.p1 + '</b>, <b>II.1…II.' + C.p2 + '</b>, <b>III.1…III.' + C.p3 + '</b>. Tải file mẫu để xem định dạng chuẩn.' }),
        inp
      ]),
      buttons: [{ text: 'Huỷ', onClick: closeModal }, {
        text: 'Đọc file', class: 'btn-primary', onClick: async () => {
          if (!inp.files.length) { err('Chưa chọn file'); return; }
          const fd = new FormData(); fd.append('file', inp.files[0]);
          try {
            const r = await api('/api/exams/' + EX.id + '/keys/import', { method: 'POST', body: fd });
            KEYS = r.keys.map(k => ({
              made: k.made || '',
              p1: (k.p1 || []).map(x => (x || '').toUpperCase()),
              p2: (k.p2 || []).map(x => (x || '').toUpperCase().replace(/T|1/g, 'D').replace(/F|0/g, 'S').padEnd(C.p2_subs, '-')),
              p3: (k.p3 || []).map(x => String(x || '').replace('.', ','))
            }));
            closeModal(); drawKeys();
            ok('Đã đọc ' + r.count + ' mã đề. Kiểm tra rồi bấm Lưu đáp án.');
          } catch (e) { err(e.message); }
        }
      }]
    });
  }
  async function saveKeys(regrade) {
    if (!KEYS.length) { err('Chưa có đáp án nào'); return; }
    try {
      const r = await api('/api/exams/' + EX.id + '/keys', { method: 'PUT', body: { keys: KEYS, replace: true, regrade: !!regrade } });
      ok('Đã lưu ' + r.count + ' mã đề' + (r.regraded ? ' · chấm lại ' + r.regraded + ' phiếu' : ''));
      (r.warnings || []).forEach(w => warn(w));
      render();
    } catch (e) { err(e.message); }
  }
}

/* ---------------- TAB: phòng thi & thí sinh ---------------- */
async function tabCands(b) {
  b.innerHTML = '';
  const rooms = EX.rooms || [];
  const top = el('div', { class: 'split' });
  // phong thi
  const rl = el('div');
  rooms.forEach(r => rl.appendChild(el('div', { class: 'row', style: 'padding:7px 0;border-bottom:1px solid var(--line)' }, [
    el('b', { text: r.name || r.code }),
    el('span', { class: 'small muted', text: (r.capacity ? 'sức chứa ' + r.capacity : '') }),
    el('div', { class: 'grow' }),
    el('span', { class: 'badge', text: r.n_candidates + ' thí sinh' }),
    el('button', { class: 'btn btn-sm btn-ghost', onclick: () => editRoom(r) }, '✎'),
    el('button', { class: 'btn btn-sm btn-ghost', onclick: () => confirmBox('Xoá phòng “' + (r.name || r.code) + '”?', async () => { await api('/api/rooms/' + r.id, { method: 'DELETE' }); render(); }, { danger: true }) }, '🗑')
  ])));
  if (!rooms.length) rl.appendChild(el('div', { class: 'empty' }, [el('b', { text: 'Chưa có phòng thi' }), el('span', { text: 'Có thể bỏ qua nếu không chia phòng.' })]));
  top.appendChild(card('Phòng thi (' + rooms.length + ')', rl, [
    el('button', { class: 'btn btn-sm', onclick: () => editRoom(null) }, '+ Thêm'),
    el('button', { class: 'btn btn-sm', onclick: bulkRooms }, 'Tạo nhiều phòng')
  ]));
  // lap danh sach
  const f = el('div');
  f.appendChild(el('p', { class: 'small muted', style: 'margin:0 0 12px', text: 'Chọn lớp để đưa học sinh vào danh sách thi, hệ thống sẽ tự sinh số báo danh và chia phòng theo thứ tự.' }));
  const cls = await api('/api/classes');
  const chips = el('div', { class: 'chips', style: 'margin-bottom:12px' });
  const picked = new Set();
  cls.items.forEach(c => {
    const ch = el('div', { class: 'chip', onclick: () => { ch.classList.toggle('on'); if (picked.has(c.id)) picked.delete(c.id); else picked.add(c.id); } },
      (c.name || c.code) + ' (' + c.n_students + ')');
    chips.appendChild(ch);
  });
  if (!cls.items.length) chips.appendChild(el('span', { class: 'muted small', text: 'Chưa có lớp nào – hãy tạo lớp và nhập học sinh trước.' }));
  f.appendChild(chips);
  f.appendChild(el('div', { class: 'inline-fields' }, [
    el('label', { class: 'field' }, [el('span', { text: 'Tiền tố SBD' }), el('input', { id: 'c-prefix', value: '' })]),
    el('label', { class: 'field' }, [el('span', { text: 'SBD bắt đầu từ' }), el('input', { id: 'c-start', type: 'number', value: '1' })]),
    el('label', { class: 'field' }, [el('span', { text: 'Số chữ số' }), el('input', { id: 'c-len', type: 'number', value: '6' })]),
    el('label', { class: 'field' }, [el('span', { text: 'Số thí sinh mỗi phòng' }), el('input', { id: 'c-size', type: 'number', value: '24' })]),
    el('label', { class: 'field' }, [el('span', { html: 'Danh sách mã đề <span class="hint">(cách nhau bởi dấu phẩy)</span>' }), el('input', { id: 'c-mades', placeholder: 'VD: 0001,0002,0003,0004' })])
  ]));
  f.appendChild(el('label', { class: 'check' }, [el('input', { type: 'checkbox', id: 'c-gen', checked: 'checked' }), el('span', { text: 'Sinh lại số báo danh cho toàn bộ (bỏ chọn nếu muốn giữ SBD sẵn có của học sinh)' })]));
  f.appendChild(el('label', { class: 'check' }, [el('input', { type: 'checkbox', id: 'c-clear' }), el('span', { text: 'Xoá danh sách thí sinh hiện tại trước khi lập' })]));
  top.appendChild(card('Lập danh sách thí sinh', f, [
    el('button', {
      class: 'btn btn-primary btn-sm', onclick: async ev => {
        if (!picked.size) { err('Chọn ít nhất một lớp'); return; }
        ev.target.disabled = true;
        try {
          const r = await api('/api/exams/' + EX.id + '/candidates', {
            method: 'POST', body: {
              class_ids: Array.from(picked), clear: $('#c-clear').checked,
              gen_sbd: $('#c-gen').checked, sbd_prefix: $('#c-prefix').value,
              sbd_start: parseInt($('#c-start').value, 10) || 1, sbd_len: parseInt($('#c-len').value, 10) || 6,
              room_size: parseInt($('#c-size').value, 10) || 0, auto_room: true,
              made_list: $('#c-mades').value.split(',').map(s => s.trim()).filter(Boolean)
            }
          });
          ok('Đã thêm ' + r.count + ' thí sinh'); render();
        } catch (e) { err(e.message); ev.target.disabled = false; }
      }
    }, 'Lập danh sách')
  ]));
  b.appendChild(top);
  b.appendChild(el('div', { style: 'height:16px' }));

  const cnd = await api('/api/exams/' + EX.id + '/candidates');
  const rows = cnd.items.map(c => ({
    sbd: el('b', { class: 'mono', text: c.sbd || '—' }),
    name: c.full_name || '—', cls: c.class_name || '—',
    room: c.room_name || '—', seat: c.seat || '—', made: c.made || '—',
    absent: c.absent ? el('span', { class: 'badge err', text: 'vắng' }) : '',
    act: el('div', { class: 'row tight' }, [
      el('button', { class: 'btn btn-sm btn-ghost', onclick: () => editCand(c, EX.rooms) }, '✎'),
      el('button', { class: 'btn btn-sm btn-ghost', onclick: () => confirmBox('Xoá thí sinh này khỏi kỳ thi?', async () => { await api('/api/candidates/' + c.id, { method: 'DELETE' }); render(); }, { danger: true }) }, '🗑')
    ])
  }));
  b.appendChild(card('Danh sách thí sinh (' + cnd.items.length + ')', tableEl([
    { t: 'SBD', k: 'sbd', w: '110px' }, { t: 'Họ và tên', k: 'name' }, { t: 'Lớp', k: 'cls', w: '110px' },
    { t: 'Phòng thi', k: 'room', w: '130px' }, { t: 'Số ghế', k: 'seat', w: '80px' },
    { t: 'Mã đề', k: 'made', w: '90px' }, { t: '', k: 'absent', w: '70px' }, { t: '', k: 'act', w: '90px' }
  ], rows, { emptyTitle: 'Chưa có thí sinh', emptyText: 'Dùng khung “Lập danh sách thí sinh” ở trên.' }),
    [el('button', { class: 'btn btn-sm', onclick: () => window.open('/api/templates/' + EX.template_id + '/blank.pdf?count=' + Math.max(1, cnd.items.length) + '&exam_id=' + EX.id + '&prefill=1&dl=1', '_blank') }, 'In phiếu điền sẵn SBD')],
    { tight: true }));

  function editRoom(r) {
    promptBox(r ? 'Sửa phòng thi' : 'Thêm phòng thi', [
      { name: 'code', label: 'Mã phòng', value: r ? r.code : '' },
      { name: 'name', label: 'Tên phòng *', value: r ? r.name : '' },
      { name: 'capacity', label: 'Sức chứa', type: 'number', value: r ? r.capacity : 24 },
      { name: 'note', label: 'Ghi chú', value: r ? r.note : '' }
    ], async v => {
      if (r) await api('/api/rooms/' + r.id, { method: 'PUT', body: v });
      else await api('/api/exams/' + EX.id + '/rooms', { method: 'POST', body: v });
      ok('Đã lưu'); render();
    });
  }
  function bulkRooms() {
    promptBox('Tạo nhiều phòng thi', [
      { name: 'prefix', label: 'Tiền tố tên phòng', value: 'Phòng ' },
      { name: 'start', label: 'Bắt đầu từ số', type: 'number', value: 1 },
      { name: 'count', label: 'Số phòng cần tạo', type: 'number', value: 10 },
      { name: 'capacity', label: 'Sức chứa mỗi phòng', type: 'number', value: 24 }
    ], async v => {
      const r = await api('/api/exams/' + EX.id + '/rooms', { method: 'POST', body: { prefix: v.prefix, start: +v.start, count: +v.count, capacity: +v.capacity } });
      ok('Đã tạo ' + r.created + ' phòng'); render();
    });
  }
  function editCand(c, rooms) {
    promptBox('Sửa thí sinh', [
      { name: 'sbd', label: 'Số báo danh', value: c.sbd },
      { name: 'room_id', label: 'Phòng thi', type: 'select', value: c.room_id, options: [{ value: 0, label: '— Không —' }].concat((rooms || []).map(r => ({ value: r.id, label: r.name || r.code }))) },
      { name: 'seat', label: 'Số ghế', value: c.seat },
      { name: 'made', label: 'Mã đề', value: c.made },
      { name: 'absent', label: 'Vắng thi', type: 'checkbox', value: c.absent }
    ], async v => {
      await api('/api/candidates/' + c.id, { method: 'PUT', body: v });
      ok('Đã lưu'); render();
    });
  }
}
