/* review.js - soat & sua tay ket qua mot phieu */
'use strict';

let RV = null;

async function openReview(id) {
  const r = await api('/api/sheets/' + id);
  RV = r.sheet;
  RV.edit = JSON.parse(JSON.stringify(RV.ans || {}));
  const C = RV.counts;
  const key = RV.key || null;
  const det = RV.detail || {};

  const body = el('div', { class: 'split', style: 'gap:16px' });

  /* ---- cot phai: anh ---- */
  const right = el('div', { class: 'stack' });
  const imgSrc = '/api/sheets/' + RV.id + '/image?overlay=1&t=' + Date.now();
  const ib = el('div', { class: 'imgbox' }, [
    el('div', { class: 'ib-bar' }, [
      el('b', { text: 'Ảnh phiếu' }),
      el('span', { class: 'muted tiny', text: RV.orig_name }),
      el('div', { class: 'grow' }),
      el('label', { class: 'mini-check' }, [
        el('input', { type: 'checkbox', id: 'rv-ov', checked: RV.has_overlay ? 'checked' : null, onchange: e => { $('#rv-img').src = '/api/sheets/' + RV.id + '/image?overlay=' + (e.target.checked ? 1 : 0) + '&t=' + Date.now(); } }),
        el('span', { text: 'hiện đánh dấu' })
      ]),
      el('button', { class: 'btn btn-sm btn-ghost', onclick: () => window.open('/api/sheets/' + RV.id + '/image?dl=1', '_blank'), title: 'Tải ảnh gốc' }, '⭳')
    ]),
    el('img', { id: 'rv-img', src: imgSrc, alt: 'phiếu', onclick: () => lightbox($('#rv-img').src) })
  ]);
  right.appendChild(ib);
  const qinfo = el('div', { class: 'kv' }, [
    el('dt', { text: 'Chất lượng ảnh' }), el('dd', { text: Math.round(RV.quality) + '/100' }),
    el('dt', { text: 'Độ tin cậy' }), el('dd', { text: Math.round(RV.confidence * 100) + '%' }),
    el('dt', { text: 'Cách định vị' }), el('dd', { text: det.method === 'fiducial' ? 'ô định vị góc' : (det.method || '—') }),
    el('dt', { text: 'Xoay ảnh' }), el('dd', { text: (det.rotation ? det.rotation * 90 : 0) + '°' }),
    el('dt', { text: 'Tương phản' }), el('dd', { text: sc2(det.contrast) }),
    el('dt', { text: 'Độ nét' }), el('dd', { text: sc2(det.sharpness) }),
    el('dt', { text: 'Tách biệt ô tô' }), el('dd', { text: sc2(det.separation) }),
    el('dt', { text: 'Khớp lưới ô tròn' }), el('dd', { text: sc2(det.grid) }),
    el('dt', { text: 'Kênh đọc vết bút' }), el('dd', { text: det.mark_channel === 'loai-hong' ? 'loại nét in hồng' : 'kênh mực (min RGB)' }),
    el('dt', { text: 'Thời gian xử lý' }), el('dd', { text: RV.ms + ' ms' }),
    el('dt', { text: 'Chấm lúc' }), el('dd', { text: RV.time_txt })
  ]);
  right.appendChild(card('Thông tin nhận dạng', qinfo));

  /* ---- cot trai: thong tin + dap an ---- */
  const left = el('div', { class: 'stack' });
  const hd = el('div');
  hd.appendChild(el('div', { class: 'row', style: 'margin-bottom:12px' }, [
    el('label', { class: 'field', style: 'margin:0;flex:1' }, [el('span', { text: 'Số báo danh' }),
      el('input', { id: 'rv-sbd', class: 'mono', value: RV.ans.sbd || '', maxlength: 12 })]),
    el('label', { class: 'field', style: 'margin:0;width:110px' }, [el('span', { text: 'Mã đề' }),
      el('input', { id: 'rv-made', class: 'mono', value: RV.ans.made || '', maxlength: 8 })]),
    el('div', { style: 'text-align:right;min-width:120px' }, [
      el('div', { class: 'small muted', text: 'Điểm hiện tại' }),
      el('div', { id: 'rv-score', style: 'font-size:26px;font-weight:700', class: RV.score >= 5 ? 'sc hi' : 'sc lo', text: sc2(RV.score) })
    ])
  ]));
  hd.appendChild(el('div', { class: 'row small muted' }, [
    el('span', { html: '<b>' + esc(RV.full_name || '(chưa khớp học sinh)') + '</b>' }),
    RV.class_name ? el('span', { text: '· ' + RV.class_name }) : null,
    RV.room_name ? el('span', { text: '· ' + RV.room_name }) : null,
    el('div', { class: 'grow' }),
    statusBadge(RV.status, RV.status_txt),
    el('span', { text: 'Đ ' + RV.n_correct + ' · S ' + RV.n_wrong + ' · trống ' + RV.n_blank })
  ]));
  if (RV.warns && RV.warns.length) {
    const ul = el('ul');
    RV.warns.forEach(w => ul.appendChild(el('li', { text: w })));
    hd.appendChild(el('div', { class: 'warnbox', style: 'margin-top:10px' }, [el('b', { text: 'Cần kiểm tra:' }), ul]));
  }
  if (det.infos && det.infos.length) {
    const ul = el('ul');
    det.infos.forEach(w => ul.appendChild(el('li', { text: w })));
    hd.appendChild(el('div', { class: 'small muted', style: 'margin-top:8px' }, [el('b', { text: 'Ghi nhận khi xử lý ảnh:' }), ul]));
  }
  left.appendChild(card(null, hd));

  const mkSection = (title, kind) => {
    const box = el('div');
    if (kind === 'p1') {
      const g = el('div', { class: 'ansgrid bycol', style: '--cw:172px' });
      const items = det.p1_items || [];
      const byIdx = {}; items.forEach(i => byIdx[i.i] = i);
      for (let i = 1; i <= C.p1; i++) {
        const it = byIdx[i];
        const got = (RV.edit.p1 && RV.edit.p1[i - 1]) || '';
        const want = it ? it.want : (key && key.p1 ? key.p1[i - 1] : '');
        const st = it ? it.st : (got ? 9 : 2);
        const cls = st === 0 ? 'c' : st === 1 ? 'w' : st === 3 ? 'm' : st === 2 ? 'b' : '';
        const cell = el('div', { class: 'ansitem ' + cls });
        cell.appendChild(el('span', { class: 'n', text: i + '.' }));
        const btns = el('div', { class: 'abcd' });
        'ABCD'.split('').forEach(L => {
          const on = got.indexOf(L) >= 0;
          btns.appendChild(el('button', {
            class: (on ? 'on' : '') + (want === L ? ' key' : ''),
            title: want === L ? 'đáp án đúng' : '',
            onclick: e => {
              RV.edit.p1[i - 1] = (RV.edit.p1[i - 1] === L) ? '' : L;
              Array.from(btns.children).forEach(c => c.classList.toggle('on', c.textContent === RV.edit.p1[i - 1]));
              markDirty();
            }
          }, L));
        });
        cell.appendChild(btns);
        if (want && st !== 0) cell.appendChild(el('span', { class: 'key', text: want }));
        g.appendChild(cell);
      }
      box.appendChild(g);
    } else if (kind === 'p2') {
      const g = el('div', { class: 'ansgrid', style: 'grid-template-columns:repeat(auto-fill,minmax(258px,1fr))' });
      const items = det.p2_items || [];
      const byIdx = {}; items.forEach(i => byIdx[i.i] = i);
      for (let i = 1; i <= C.p2; i++) {
        const it = byIdx[i];
        const want = it ? it.want : (key && key.p2 ? key.p2[i - 1] : '');
        let got = ((RV.edit.p2 && RV.edit.p2[i - 1]) || '').padEnd(C.p2_subs, '-');
        const cls = it ? (it.st === 0 ? 'c' : it.st === 1 ? 'w' : 'm') : '';
        const cell = el('div', { class: 'ansitem ' + cls }, [el('span', { class: 'n', text: 'C' + i })]);
        for (let j = 0; j < C.p2_subs; j++) {
          const wch = want ? want[j] : '';
          const bt = el('button', { class: 'btn btn-sm', style: 'min-width:32px;padding:2px 5px' });
          const paint = () => {
            const c = RV.edit.p2[i - 1].padEnd(C.p2_subs, '-')[j];
            bt.textContent = 'abcd'[j] + (c === 'D' ? 'Đ' : c === 'S' ? 'S' : c === '?' ? '?' : '·');
            bt.className = 'btn btn-sm' + (c === 'D' ? ' btn-ok' : c === 'S' ? ' btn-danger' : '');
            bt.title = wch ? 'đáp án: ' + (wch === 'D' ? 'Đúng' : 'Sai') : '';
            bt.style.boxShadow = (wch && c === wch) ? 'inset 0 0 0 2px var(--ok)' : (wch && c !== '-' && c !== wch ? 'inset 0 0 0 2px var(--err)' : '');
          };
          bt.addEventListener('click', () => {
            const order = ['D', 'S', '-'];
            let c = RV.edit.p2[i - 1].padEnd(C.p2_subs, '-');
            const cur = order.indexOf(c[j]);
            const nx = order[(cur + 1) % 3];
            RV.edit.p2[i - 1] = c.substring(0, j) + nx + c.substring(j + 1);
            paint(); markDirty();
          });
          paint();
          cell.appendChild(bt);
        }
        if (want) cell.appendChild(el('span', { class: 'key', text: want.replace(/D/g, 'Đ') }));
        g.appendChild(cell);
      }
      box.appendChild(g);
    } else {
      const g = el('div', { class: 'ansgrid', style: 'grid-template-columns:repeat(auto-fill,minmax(190px,1fr))' });
      const items = det.p3_items || [];
      const byIdx = {}; items.forEach(i => byIdx[i.i] = i);
      for (let i = 1; i <= C.p3; i++) {
        const it = byIdx[i];
        const want = it ? it.want : (key && key.p3 ? key.p3[i - 1] : '');
        const cls = it ? (it.st === 0 ? 'c' : it.st === 2 ? 'b' : 'w') : '';
        g.appendChild(el('div', { class: 'ansitem ' + cls }, [
          el('span', { class: 'n', text: i + '.' }),
          el('input', {
            class: 'mono', value: (RV.edit.p3 && RV.edit.p3[i - 1]) || '', maxlength: 8,
            oninput: e => { RV.edit.p3[i - 1] = e.target.value.replace('.', ','); markDirty(); }
          }),
          want ? el('span', { class: 'key', text: want }) : null
        ]));
      }
      box.appendChild(g);
    }
    return card(title, box);
  };
  left.appendChild(mkSection('PHẦN I – ' + C.p1 + ' câu (viền xanh = đáp án đúng)', 'p1'));
  if (C.p2) left.appendChild(mkSection('PHẦN II – Đúng/Sai (bấm để đổi Đ → S → bỏ)', 'p2'));
  if (C.p3) left.appendChild(mkSection('PHẦN III – Trả lời ngắn', 'p3'));

  body.appendChild(left);
  body.appendChild(right);

  const idx = RESULT_IDS.indexOf(RV.id);
  modal({
    title: 'Soát phiếu · SBD ' + (RV.ans.sbd || '?') + (RV.full_name ? ' · ' + RV.full_name : ''),
    size: 'xwide', body, focus: false,
    buttons: [
      { text: '‹ Phiếu trước', onClick: () => { if (idx > 0) { closeModal(); openReview(RESULT_IDS[idx - 1]); } } },
      { text: 'Phiếu sau ›', onClick: () => { if (idx >= 0 && idx < RESULT_IDS.length - 1) { closeModal(); openReview(RESULT_IDS[idx + 1]); } } },
      { text: '↻ Chấm lại từ ảnh', onClick: rescan },
      { text: '🗑 Xoá phiếu', class: 'btn-ghost', onClick: delSheet },
      { text: 'Đóng', onClick: closeModal },
      { text: '✓ Lưu & tính điểm lại', class: 'btn-primary', id: 'rv-save', onClick: saveReview }
    ]
  });

  function markDirty() {
    const b = $('#rv-save');
    if (b) { b.classList.add('btn-primary'); b.textContent = '✓ Lưu & tính điểm lại *'; }
  }
  async function saveReview() {
    const b = $('#rv-save');
    b.disabled = true;
    try {
      const r = await api('/api/sheets/' + RV.id, {
        method: 'PUT', body: {
          sbd: $('#rv-sbd').value.trim(), made: $('#rv-made').value.trim(),
          p1: RV.edit.p1, p2: RV.edit.p2, p3: RV.edit.p3
        }
      });
      ok('Đã lưu · điểm mới: ' + sc2(r.score));
      closeModal();
      if (typeof tabResults === 'function' && location.hash.indexOf('/results') > 0) render();
    } catch (e) { err(e.message); }
    finally { if ($('#rv-save')) $('#rv-save').disabled = false; }
  }
  function rescan() {
    confirmBox('Chấm lại phiếu này từ ảnh gốc? Các sửa tay hiện tại sẽ bị mất.', async () => {
      try {
        const r = await api('/api/sheets/' + RV.id + '/rescan', { method: 'POST' });
        closeModal();
        if (r.new_id) { ok('Đã chấm lại'); openReview(r.new_id); }
        else { err(r.error || 'Không chấm lại được'); render(); }
      } catch (e) { err(e.message); }
    });
  }
  function delSheet() {
    confirmBox('Xoá phiếu này khỏi kết quả?', async () => {
      await api('/api/sheets/' + RV.id, { method: 'DELETE' });
      ok('Đã xoá'); closeModal(); render();
    }, { danger: true });
  }
}
