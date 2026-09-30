/* dash.js - trang tong quan */
'use strict';

route('dashboard', async (v) => {
  crumb('Tổng quan');
  const st = await api('/api/stats');
  v.innerHTML = '';

  const head = el('div', { class: 'page-head' }, [
    el('div', {}, [
      el('h1', { text: 'Xin chào, ' + (CTN.user.full_name || CTN.user.username) }),
      el('div', { class: 'sub', text: 'Hôm nay ' + todayVN() + ' · ' + (CTN.user.role === 'admin' ? 'Quản trị viên' : 'Giáo viên') })
    ]),
    el('div', { class: 'grow' }),
    el('button', { class: 'btn btn-primary', onclick: () => newExam() }, '+ Kỳ thi mới'),
    el('button', { class: 'btn', onclick: () => go('#/try') }, 'Chấm thử một phiếu')
  ]);
  v.appendChild(head);

  const stats = el('div', { class: 'grid g5' }, [
    statCard('Kỳ thi', num(st.n_exams), 'đang quản lý', 'b'),
    statCard('Phiếu đã chấm', num(st.n_sheets), st.n_today ? '+' + num(st.n_today) + ' hôm nay' : 'tổng cộng', 'g'),
    statCard('Cần xem lại', num(st.n_warn), 'phiếu có cảnh báo', st.n_warn > 0 ? 'w' : ''),
    statCard('Học sinh', num(st.n_students), num(st.n_classes) + ' lớp', ''),
    statCard('Đang chấm', num(st.active_jobs), 'lô ảnh', st.active_jobs > 0 ? 'b' : '')
  ]);
  v.appendChild(stats);
  v.appendChild(el('div', { style: 'height:16px' }));

  const wrap = el('div', { class: 'split' });
  // ky thi gan day
  const rows = (st.recent_exams || []).map(e => ({
    __click: () => go('#/exams/' + e.id),
    name: e.name, code: e.code || '—', subject: e.subject || '—',
    date: e.exam_date_txt || '—', n: num(e.n_sheets), status: e.status
  }));
  wrap.appendChild(card('Kỳ thi gần đây', tableEl([
    { t: 'Tên kỳ thi', k: 'name' },
    { t: 'Mã', k: 'code', w: '90px' },
    { t: 'Môn', k: 'subject', w: '110px' },
    { t: 'Ngày thi', k: 'date', w: '100px' },
    { t: 'Phiếu', k: 'n', align: 'right', w: '70px' }
  ], rows, { short: true, emptyTitle: 'Chưa có kỳ thi nào', emptyText: 'Bấm “Kỳ thi mới” để bắt đầu' }),
    [el('button', { class: 'btn btn-sm', onclick: () => go('#/exams') }, 'Xem tất cả')], { tight: true }));

  // huong dan nhanh
  const guide = el('div', { class: 'stack' });
  const steps = [
    ['1', 'Tạo lớp &amp; nhập học sinh', 'Nhập từ file Excel/CSV hoặc thêm tay.', '#/students'],
    ['2', 'Tạo kỳ thi &amp; chọn cách tính điểm', 'Có sẵn thang điểm tốt nghiệp THPT 2025.', '#/exams'],
    ['3', 'Nhập đáp án theo từng mã đề', 'Nhập tay, dán nhanh hoặc tải file Excel.', '#/exams'],
    ['4', 'Tải ảnh phiếu lên và chấm', 'Ảnh scan, ảnh điện thoại, thư mục hoặc file .zip / .pdf.', '#/exams'],
    ['5', 'Soát phiếu cảnh báo &amp; xuất kết quả', 'Xuất Excel, CSV, PDF có overlay đúng/sai.', '#/exams']
  ];
  const gl = el('div');
  steps.forEach(s => {
    gl.appendChild(el('div', { class: 'row', style: 'padding:9px 0;border-bottom:1px solid var(--line);align-items:flex-start' }, [
      el('span', { class: 'badge brand', style: 'min-width:24px;justify-content:center', text: s[0] }),
      el('div', { style: 'flex:1' }, [
        el('div', { html: '<b>' + s[1] + '</b>' }),
        el('div', { class: 'small muted', html: s[2] })
      ]),
      el('a', { href: s[3], class: 'btn btn-sm' }, 'Mở')
    ]));
  });
  guide.appendChild(card('Bắt đầu nhanh', gl));
  guide.appendChild(card('Mẫu phiếu đang dùng', el('div', {}, [
    el('p', { class: 'small muted', style: 'margin:0 0 10px',
      html: 'Phiếu trả lời trắc nghiệm theo <b>CV 1239/BGDĐT-QLCL</b> (áp dụng từ 2025): 40 câu Phần I, 8 câu Đúng/Sai Phần II, 6 câu trả lời ngắn Phần III, 8 chữ số báo danh, 4 chữ số mã đề.' }),
    el('div', { class: 'row' }, [
      el('button', { class: 'btn btn-sm', onclick: () => window.open('/api/templates/moet2025_40/blank.pdf?count=1', '_blank') }, 'In phiếu trống (PDF)'),
      el('button', { class: 'btn btn-sm', onclick: () => go('#/templates') }, 'Xem mẫu phiếu')
    ])
  ])));
  wrap.appendChild(guide);
  v.appendChild(wrap);
});
