// ========== State ==========
let corpusData = [];
let refsData = [];
let stylesData = {};
let selectedId = null;
let selectedRefForRegen = null;
let selectedRefs = {};
let activeStyle = 'all';
let activeTab = 'unlocked';
let checkedIds = new Set();
let lastCheckedId = null;
let sortRating = 'none'; // rating sort mode
let filterRating = 'none'; // rating filter
const RATING_LABELS = { excellent: '优秀', good: '良好', fair: '一般', poor: '差' };

// ========== API ==========
async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  return res.json();
}

// ========== Load Data ==========
async function loadData() {
  const [corpusRes, refsRes] = await Promise.all([
    api('/api/corpus'),
    api('/api/refs')
  ]);
  corpusData = corpusRes.corpus;
  refsData = refsRes.refs;
  stylesData = refsRes.styles;
  updateStatusBar();
  updateTabCounts();
  renderList();
}

function updateTabCounts() {
  const unlocked = corpusData.filter(c => !c.locked).length;
  const locked = corpusData.filter(c => c.locked).length;
  document.getElementById('unlockedCount').textContent = `(${unlocked})`;
  document.getElementById('lockedCount').textContent = `(${locked})`;
}

function switchTab(tab) {
  activeTab = tab;
  document.getElementById('tabUnlocked').classList.toggle('active', tab === 'unlocked');
  document.getElementById('tabLocked').classList.toggle('active', tab === 'locked');
  renderList();
}

function updateStatusBar() {
  const gen = corpusData.filter(c => c.generated).length;
  document.getElementById('statusBar').textContent = `已生成 ${gen} / ${corpusData.length} 条`;
  updateTabCounts();
}

// ========== Render List ==========
function renderList() {
  const search = document.getElementById('searchInput').value.trim();
  const statusFilter = document.getElementById('statusFilter').value;
  const ratingFilter = document.querySelector('.filter-btn.active')?.dataset.value || 'none';
  const ratingSort = document.getElementById('ratingSort').value;
  const list = document.getElementById('corpusList');

  // Filter
  let items = corpusData.filter(item => {
    if (activeTab === 'locked' && !item.locked) return false;
    if (activeTab === 'unlocked' && item.locked) return false;
    if (statusFilter === 'generated' && !item.generated) return false;
    if (statusFilter === 'pending' && item.generated) return false;
    if (ratingFilter !== 'none' && item.rating !== ratingFilter) return false;
    if (search) {
      const s = search.toLowerCase();
      if (!item.id.toString().includes(s) && !item.text.toLowerCase().includes(s)) return false;
    }
    return true;
  });

  // Sort by rating if needed
  const ratingOrder = { poor: 0, fair: 1, good: 2, excellent: 3 };
  if (ratingSort === 'rating_asc') {
    items.sort((a, b) => (ratingOrder[a.rating] || -1) - (ratingOrder[b.rating] || -1));
  } else if (ratingSort === 'rating_desc') {
    items.sort((a, b) => (ratingOrder[b.rating] || -1) - (ratingOrder[a.rating] || -1));
  }

  let html = '';
  for (const item of items) {
    const badgeClass = item.generated ? 'badge-done' : 'badge-pending';
    const badgeText = item.generated ? '已生成' : '未生成';
    const isActive = item.id === selectedId ? ' active' : '';
    const checked = checkedIds.has(item.id) ? ' checked' : '';
    const refBadge = item.ref_name ? (() => {
      const ref = refsData.find(r => r.name === item.ref_name);
      const styleLabel = ref ? ref.style_label : '';
      return `<span style="font-size:10px;color:#aaa;white-space:nowrap;">[${item.ref_name}${styleLabel ? '/' + styleLabel : ''}]</span>`;
    })() : '';
    const refInfo = item.ref_name ? (() => {
      const ref = refsData.find(r => r.name === item.ref_name);
      const styleLabel = ref ? ref.style_label : '';
      return `<span class="ref-info">🎵${item.ref_name}${styleLabel ? ' · ' + styleLabel : ''}</span>`;
    })() : '';
    const lockIcon = item.locked ? '🔒' : '🔓';
    const itemStyle = item.locked ? 'opacity: 0.6;' : '';
    const ratingBadge = item.rating ? `<span class="rating-badge rating-${item.rating}">${RATING_LABELS[item.rating]}</span>` : '';

    html += `<div class="corpus-item${isActive}" data-id="${item.id}" onclick="selectItem(${item.id}, event)" style="${itemStyle}">
      <input class="checkbox" type="checkbox" ${checked} onclick="event.stopPropagation();toggleCheck(${item.id}, event)" />
      <div class="item-main">
        <div class="item-top">
          <span class="item-id">${String(item.id).padStart(4, '0')}</span>
          <span class="item-text" title="${escHtml(item.text)}">${escHtml(item.text)}</span>
          <span class="badge ${badgeClass}">${badgeText}</span>
        </div>
        <div class="item-meta">
          <div class="item-meta-left">${refInfo}</div>
          <div class="item-meta-right">${ratingBadge}</div>
        </div>
      </div>
      <span class="lock-btn" onclick="event.stopPropagation();toggleLock(${item.id})" title="${item.locked ? '点击解锁' : '点击锁定'}">${lockIcon}</span>
    </div>`;
  }

  list.innerHTML = html || '<div class="empty-state">没有匹配结果</div>';
  updateBatchButtons();
}

// ========== Selection ==========
function selectItem(id, event) {
  const e = event || window.event;
  const ctrlKey = e && (e.ctrlKey || e.metaKey);
  const shiftKey = e && e.shiftKey;

  // Handle Ctrl/Shift selection
  if (ctrlKey || shiftKey) {
    if (shiftKey && lastCheckedId !== null) {
      const allIds = corpusData.map(c => c.id);
      const fromIdx = allIds.indexOf(lastCheckedId);
      const toIdx = allIds.indexOf(id);
      const start = Math.min(fromIdx, toIdx);
      const end = Math.max(fromIdx, toIdx);
      for (let i = start; i <= end; i++) checkedIds.add(allIds[i]);
    } else if (ctrlKey) {
      if (checkedIds.has(id)) checkedIds.delete(id);
      else checkedIds.add(id);
    }
    lastCheckedId = id;
    updateBatchButtons();
    renderList();
    return; // Don't play audio or show detail when just selecting
  }

  selectedId = id;
  renderList();
  renderDetail(id);
  setTimeout(() => {
    const a = document.getElementById('genAudio');
    if (a) { stopOtherAudio(a); a.currentTime = 0; a.play(); }
  }, 100);
}

function toggleLock(id) {
  const item = corpusData.find(c => c.id === id);
  if (!item) return;

  const wasUnlocked = !item.locked;
  item.locked = !item.locked;
  api(`/api/lock/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ locked: item.locked })
  }).then(res => {
    if (res.error) toast(`锁定失败: ${res.error}`, 'error');
  });
  updateTabCounts();

  // Move selection to the next available item before re-rendering
  const currentIndex = corpusData.findIndex(c => c.id === id);
  let nextItem = null;
  // Search forward first, then backward from currentIndex
  for (let i = currentIndex + 1; i < corpusData.length; i++) {
    if (isVisible(corpusData[i])) { nextItem = corpusData[i]; break; }
  }
  if (!nextItem) {
    for (let i = currentIndex - 1; i >= 0; i--) {
      if (isVisible(corpusData[i])) { nextItem = corpusData[i]; break; }
    }
  }

  selectedId = nextItem ? nextItem.id : null;
  renderList();
  if (selectedId) {
    renderDetail(selectedId);
    // Auto-play only when locking, not when unlocking
    if (wasUnlocked) {
      setTimeout(() => {
        const a = document.getElementById('genAudio');
        if (a) { stopOtherAudio(a); a.currentTime = 0; a.play(); }
      }, 100);
    }
  }
}

function isVisible(item) {
  if (activeTab === 'locked' && !item.locked) return false;
  if (activeTab === 'unlocked' && item.locked) return false;
  const statusFilter = document.getElementById('statusFilter').value;
  if (statusFilter === 'generated' && !item.generated) return false;
  if (statusFilter === 'pending' && item.generated) return false;
  const ratingFilter = document.querySelector('.filter-btn.active')?.dataset.value || 'none';
  if (ratingFilter !== 'none' && item.rating !== ratingFilter) return false;
  const search = document.getElementById('searchInput').value.trim();
  if (search) {
    const s = search.toLowerCase();
    if (!item.id.toString().includes(s) && !item.text.toLowerCase().includes(s)) return false;
  }
  return true;
}

function getVisibleIds() {
  const ids = [];
  for (const item of corpusData) {
    if (isVisible(item)) ids.push(item.id);
  }
  return ids;
}

function toggleCheck(id, event) {
  const e = event || window.event;
  const ctrlKey = e && (e.ctrlKey || e.metaKey);
  const shiftKey = e && e.shiftKey;

  if (shiftKey && lastCheckedId !== null) {
    // Shift+Click: select range
    const allIds = corpusData.map(c => c.id);
    const fromIdx = allIds.indexOf(lastCheckedId);
    const toIdx = allIds.indexOf(id);
    const start = Math.min(fromIdx, toIdx);
    const end = Math.max(fromIdx, toIdx);
    for (let i = start; i <= end; i++) {
      checkedIds.add(allIds[i]);
    }
  } else if (ctrlKey) {
    // Ctrl+Click: toggle single item
    if (checkedIds.has(id)) checkedIds.delete(id);
    else checkedIds.add(id);
  } else {
    // Regular click: select only this item
    checkedIds.clear();
    checkedIds.add(id);
  }
  lastCheckedId = id;
  updateBatchButtons();
  renderList();
}

function updateBatchButtons() {
  const has = checkedIds.size > 0;
  document.getElementById('batchBtn').disabled = !has;
  document.getElementById('batchDelBtn').disabled = !has;
}

// ========== Detail ==========
async function renderDetail(id) {
  const item = corpusData.find(c => c.id === id);
  if (!item) return;

  const title = document.getElementById('mainTitle');
  const content = document.getElementById('mainContent');

  title.innerHTML = `第 ${String(id).padStart(4, '0')} 条 <span class="current-ref-badge" id="currentRefBadge"></span><span class="style-badge" id="styleBadge"></span>`;

  const origRefName = item.ref_name || null;
  const origRef = refsData.find(r => r.name === origRefName);

  content.innerHTML = `<div class="detail-card">
    <div class="detail-text">${escHtml(item.text)}</div>
    <div class="audio-section">
      <h3>音频对比</h3>
      <div class="audio-row">
        <div class="audio-block">
          <label>参照语音（参考音频）</label>
          ${origRef
            ? `<audio id="refAudio" controls preload="none"><source src="/${origRef.path}" type="audio/wav"></audio>
               <div class="ref-text" id="refText">${origRef.name}.WAV「${escHtml(origRef.text)}」</div>`
            : `<audio id="refAudio" controls preload="none"></audio>
               <div class="ref-text" id="refText">点击下方选择参考音频</div>`
          }
        </div>
        <div class="audio-block">
          <label>生成语音（TTS 输出）</label>
          ${item.generated
            ? `<audio id="genAudio" controls preload="none"><source src="/wav/${String(id).padStart(4,'0')}.wav?t=${Date.now()}" type="audio/wav"></audio>`
            : `<div style="color:#999;padding:12px 0;">尚未生成</div>`
          }
        </div>
      </div>
    </div>
    <div class="ref-section">
      <h3>选择参考音频</h3>
      <div class="ref-filter" id="refFilter"></div>
      <div class="ref-grid" id="refGrid"></div>
    </div>
    <div class="action-bar">
      <button class="btn btn-primary" onclick="regenerate()" id="regenBtn" ${item.locked ? 'disabled title="已锁定"' : ''}>
        ${item.locked ? '🔒 已锁定' : '重新生成'}
      </button>
      <button class="btn btn-primary" onclick="randomRegenerate()" id="randomRegenBtn" ${item.locked ? 'disabled title="已锁定"' : ''}>
        ${item.locked ? '🔒 已锁定' : '🎲 随机参照生成'}
      </button>
      <button class="btn btn-secondary" onclick="playRef()">播放参照</button>
      <button class="btn btn-secondary" onclick="playGen()" ${!item.generated ? 'disabled' : ''}>播放生成</button>
      <button class="btn btn-danger" onclick="deleteWav(${id})" ${!item.generated || item.locked ? 'disabled' : ''}>删除生成</button>
    </div>
    <div class="rating-selector">
      <h3>语音质量评级</h3>
      <div class="rating-btns">
        <button class="rating-btn ${item.rating === 'excellent' ? 'active' : ''}" data-rating="excellent" onclick="setRatingAction(${id}, 'excellent')">优秀</button>
        <button class="rating-btn ${item.rating === 'good' ? 'active' : ''}" data-rating="good" onclick="setRatingAction(${id}, 'good')">良好</button>
        <button class="rating-btn ${item.rating === 'fair' ? 'active' : ''}" data-rating="fair" onclick="setRatingAction(${id}, 'fair')">一般</button>
        <button class="rating-btn ${item.rating === 'poor' ? 'active' : ''}" data-rating="poor" onclick="setRatingAction(${id}, 'poor')">差</button>
      </div>
    </div>
  </div>`;

  renderRefFilter();
  renderRefGrid();

  // Bind audio events
  const refA = document.getElementById('refAudio');
  const genA = document.getElementById('genAudio');
  if (refA) refA.addEventListener('play', () => { if (genA && !genA.paused) genA.pause(); });
  if (genA) genA.addEventListener('play', () => { if (refA && !refA.paused) refA.pause(); });

  // Restore selected ref
  const preservedRef = selectedRefForRegen;
  if (preservedRef && refsData.find(r => r.name === preservedRef)) {
    selectRef(preservedRef, false);
  } else if (origRef) {
    selectRef(origRef.name, false);
  } else if (refsData.length > 0) {
    selectRef(refsData[0].name, false);
  }
}

function renderRefFilter() {
  const container = document.getElementById('refFilter');
  let html = `<button class="style-tab ${activeStyle === 'all' ? 'active' : ''}" onclick="setStyle('all')">全部</button>`;
  for (const [key, label] of Object.entries(stylesData)) {
    html += `<button class="style-tab ${activeStyle === key ? 'active' : ''}" onclick="setStyle('${key}')">${label}</button>`;
  }
  container.innerHTML = html;
}

function renderRefGrid() {
  const container = document.getElementById('refGrid');
  const filtered = activeStyle === 'all' ? refsData : refsData.filter(r => r.style === activeStyle);
  let html = '';
  for (const ref of filtered) {
    const sel = selectedRefForRegen === ref.name ? ' selected' : '';
    html += `<div class="ref-item${sel}" onclick="selectRef('${ref.name}')">
      <span class="ref-id">${ref.name}.WAV</span>
      <span class="ref-text">${escHtml(ref.text)}</span>
    </div>`;
  }
  container.innerHTML = html;
}

function setStyle(style) {
  activeStyle = style;
  renderRefFilter();
  renderRefGrid();
}

function selectRef(name, play = true) {
  selectedRefForRegen = name;
  const ref = refsData.find(r => r.name === name);
  if (ref) {
    document.getElementById('refAudio').src = '/' + ref.path;
    document.getElementById('refAudio').currentTime = 0;
    document.getElementById('refText').textContent = `「${ref.text}」`;
    const badge = document.getElementById('currentRefBadge');
    if (badge) badge.textContent = `当前参考: ${name}.WAV`;
    const styleBadge = document.getElementById('styleBadge');
    if (styleBadge) styleBadge.textContent = ref.style_label;
    if (play) {
      setTimeout(() => {
        const a = document.getElementById('refAudio');
        if (a) { stopOtherAudio(a); a.currentTime = 0; a.play(); }
      }, 50);
    }
  }
  renderRefGrid();
}

// ========== Audio Control ==========
function stopOtherAudio(currentAudio) {
  ['refAudio', 'genAudio'].forEach(id => {
    const el = document.getElementById(id);
    if (el && el !== currentAudio && !el.paused) { el.pause(); el.currentTime = 0; }
  });
}

function playRef() {
  const a = document.getElementById('refAudio');
  if (a && a.src) { stopOtherAudio(a); a.currentTime = 0; a.play(); }
}

function playGen() {
  const a = document.getElementById('genAudio');
  if (a) { stopOtherAudio(a); a.currentTime = 0; a.play(); }
}

// ========== Actions ==========
async function regenerate() {
  if (!selectedId) return;
  const item = corpusData.find(c => c.id === selectedId);
  if (item && item.locked) {
    toast('该条目已锁定，请先解锁再修改', 'error');
    return;
  }
  const refName = selectedRefForRegen;
  if (!refName) { toast('请先选择一个参考音频', 'error'); return; }

  const btn = document.getElementById('regenBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="loading"></span>生成中...';

  try {
    const res = await api('/api/regenerate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: selectedId, ref: refName })
    });
    if (res.error) {
      toast(`生成失败: ${res.error}`, 'error');
    } else {
      toast(`第 ${String(selectedId).padStart(4,'0')} 条生成成功`, 'success');
      if (item) {
        item.generated = true;
        item.ref_name = res.ref;
        item.ref_text = res.ref_text || item.ref_text;
      }
      updateStatusBar();
      renderList();
      renderDetail(selectedId);
      setTimeout(() => {
        const a = document.getElementById('genAudio');
        if (a) a.play();
      }, 300);
    }
  } catch (e) {
    toast(`请求失败: ${e.message}`, 'error');
  }
  btn.disabled = false;
  btn.textContent = '重新生成';
}

async function randomRegenerate() {
  if (!selectedId) return;
  const item = corpusData.find(c => c.id === selectedId);
  if (item && item.locked) {
    toast('该条目已锁定，请先解锁再修改', 'error');
    return;
  }
  if (refsData.length === 0) { toast('没有可用的参考音频', 'error'); return; }

  const randomRef = refsData[Math.floor(Math.random() * refsData.length)];
  toast(`🎲 随机选择: ${randomRef.name}.WAV [${randomRef.style_label}]`, 'info');
  selectRef(randomRef.name, false);

  const btn = document.getElementById('randomRegenBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="loading"></span>生成中...';

  try {
    const res = await api('/api/regenerate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: selectedId, ref: randomRef.name })
    });
    if (res.error) {
      toast(`生成失败: ${res.error}`, 'error');
    } else {
      toast(`第 ${String(selectedId).padStart(4,'0')} 条随机生成成功`, 'success');
      if (item) {
        item.generated = true;
        item.ref_name = res.ref;
        item.ref_text = res.ref_text || item.ref_text;
      }
      updateStatusBar();
      renderList();
      renderDetail(selectedId);
      setTimeout(() => {
        const a = document.getElementById('genAudio');
        if (a) a.play();
      }, 300);
    }
  } catch (e) {
    toast(`请求失败: ${e.message}`, 'error');
  }
  btn.disabled = false;
  btn.textContent = '🎲 随机参照生成';
}

async function setRatingAction(id, rating) {
  const item = corpusData.find(c => c.id === id);
  if (!item) return;
  // If clicking same rating, remove it
  if (item.rating === rating) {
    rating = 'none';
  }
  try {
    await api(`/api/rating/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rating })
    });
    if (item) item.rating = rating === 'none' ? null : rating;

    // 优秀/良好/一般 自动锁定，差只评级不锁定
    if (['excellent', 'good', 'fair'].includes(rating) && !item.locked) {
      item.locked = true;
      api(`/api/lock/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ locked: true })
      });
    }

    renderList();
    renderDetail(id);
  } catch (e) {
    toast(`评级失败: ${e.message}`, 'error');
  }
}

async function deleteWav(id) {
  const item = corpusData.find(c => c.id === id);
  if (item && item.locked) {
    toast('该条目已锁定，请先解锁再删除', 'error');
    return;
  }
  if (!confirm(`确定删除第 ${String(id).padStart(4, '0')} 条的生成音频？`)) return;

  try {
    const res = await api(`/api/wav/${id}`, { method: 'DELETE' });
    if (res.error) {
      toast(`删除失败: ${res.error}`, 'error');
    } else {
      toast(`已删除`, 'info');
      const item = corpusData.find(c => c.id === id);
      if (item) item.generated = false;
      updateStatusBar();
      renderList();
      renderDetail(id);
    }
  } catch (e) {
    toast(`请求失败: ${e.message}`, 'error');
  }
}

async function batchRegenerate() {
  const allChecked = Array.from(checkedIds);
  const ids = allChecked.filter(id => {
    const item = corpusData.find(c => c.id === id);
    return !item || !item.locked;
  });
  const lockedCount = allChecked.length - ids.length;
  if (lockedCount > 0) toast(`已跳过 ${lockedCount} 条已锁定的语料`, 'info');
  if (ids.length === 0) {
    if (lockedCount === 0) toast('请先勾选要生成的语料', 'info');
    return;
  }

  const refName = selectedRefForRegen;
  if (!refName) { toast('请先选择一个参考音频', 'error'); return; }
  if (!confirm(`确定用参考音频 ${refName}.WAV 重新生成 ${ids.length} 条语料？`)) return;
  toast(`开始批量生成 ${ids.length} 条...`, 'info');

  try {
    const res = await api('/api/batch-regenerate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids, ref: refName })
    });
    if (res.error) {
      toast(`批量生成失败: ${res.error}`, 'error');
    } else {
      const ok = res.success.length;
      const fail = res.failed.length;
      const skipped = (res.skipped_locked || []).length;
      let msg = `批量生成完成: 成功 ${ok} 条，失败 ${fail} 条`;
      if (skipped > 0) msg += `，跳过已锁定 ${skipped} 条`;
      toast(msg, ok > 0 ? 'success' : 'info');

      const ref = refsData.find(r => r.name === refName);
      const refText = ref ? ref.text : '';
      for (const id of res.success) {
        const item = corpusData.find(c => c.id === id);
        if (item) {
          item.generated = true;
          item.ref_name = refName;
          item.ref_text = refText;
        }
      }
      updateStatusBar();
      renderList();
      if (selectedId && res.success.includes(selectedId)) renderDetail(selectedId);
    }
  } catch (e) {
    toast(`请求失败: ${e.message}`, 'error');
  }
}

async function batchDelete() {
  const allChecked = Array.from(checkedIds);
  const ids = allChecked.filter(id => {
    const item = corpusData.find(c => c.id === id);
    return !item || !item.locked;
  });
  const lockedCount = allChecked.length - ids.length;
  if (lockedCount > 0) toast(`已跳过 ${lockedCount} 条已锁定的语料`, 'info');
  if (ids.length === 0) {
    if (lockedCount === 0) toast('请先勾选要删除的语料', 'info');
    return;
  }
  if (!confirm(`确定删除 ${ids.length} 条生成音频？`)) return;

  let success = 0, failed = 0;
  for (const id of ids) {
    try {
      const res = await api(`/api/wav/${id}`, { method: 'DELETE' });
      if (res.success) {
        success++;
        const item = corpusData.find(c => c.id === id);
        if (item) item.generated = false;
      } else { failed++; }
    } catch { failed++; }
  }

  toast(`批量删除完成: 成功 ${success} 条，失败 ${failed} 条`, 'info');
  updateStatusBar();
  renderList();
  if (selectedId) renderDetail(selectedId);
  checkedIds.clear();
  document.getElementById('selectAll').checked = false;
}

function batchClearRatings() {
  const ratedItems = corpusData.filter(c => c.rating);
  if (ratedItems.length === 0) {
    toast('没有已评级的语料', 'info');
    return;
  }
  if (!confirm(`确定清空 ${ratedItems.length} 条已评级语料的评级？`)) return;

  // Clear frontend state
  for (const item of ratedItems) {
    item.rating = null;
  }

  // Clear backend state
  for (const item of ratedItems) {
    api(`/api/rating/${item.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rating: 'none' })
    });
  }

  toast(`已清空 ${ratedItems.length} 条语料的评级`, 'success');
  renderList();
  if (selectedId) renderDetail(selectedId);
}

// ========== Select All ==========
document.getElementById('selectAll').addEventListener('change', function() {
  if (this.checked) {
    const search = document.getElementById('searchInput').value.trim();
    const statusFilter = document.getElementById('statusFilter').value;
    for (const item of corpusData) {
      if (statusFilter === 'generated' && !item.generated) continue;
      if (statusFilter === 'pending' && item.generated) continue;
      if (search) {
        const s = search.toLowerCase();
        if (!item.id.toString().includes(s) && !item.text.toLowerCase().includes(s)) continue;
      }
      checkedIds.add(item.id);
    }
  } else {
    checkedIds.clear();
  }
  renderList();
});

// ========== Search ==========
document.getElementById('searchInput').addEventListener('input', renderList);
document.getElementById('statusFilter').addEventListener('change', renderList);
document.getElementById('ratingSort').addEventListener('change', renderList);

function setRatingFilter(value) {
  // Update active button
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.value === value);
  });
  renderList();
}

// ========== Toast ==========
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ========== Utils ==========
function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ========== Zen Mode ==========
let zenActive = false;
let zenQueue = [];
let zenIndex = 0;
let zenCountdownSec = 5;
let zenCountdownTimer = null;
let zenCountdownInterval = null;
let zenRating = null;
let zenGenEnded = false;

function startZenMode() {
  zenQueue = corpusData
    .filter(item => item.generated && !item.locked && !item.rating)
    .map(item => item.id);
  if (zenQueue.length === 0) {
    toast('没有未锁定且未评级的语料', 'info');
    return;
  }
  zenActive = true;
  zenIndex = 0;
  document.getElementById('zenOverlay').style.display = 'flex';
  document.addEventListener('keydown', zenKeyboardHandler);
  // Pause any main UI audio
  ['refAudio', 'genAudio'].forEach(id => {
    const el = document.getElementById(id);
    if (el && !el.paused) el.pause();
  });
  zenShowItem();
}

function stopZenMode() {
  zenActive = false;
  zenClearTimer();
  document.removeEventListener('keydown', zenKeyboardHandler);
  document.getElementById('zenOverlay').style.display = 'none';
  // Refresh the main list
  renderList();
  if (selectedId) renderDetail(selectedId);
}

function zenKeyboardHandler(e) {
  if (!zenActive) return;
  switch (e.key) {
    case 'ArrowLeft': e.preventDefault(); zenPrev(); break;
    case 'ArrowRight': e.preventDefault(); zenNext(); break;
    case 'a': case 'A': zenRate('excellent'); break;
    case 's': case 'S': zenRate('good'); break;
    case 'd': case 'D': zenRate('fair'); break;
    case 'f': case 'F': zenRate('poor'); break;
    case 'r': case 'R': zenReplayGen(); break;
    case 'q': case 'Q': zenPlayRef(); break;
    case ' ': e.preventDefault(); zenRandomRegenerate(); break;
    case 'Escape': stopZenMode(); break;
  }
}

function zenClearTimer() {
  if (zenCountdownTimer) { clearTimeout(zenCountdownTimer); zenCountdownTimer = null; }
  if (zenCountdownInterval) { clearInterval(zenCountdownInterval); zenCountdownInterval = null; }
}

function zenShowItem() {
  zenClearTimer();
  zenRating = null;
  zenGenEnded = false;
  if (zenIndex < 0 || zenIndex >= zenQueue.length) {
    if (zenQueue.length === 0) {
      stopZenMode();
      toast('🎉 所有语料已浏览完毕', 'info');
    } else {
      zenIndex = 0;
      zenShowItem();
    }
    return;
  }
  const id = zenQueue[zenIndex];
  const item = corpusData.find(c => c.id === id);
  if (!item) { zenNext(); return; }

  // Update progress
  document.getElementById('zenProgress').textContent = `${zenIndex + 1} / ${zenQueue.length} 条`;
  document.getElementById('zenItemId').textContent = `第 ${String(id).padStart(4, '0')} 条`;
  document.getElementById('zenItemText').textContent = item.text;

  // Ref info
  const origRef = refsData.find(r => r.name === item.ref_name);
  document.getElementById('zenRefInfo').textContent = origRef
    ? `当前参考: ${item.ref_name}.WAV [${origRef.style_label}]`
    : '无参考信息';
  if (origRef) {
    document.getElementById('zenRefText').textContent = `「${origRef.text}」`;
    document.getElementById('zenRefAudio').src = '/' + origRef.path;
  }

  // Audio
  const genAudio = document.getElementById('zenGenAudio');
  if (item.generated) {
    genAudio.src = `/wav/${String(id).padStart(4, '0')}.wav?t=${Date.now()}`;
  }

  // Reset countdown display
  document.getElementById('zenCountdownFill').style.width = '100%';
  document.getElementById('zenCountdownText').textContent = '等待播放完成...';

  // Clear previous onended handler
  genAudio.onended = null;

  // Auto-play after a short delay
  setTimeout(() => {
    if (!zenActive) return;
    const a = document.getElementById('zenGenAudio');
    if (a) { a.currentTime = 0; a.play().catch(() => {}); }
  }, 300);

  // Listen for audio end (capture current index to prevent stale handlers)
  const capturedIndex = zenIndex;
  genAudio.onended = () => {
    if (!zenActive || zenIndex !== capturedIndex) return;
    zenGenEnded = true;
    zenStartCountdown();
  };
}

function zenStartCountdown() {
  zenClearTimer();
  let remaining = zenCountdownSec;
  const fill = document.getElementById('zenCountdownFill');
  const text = document.getElementById('zenCountdownText');
  fill.style.width = '100%';
  text.textContent = `请在 ${remaining} 秒内评级`;

  zenCountdownInterval = setInterval(() => {
    remaining--;
    fill.style.width = `${(remaining / zenCountdownSec) * 100}%`;
    text.textContent = `请在 ${remaining} 秒内评级`;
    if (remaining <= 0) {
      zenClearTimer();
      fill.style.width = '100%';
      text.textContent = '等待播放完成...';
      // Time expired - don't lock, move to next
      zenNext();
    }
  }, 1000);
}

function zenRate(rating) {
  if (!zenActive) return;
  const id = zenQueue[zenIndex];
  if (!id) return;

  zenClearTimer();
  const item = corpusData.find(c => c.id === id);
  if (!item) return;

  // Set rating
  item.rating = rating;
  api(`/api/rating/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rating })
  });

  const label = RATING_LABELS[rating] || rating;

  // excellent/good/fair → auto-lock; poor → no lock
  if (rating === 'poor') {
    toast(`⚠️ ${label} — 未锁定`, 'info');
  } else {
    item.locked = true;
    api(`/api/lock/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ locked: true })
    });
    toast(`✅ ${label} — 已锁定`, 'success');
  }

  // Remove from queue
  zenQueue.splice(zenIndex, 1);

  // Move to next (same index since current was removed)
  zenShowItem();
}

function zenNext() {
  zenClearTimer();
  document.getElementById('zenCountdownFill').style.width = '100%';
  document.getElementById('zenCountdownText').textContent = '等待播放完成...';
  zenIndex++;
  if (zenIndex >= zenQueue.length) {
    // Check if queue was emptied by ratings
    if (zenQueue.length === 0) {
      stopZenMode();
      toast('🎉 所有语料已浏览完毕', 'info');
    } else {
      zenIndex = 0;
      zenShowItem();
    }
  } else {
    zenShowItem();
  }
}

function zenPrev() {
  zenClearTimer();
  if (zenIndex > 0) zenIndex--;
  document.getElementById('zenCountdownFill').style.width = '100%';
  document.getElementById('zenCountdownText').textContent = '等待播放完成...';
  zenShowItem();
}

function zenReplayGen() {
  const a = document.getElementById('zenGenAudio');
  if (a) { a.currentTime = 0; a.play().catch(() => {}); }
}

function zenPlayRef() {
  const a = document.getElementById('zenRefAudio');
  if (a && a.src) { a.currentTime = 0; a.play().catch(() => {}); }
}

async function zenRandomRegenerate() {
  if (!zenActive) return;
  const id = zenQueue[zenIndex];
  if (!id) return;
  if (refsData.length === 0) { toast('没有可用的参考音频', 'error'); return; }

  const randomRef = refsData[Math.floor(Math.random() * refsData.length)];
  toast(`🎲 随机选择: ${randomRef.name}.WAV [${randomRef.style_label}]`, 'info');

  zenClearTimer();
  document.getElementById('zenCountdownFill').style.width = '100%';
  document.getElementById('zenCountdownText').textContent = '等待播放完成...';

  try {
    const res = await api('/api/regenerate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, ref: randomRef.name })
    });
    if (res.error) {
      toast(`生成失败: ${res.error}`, 'error');
    } else {
      toast(`随机生成成功`, 'success');
      const item = corpusData.find(c => c.id === id);
      if (item) {
        item.generated = true;
        item.ref_name = res.ref;
        item.ref_text = res.ref_text || item.ref_text;
      }
      zenShowItem();
    }
  } catch (e) {
    toast(`请求失败: ${e.message}`, 'error');
  }
}

// ========== Init ==========
loadData();
