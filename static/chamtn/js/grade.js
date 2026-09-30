/* grade.js - tab cham bai, ket qua, thong ke */
'use strict';

let JOB_WATCH = 0;
function onJobUpdate(j) {
  if (JOB_WATCH && j.id === JOB_WATCH) drawJobPanel(j);
  if (j.status !== 'running' && j.status !== 'queued' && JOB_WATCH === j.id) {
    JOB_WATCH = 0;
    ok('Đã chấm xong ' + (j.done - j.failed) + '/' + j.total + ' phiếu' + (j.failed ? ' · ' + j.failed + ' lỗi' : ''), 'Hoàn tất');
  }
}
function drawJobPanel(j) {
  const box = $('#job-panel');
  if (!box) return;
  box.innerHTML = '';
  const pc = j.percent || 0;
  const st = j.status === 'running' ? 'Đang chấm' : j.status === 'done' ? 'Hoàn tất' : j.status === 'cancelled' ? 'Đã dừng' : j.status === 'error' ? 'Lỗi' : 'Chờ';
  box.appendChild(el('div', { class: 'row', style: 'margin-bottom:8px' }, [
    j.status === 'running' ? el('span', { class: 'spinner' }) : null,
    el('b', { text: st + ': ' + (j.name || 'lô #' + j.id) }),
    el('div', { class: 'grow' }),
    el('span', { class: 'badge ' + (j.failed ? 'warn' : 'ok'), text: j.done + '/' + j.total + ' phiếu' }),
    j.status === 'running' ? el('button', {
      class: 'btn btn-sm', onclick: () => api('/api/batches/' + j.id + '/cancel', { method: 'POST' }).then(() => warn('Đã yêu cầu dừng'))
    }, 'Dừng') : null
  ]));
  const p = el('div', { class: 'progress ' + (j.status === 'done' ? 'ok' : j.status === 'error' ? 'err' : '') });
  p.appendChild(el('div', { style: 'width:' + pc + '%' }));
  box.appendChild(p);
  box.appendChild(el('div', { class: 'row small muted', style: 'margin-top:8px' }, [
    el('span', { text: 'Thành công: ' + (j.ok || 0) }),
    el('span', { text: 'Cần soát: ' + (j.warn || 0) }),
    el('span', { text: 'Lỗi: ' + (j.failed || 0) }),
    el('div', { class: 'grow' }),
    el('span', { text: 'Đã chạy ' + secs(j.elapsed) + (j.eta ? ' · còn ~' + secs(j.eta) : '') })
  ]));
  const lg = el('div', { class: 'file-list', style: 'max-height:230px;margin-top:10px;font-family:var(--mono);font-size:11.6px' });
  (j.recent || []).slice(-40).reverse().forEach(l => lg.appendChild(el('div', {}, [
    el('span', { style: l.indexOf('LỖI') >= 0 ? 'color:var(--err)' : '', text: l })
  ])));
  box.appendChild(lg);
  if (j.status !== 'running' && j.status !== 'queued')
    box.appendChild(el('div', { class: 'row', style: 'margin-top:10px' }, [
      el('button', { class: 'btn btn-primary btn-sm', onclick: () => go('#/exams/' + EX.id + '/results') }, 'Xem kết quả'),
      el('button', { class: 'btn btn-sm', onclick: () => render() }, 'Tải lại')
    ]));
}

/* ---------------- TAB: chấm bài ---------------- */
async function tabGrade(b) {
  b.innerHTML = '';
  if (!EX.keys.length)
    b.appendChild(el('div', { class: 'warnbox', style: 'margin-bottom:14px', html:
      'Kỳ thi <b>chưa có đáp án</b>. Vẫn có thể chấm để đọc phiếu, nhưng điểm sẽ bằng 0 cho đến khi nhập đáp án. ' +
      '<a href="#/exams/' + EX.id + '/keys">Nhập đáp án ngay →</a>' }));

  const left = el('div', { class: 'stack' });
  // vung tha file
  const drop = el('div', { class: 'drop' }, [
    el('div', { class: 'big', text: '⬆' }),
    el('div', { html: '<b>Kéo & thả ảnh phiếu vào đây</b>' }),
    el('div', { class: 'small muted', style: 'margin-top:4px', text: 'hoặc bấm để chọn tệp · JPG, PNG, BMP, TIFF, WEBP · file .ZIP · file .PDF nhiều trang' })
  ]);
  const fi = el('input', { type: 'file', multiple: 'multiple', accept: '.jpg,.jpeg,.png,.bmp,.tif,.tiff,.webp,.zip,.pdf,image/*', class: 'hidden' });
  const fdir = el('input', { type: 'file', multiple: 'multiple', class: 'hidden' });
  fdir.setAttribute('webkitdirectory', ''); fdir.setAttribute('directory', '');
  let files = [];
  const flist = el('div', { class: 'file-list hidden', id: 'g-files' });
  const addFiles = fs => {
    for (const f of fs) {
      if (files.length >= 5000) break;
      files.push(f);
    }
    drawFiles();
  };
  const drawFiles = () => {
    flist.innerHTML = '';
    flist.classList.toggle('hidden', !files.length);
    let total = 0;
    files.forEach((f, i) => {
      total += f.size;
      if (i < 300) flist.appendChild(el('div', {}, [
        el('span', { class: 'grow nowrap', style: 'overflow:hidden;text-overflow:ellipsis', text: (f.webkitRelativePath || f.name) }),
        el('span', { class: 'muted tiny', text: bytes(f.size) }),
        el('button', { class: 'btn btn-sm btn-ghost', onclick: () => { files.splice(i, 1); drawFiles(); } }, '✕')
      ]));
    });
    if (files.length > 300) flist.appendChild(el('div', { class: 'muted', text: '… và ' + (files.length - 300) + ' tệp nữa' }));
    $('#g-count').textContent = files.length ? files.length + ' tệp · ' + bytes(total) : 'chưa chọn tệp';
    $('#g-start').disabled = !files.length;
  };
  drop.addEventListener('click', () => fi.click());
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', async e => {
    e.preventDefault(); drop.classList.remove('over');
    const items = e.dataTransfer.items;
    if (items && items.length && items[0].webkitGetAsEntry) {
      const out = [];
      const walk = (entry, path) => new Promise(res => {
        if (entry.isFile) entry.file(f => { out.push(f); res(); }, res);
        else if (entry.isDirectory) {
          const rd = entry.createReader();
          const read = () => rd.readEntries(async ents => {
            if (!ents.length) { res(); return; }
            for (const en of ents) await walk(en, path + '/' + en.name);
            read();
          }, res);
          read();
        } else res();
      });
      const ents = [];
      for (let i = 0; i < items.length; i++) { const en = items[i].webkitGetAsEntry(); if (en) ents.push(en); }
      for (const en of ents) await walk(en, '');
      addFiles(out);
    } else addFiles(e.dataTransfer.files);
  });
  fi.addEventListener('change', () => { addFiles(fi.files); fi.value = ''; });
  fdir.addEventListener('change', () => { addFiles(fdir.files); fdir.value = ''; });

  const g = el('div');
  g.appendChild(drop);
  g.appendChild(fi); g.appendChild(fdir);
  g.appendChild(el('div', { class: 'row', style: 'margin-top:11px' }, [
    el('button', { class: 'btn btn-sm', onclick: () => fi.click() }, 'Chọn tệp'),
    el('button', { class: 'btn btn-sm', onclick: () => fdir.click() }, 'Chọn cả thư mục'),
    el('button', { class: 'btn btn-sm btn-ghost', onclick: () => { files = []; drawFiles(); } }, 'Bỏ hết'),
    el('div', { class: 'grow' }),
    el('span', { class: 'small muted', id: 'g-count', text: 'chưa chọn tệp' })
  ]));
  g.appendChild(flist);
  g.appendChild(el('div', { style: 'height:12px' }));
  g.appendChild(el('label', { class: 'field' }, [el('span', { text: 'Tên lô (để nhận biết về sau)' }),
    el('input', { id: 'g-name', value: 'Lô ' + todayVN() + ' ' + new Date().toTimeString().slice(0, 5) })]));
  if (CTN.user.role === 'admin')
    g.appendChild(el('label', { class: 'field' }, [
      el('span', { html: 'Hoặc: đường dẫn thư mục trên máy chủ <span class="hint">(quét đệ quy tất cả ảnh)</span>' }),
      el('input', { id: 'g-folder', placeholder: 'VD: D:\\Scan\\GiuaKy1  hoặc  /home/scan/gk1' })]));
  g.appendChild(el('div', { class: 'progress hidden', id: 'g-upprog' }, el('div', { style: 'width:0%' })));
  g.appendChild(el('div', { class: 'small muted hidden', id: 'g-upinfo', style: 'margin-top:5px' }));
  left.appendChild(card('Tải ảnh phiếu lên', g, [
    el('button', { class: 'btn btn-primary', id: 'g-start', disabled: 'disabled', onclick: startGrade }, 'Bắt đầu chấm')
  ]));

  // bang tien trinh
  left.appendChild(card('Tiến trình', el('div', { id: 'job-panel' }, el('div', { class: 'muted small', text: 'Chưa có lô nào đang chạy. Tải ảnh lên và bấm “Bắt đầu chấm”.' })), [
    el('button', { class: 'btn btn-sm', onclick: () => toggleConsole(true) }, 'Mở nhật ký chi tiết')
  ]));

  // lich su lo
  const bt = await api('/api/exams/' + EX.id + '/batches');
  const rows = bt.items.map(x => ({
    name: el('div', {}, [el('b', { text: x.name }), el('div', { class: 'tiny muted', text: x.created_at_txt + ' · ' + (x.owner || '') })]),
    st: el('span', { class: 'badge ' + (x.status === 'done' ? 'ok' : x.status === 'running' ? 'info' : x.status === 'error' ? 'err' : ''), text: { done: 'hoàn tất', running: 'đang chạy', queued: 'chờ', error: 'lỗi', cancelled: 'đã dừng' }[x.status] || x.status }),
    n: x.done + '/' + x.total, f: x.failed ? el('span', { class: 'badge err', text: x.failed }) : '—',
    t: x.secs ? secs(x.secs) : '—',
    act: el('div', { class: 'row tight' }, [
      el('button', { class: 'btn btn-sm', onclick: () => { JOB_WATCH = x.id; api('/api/batches/' + x.id).then(r => drawJobPanel(r.job)); } }, 'Xem'),
      el('button', { class: 'btn btn-sm btn-ghost', onclick: () => confirmBox('Xoá lô này và toàn bộ ' + x.done + ' phiếu đã chấm trong lô?', async () => { await api('/api/batches/' + x.id, { method: 'DELETE' }); ok('Đã xoá'); render(); }, { danger: true }) }, '🗑')
    ])
  }));
  left.appendChild(card('Các lô đã chấm', tableEl([
    { t: 'Lô', k: 'name' }, { t: 'Trạng thái', k: 'st', w: '110px' }, { t: 'Phiếu', k: 'n', w: '90px', align: 'right' },
    { t: 'Lỗi', k: 'f', w: '70px', align: 'center' }, { t: 'Thời gian', k: 't', w: '90px' }, { t: '', k: 'act', w: '110px' }
  ], rows, { short: true, emptyTitle: 'Chưa có lô nào' }), null, { tight: true }));
  b.appendChild(left);

  // dang chay?
  const running = Object.values(CTN.jobs).filter(j => j.exam_id == EX.id && (j.status === 'running' || j.status === 'queued'));
  if (running.length) { JOB_WATCH = running[running.length - 1].id; drawJobPanel(running[running.length - 1]); }

  async function startGrade() {
    const folder = $('#g-folder') ? $('#g-folder').value.trim() : '';
    if (!files.length && !folder) { err('Chưa chọn tệp nào'); return; }
    const btn = $('#g-start');
    btn.disabled = true; btn.textContent = 'Đang tải lên…';
    const fd = new FormData();
    files.forEach(f => fd.append('files', f, f.webkitRelativePath || f.name));
    fd.append('name', $('#g-name').value || '');
    if (folder) fd.append('folder', folder);
    $('#g-upprog').classList.remove('hidden');
    $('#g-upinfo').classList.remove('hidden');
    try {
      const r = await api('/api/exams/' + EX.id + '/grade', {
        method: 'POST', body: fd,
        onProgress: (p, l, t) => {
          $('#g-upprog').firstChild.style.width = (p * 100).toFixed(1) + '%';
          $('#g-upinfo').textContent = 'Đã tải lên ' + bytes(l) + ' / ' + bytes(t) + ' (' + (p * 100).toFixed(0) + '%)';
        }
      });
      $('#g-upinfo').textContent = 'Tải lên xong. Bắt đầu chấm ' + r.total + ' ảnh…';
      (r.skipped || []).forEach(s => warn('Bỏ qua: ' + s));
      JOB_WATCH = r.batch_id;
      files = []; drawFiles();
      ok('Đã bắt đầu chấm ' + r.total + ' phiếu');
      toggleConsole(true);
      const j = await api('/api/batches/' + r.batch_id);
      drawJobPanel(j.job);
    } catch (e) { err(e.message); }
    finally { btn.disabled = false; btn.textContent = 'Bắt đầu chấm'; }
  }
}

/* ---------------- TAB: kết quả ---------------- */
let RES_STATE = { page: 1, per: 50, status: '', q: '', sort: 'sbd', room: 0 };
async function tabResults(b) {
  b.innerHTML = '';
  const bar = el('div', { class: 'row', style: 'margin-bottom:14px' }, [
    el('select', { id: 'r-status', class: 'mini', onchange: e => { RES_STATE.status = e.target.value; RES_STATE.page = 1; loadRows(); } }, [
      el('option', { value: '' }, 'Tất cả trạng thái'),
      el('option', { value: 'need' }, '⚠ Cần xem lại (cảnh báo + lỗi)'),
      el('option', { value: 'ok' }, 'Đã chấm tốt'),
      el('option', { value: 'warn' }, 'Có cảnh báo'),
      el('option', { value: 'review' }, 'Chờ soát'),
      el('option', { value: 'manual' }, 'Đã sửa tay'),
      el('option', { value: 'error' }, 'Lỗi đọc phiếu')
    ]),
    el('select', { id: 'r-room', class: 'mini', onchange: e => { RES_STATE.room = e.target.value; RES_STATE.page = 1; loadRows(); } },
      [el('option', { value: 0 }, 'Tất cả phòng')].concat((EX.rooms || []).map(r => el('option', { value: r.id }, r.name || r.code)))),
    el('select', { id: 'r-sort', class: 'mini', onchange: e => { RES_STATE.sort = e.target.value; loadRows(); } }, [
      el('option', { value: 'sbd' }, 'Sắp theo SBD'),
      el('option', { value: 'score' }, 'Điểm cao → thấp'),
      el('option', { value: 'score_asc' }, 'Điểm thấp → cao'),
      el('option', { value: 'name' }, 'Theo tên'),
      el('option', { value: 'time' }, 'Mới chấm nhất'),
      el('option', { value: 'quality' }, 'Chất lượng ảnh thấp nhất')
    ]),
    el('input', { type: 'search', id: 'r-q', class: 'mini', placeholder: 'Tìm SBD / tên / tệp…', style: 'width:200px', oninput: debounce(e => { RES_STATE.q = e.target.value; RES_STATE.page = 1; loadRows(); }, 350) }),
    el('div', { class: 'grow' }),
    el('button', { class: 'btn btn-sm', onclick: () => download('/api/exams/' + EX.id + '/export?kind=xlsx') }, '⭳ Excel'),
    el('button', { class: 'btn btn-sm', onclick: () => download('/api/exams/' + EX.id + '/export?kind=csv') }, '⭳ CSV'),
    el('button', { class: 'btn btn-sm', onclick: () => window.open('/api/exams/' + EX.id + '/export?kind=pdf', '_blank') }, '⭳ Bảng điểm PDF'),
    el('button', { class: 'btn btn-sm', onclick: exportSheetsPdf }, '⭳ Phiếu đã chấm (PDF)'),
    el('button', { class: 'btn btn-sm', onclick: () => confirmBox('Chấm lại toàn bộ phiếu theo đáp án & thang điểm hiện tại?', async () => { const r = await api('/api/exams/' + EX.id + '/regrade', { method: 'POST' }); ok('Đã chấm lại ' + r.count + ' phiếu'); loadRows(); }) }, '↻ Chấm lại')
  ]);
  b.appendChild(bar);
  b.appendChild(el('div', { id: 'r-sum', class: 'grid g5', style: 'margin-bottom:14px' }));
  b.appendChild(el('div', { id: 'r-table' }));
  $('#r-status').value = RES_STATE.status;
  $('#r-sort').value = RES_STATE.sort;
  $('#r-q').value = RES_STATE.q;
  await loadSum();
  await loadRows();

  async function loadSum() {
    try {
      const s = await api('/api/exams/' + EX.id + '/stats');
      const box = $('#r-sum');
      box.innerHTML = '';
      [statCard('Đã chấm', num(s.count), 'phiếu hợp lệ', 'b'),
        statCard('Điểm TB', sc2(s.avg), 'cao nhất ' + sc2(s.max) + ' · thấp nhất ' + sc2(s.min), 'g'),
        statCard('Tỉ lệ đạt', sc2(s.pass_rate) + '%', s.pass + ' em ≥ 5đ', ''),
        statCard('Cần xem lại', num(s.need_review), 'phiếu có cảnh báo', s.need_review ? 'w' : ''),
        statCard('Lỗi đọc', num(s.errors), 'phiếu không đọc được', s.errors ? 'r' : '')
      ].forEach(c => box.appendChild(c));
    } catch (e) { }
  }
  async function loadRows() {
    const t = $('#r-table');
    t.innerHTML = '<div class="loading"><span class="spinner"></span></div>';
    const qs = '?page=' + RES_STATE.page + '&per=' + RES_STATE.per + '&status=' + encodeURIComponent(RES_STATE.status) +
      '&q=' + encodeURIComponent(RES_STATE.q) + '&sort=' + RES_STATE.sort + '&room_id=' + RES_STATE.room;
    const r = await api('/api/exams/' + EX.id + '/sheets' + qs);
    RESULT_IDS = r.items.map(x => x.id);
    const rows = r.items.map(x => ({
      __cls: x.status === 'error' ? 'err' : null,
      __click: () => openReview(x.id),
      sbd: el('b', { class: 'mono', text: x.sbd || '—' }),
      made: x.made || '—',
      name: el('div', {}, [el('span', { text: x.full_name || '(chưa khớp học sinh)' }),
        el('div', { class: 'tiny muted', text: [x.class_name, x.room_name].filter(Boolean).join(' · ') })]),
      score: x.status === 'error' ? el('span', { class: 'muted', text: '—' }) : scoreEl(x.score),
      p: x.status === 'error' ? '' : el('span', { class: 'tiny muted', text: sc2(x.p1) + ' / ' + sc2(x.p2) + ' / ' + sc2(x.p3) }),
      dsb: el('span', { class: 'tiny' , html: '<span style="color:var(--ok)">' + x.n_correct + '</span> · <span style="color:var(--err)">' + x.n_wrong + '</span> · <span class="muted">' + x.n_blank + '</span>' }),
      q: el('span', { class: 'tiny ' + (x.quality < 50 ? 'sc lo' : 'muted'), text: Math.round(x.quality) + '/100' }),
      st: el('div', {}, [statusBadge(x.status, x.status_txt),
        (x.warns && x.warns.length) ? el('div', { class: 'tiny muted nowrap', style: 'max-width:230px;overflow:hidden;text-overflow:ellipsis', text: x.warns[0] }) : null]),
      time: el('span', { class: 'tiny muted', text: x.time_txt }),
      act: el('div', { class: 'row tight', onclick: e => e.stopPropagation() }, [
        el('button', { class: 'btn btn-sm', onclick: () => openReview(x.id) }, 'Soát'),
        el('button', { class: 'btn btn-sm btn-ghost', title: 'Tải PDF phiếu', onclick: () => window.open('/api/sheets/' + x.id + '/pdf', '_blank') }, '⭳' )
      ])
    }));
    t.innerHTML = '';
    t.appendChild(card(null, tableEl([
      { t: 'SBD', k: 'sbd', w: '100px' }, { t: 'Mã đề', k: 'made', w: '72px' }, { t: 'Học sinh', k: 'name' },
      { t: 'Điểm', k: 'score', w: '70px', align: 'right' },
      { t: 'I / II / III', k: 'p', w: '120px', align: 'right' },
      { t: 'Đ·S·Trống', k: 'dsb', w: '105px', align: 'center' },
      { t: 'Ảnh', k: 'q', w: '74px', align: 'center' },
      { t: 'Trạng thái', k: 'st', w: '190px' },
      { t: 'Lúc', k: 'time', w: '110px' },
      { t: '', k: 'act', w: '110px' }
    ], rows, { emptyTitle: 'Chưa có phiếu nào', emptyText: 'Chuyển sang tab “Chấm bài” để tải ảnh lên.' }), null, { tight: true }));
    t.appendChild(pager(RES_STATE.page, RES_STATE.per, r.total, p => { RES_STATE.page = p; loadRows(); }));
  }
  function exportSheetsPdf() {
    promptBox('Xuất phiếu đã chấm ra PDF', [
      { type: 'html', html: '<p class="small muted">Mỗi phiếu gồm 1 trang ảnh có overlay đúng/sai và 1 trang chi tiết đáp án.</p>' },
      { name: 'status', label: 'Chọn phiếu', type: 'select', value: 'all', options: [
        { value: 'all', label: 'Tất cả phiếu' }, { value: 'ok', label: 'Chỉ phiếu đã chấm tốt' },
        { value: 'warn', label: 'Chỉ phiếu có cảnh báo' }, { value: 'manual', label: 'Chỉ phiếu đã sửa tay' }] },
      { name: 'limit', label: 'Số phiếu tối đa', type: 'number', value: 300, hint: '(tối đa 2000)' }
    ], v => {
      window.open('/api/exams/' + EX.id + '/export?kind=sheets&status=' + v.status + '&limit=' + v.limit, '_blank');
      ok('Đang tạo PDF, vui lòng đợi…');
    }, { submit: 'Tạo PDF' });
  }
}
let RESULT_IDS = [];

/* ---------------- TAB: thống kê ---------------- */
async function tabStats(b) {
  b.innerHTML = '<div class="loading"><span class="spinner"></span> Đang tính toán…</div>';
  const s = await api('/api/exams/' + EX.id + '/stats');
  b.innerHTML = '';
  if (!s.count) {
    b.appendChild(el('div', { class: 'card card-pad' }, el('div', { class: 'empty' }, [
      el('b', { text: 'Chưa có dữ liệu thống kê' }), el('span', { text: 'Hãy chấm ít nhất một phiếu.' })])));
    return;
  }
  b.appendChild(el('div', { class: 'grid g5', style: 'margin-bottom:16px' }, [
    statCard('Số phiếu', num(s.count), '', 'b'),
    statCard('Điểm trung bình', sc2(s.avg), 'trung vị ' + sc2(s.median), 'g'),
    statCard('Cao nhất', sc2(s.max), 'thấp nhất ' + sc2(s.min), ''),
    statCard('Độ lệch chuẩn', sc2(s.stdev), 'mức phân tán', ''),
    statCard('Tỉ lệ đạt', sc2(s.pass_rate) + '%', s.pass + '/' + s.count + ' em ≥ 5đ', s.pass_rate >= 50 ? 'g' : 'w')
  ]));

  // phan phoi diem
  const dist = s.dist || [];
  const maxn = Math.max(1, ...dist.map(d => d.n));
  const chart = el('div', {});
  const bars = el('div', { class: 'bar-chart' });
  dist.forEach(d => {
    const bar = el('div', { class: 'bar', style: 'height:' + (d.n / maxn * 100) + '%', title: d.label + ': ' + d.n + ' em (' + sc2(d.pct) + '%)' });
    if (d.n) bar.appendChild(el('span', { text: d.n }));
    bars.appendChild(bar);
  });
  chart.appendChild(bars);
  const labs = el('div', { class: 'bar-labels' });
  dist.forEach(d => labs.appendChild(el('div', { text: d.label })));
  chart.appendChild(labs);
  b.appendChild(card('Phân phối điểm', chart));
  b.appendChild(el('div', { style: 'height:16px' }));

  // tung cau
  const qwrap = el('div', { class: 'stack' });
  const mkQ = (title, arr, keyfmt) => {
    if (!arr || !arr.length) return null;
    const box = el('div');
    const bars2 = el('div', { class: 'bar-chart qbar' });
    arr.forEach(q => {
      const cls = q.pct >= 70 ? 'g' : q.pct >= 40 ? 'w' : 'r';
      bars2.appendChild(el('div', {
        class: 'bar ' + cls, style: 'height:' + Math.max(2, q.pct) + '%',
        title: 'Câu ' + q.q + ' · đáp án ' + (q.key || '?') + ' · ' + sc2(q.pct) + '% đúng' +
          (q.disc !== undefined ? ' · độ phân cách ' + sc2(q.disc) : '')
      }));
    });
    box.appendChild(bars2);
    const l2 = el('div', { class: 'bar-labels' });
    arr.forEach(q => l2.appendChild(el('div', { text: q.q })));
    box.appendChild(l2);
    // bang chi tiet
    const rows = arr.map(q => ({
      q: 'Câu ' + q.q, key: el('b', { class: 'mono', text: q.key || '—' }),
      pct: el('span', { class: 'sc ' + (q.pct >= 50 ? 'hi' : 'lo'), text: sc2(q.pct) + '%' }),
      c: q.correct, w: q.wrong, bl: q.blank === undefined ? '—' : q.blank,
      disc: q.disc === undefined ? '—' : sc2(q.disc),
      pick: q.pick ? Object.keys(q.pick).sort().map(k => k + ':' + q.pick[k]).join('  ') : ''
    }));
    box.appendChild(el('div', { style: 'height:10px' }));
    box.appendChild(tableEl([
      { t: 'Câu', k: 'q', w: '80px' }, { t: 'Đáp án', k: 'key', w: '80px' },
      { t: '% đúng', k: 'pct', w: '90px', align: 'right' },
      { t: 'Đúng', k: 'c', w: '70px', align: 'right' }, { t: 'Sai', k: 'w', w: '70px', align: 'right' },
      { t: 'Bỏ trống', k: 'bl', w: '80px', align: 'right' },
      { t: 'Độ phân cách', k: 'disc', w: '110px', align: 'right' },
      { t: 'Học sinh chọn', k: 'pick' }
    ], rows, { short: true }));
    return card(title, box);
  };
  const q1 = mkQ('Phần I – phân tích từng câu', s.p1_stats); if (q1) qwrap.appendChild(q1);
  const q2 = mkQ('Phần II – phân tích từng câu', s.p2_stats); if (q2) qwrap.appendChild(q2);
  const q3 = mkQ('Phần III – phân tích từng câu', s.p3_stats); if (q3) qwrap.appendChild(q3);
  b.appendChild(qwrap);
  b.appendChild(el('div', { style: 'height:16px' }));

  const grp = (title, arr) => {
    if (!arr || !arr.length) return null;
    const rows = arr.map(g => ({
      name: g.name, n: num(g.n), avg: scoreEl(g.avg), min: sc2(g.min), max: sc2(g.max),
      pass: el('span', { class: 'badge ' + (g.pass_rate >= 50 ? 'ok' : 'warn'), text: sc2(g.pass_rate) + '%' })
    }));
    return card(title, tableEl([
      { t: 'Nhóm', k: 'name' }, { t: 'Số HS', k: 'n', w: '80px', align: 'right' },
      { t: 'Điểm TB', k: 'avg', w: '90px', align: 'right' }, { t: 'Thấp nhất', k: 'min', w: '90px', align: 'right' },
      { t: 'Cao nhất', k: 'max', w: '90px', align: 'right' }, { t: 'Tỉ lệ đạt', k: 'pass', w: '100px', align: 'center' }
    ], rows, { short: true }), null, { tight: true });
  };
  const gwrap = el('div', { class: 'stack' });
  [grp('Theo lớp', s.by_class), grp('Theo phòng thi', s.by_room), grp('Theo mã đề', s.by_made)]
    .filter(Boolean).forEach(c => gwrap.appendChild(c));
  b.appendChild(gwrap);
}
