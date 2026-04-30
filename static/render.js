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

function getRatingFilter() {
  return document.querySelector('.filter-btn.active')?.dataset.value || 'none';
}

function getVisibleFilter() {
  return document.getElementById('statusFilter').value;
}

function getSearchQuery() {
  return document.getElementById('searchInput').value.trim();
}

// ========== Render List ==========
function renderList() {
  const search = getSearchQuery();
  const statusFilter = getVisibleFilter();
  const ratingFilter = getRatingFilter();
  const ratingSort = document.getElementById('ratingSort').value;
  const list = document.getElementById('corpusList');

  let items = corpusData.filter(item => {
    if (activeTab === 'locked' && !item.locked) return false;
    if (activeTab === 'unlocked' && item.locked) return false;
    if (statusFilter === 'generated' && !item.generated) return false;
    if (statusFilter === 'pending' && item.generated) return false;
    if (ratingFilter !== 'none' && item.rating !== ratingFilter) return false;
    if (dnsmosFilter !== 'none' && (!item.dnsmos || item.dnsmos < parseFloat(dnsmosFilter))) return false;
    if (search) {
      const s = search.toLowerCase();
      if (!item.id.toString().includes(s) && !item.text.toLowerCase().includes(s)) return false;
    }
    return true;
  });

  const ratingOrder = { poor: 0, fair: 1, good: 2, excellent: 3 };
  if (ratingSort === 'rating_asc') {
    items.sort((a, b) => (ratingOrder[a.rating] || -1) - (ratingOrder[b.rating] || -1));
  } else if (ratingSort === 'rating_desc') {
    items.sort((a, b) => (ratingOrder[b.rating] || -1) - (ratingOrder[a.rating] || -1));
  } else if (ratingSort === 'dnsmos_asc') {
    items.sort((a, b) => (a.dnsmos || 0) - (b.dnsmos || 0));
  } else if (ratingSort === 'dnsmos_desc') {
    items.sort((a, b) => (b.dnsmos || 0) - (a.dnsmos || 0));
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
    const dnsmosBadge = item.dnsmos ? `<span class="dnsmos-badge">${item.dnsmos.toFixed(2)}</span>` : '';

    html += `<div class="corpus-item${isActive}" data-id="${item.id}" onclick="selectItem(${item.id}, event)" style="${itemStyle}">
      <input class="checkbox" type="checkbox" ${checked} onclick="event.stopPropagation();toggleCheck(${item.id}, event)" />
      <div class="item-main">
        <div class="item-top">
          <span class="item-id">${String(item.id).padStart(4, '0')}</span>
          <span class="item-text" title="${escHtml(item.text)}">${escHtml(item.text)}</span>
          <span class="badge ${badgeClass}">${badgeText}</span>
        </div>
        <div class="item-meta">
          <div class="item-meta-left">${refInfo}${dnsmosBadge}</div>
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
    return;
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

  const currentIndex = corpusData.findIndex(c => c.id === id);
  let nextItem = null;
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
  const statusFilter = getVisibleFilter();
  if (statusFilter === 'generated' && !item.generated) return false;
  if (statusFilter === 'pending' && item.generated) return false;
  const ratingFilter = getRatingFilter();
  if (ratingFilter !== 'none' && item.rating !== ratingFilter) return false;
  if (dnsmosFilter !== 'none' && (!item.dnsmos || item.dnsmos < parseFloat(dnsmosFilter))) return false;
  const search = getSearchQuery();
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
    const allIds = corpusData.map(c => c.id);
    const fromIdx = allIds.indexOf(lastCheckedId);
    const toIdx = allIds.indexOf(id);
    const start = Math.min(fromIdx, toIdx);
    const end = Math.max(fromIdx, toIdx);
    for (let i = start; i <= end; i++) checkedIds.add(allIds[i]);
  } else if (ctrlKey) {
    if (checkedIds.has(id)) checkedIds.delete(id);
    else checkedIds.add(id);
  } else {
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

  const refA = document.getElementById('refAudio');
  const genA = document.getElementById('genAudio');
  if (refA) refA.addEventListener('play', () => { if (genA && !genA.paused) genA.pause(); });
  if (genA) genA.addEventListener('play', () => { if (refA && !refA.paused) refA.pause(); });

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
