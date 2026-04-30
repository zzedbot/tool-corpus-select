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

  for (const item of ratedItems) {
    item.rating = null;
  }
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

function setRatingFilter(value) {
  document.querySelectorAll('#ratingFilterBtns .filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.value === value);
  });
  renderList();
}

function setDnsmosFilter(value) {
  dnsmosFilter = value;
  document.querySelectorAll('#dnsmosFilterBtns .filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.value === value);
  });
  renderList();
}

// ========== DNMOS 评分进度 ==========
let _dnsmosPollInterval = null;

function startDnsmosScoring() {
  const ids = Array.from(checkedIds).filter(id => {
    const item = corpusData.find(c => c.id === id);
    return item && item.generated; // 只对已生成的评分
  });
  const msg = ids.length > 0
    ? `开始对 ${ids.length} 条勾选的音频评分`
    : '开始对全部音频评分';
  toast(msg, 'info');

  api('/api/dnsmos/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids: ids.length > 0 ? ids : null, skip_scored: true })
  }).then(res => {
    if (res.error) {
      toast(`评分失败: ${res.error}`, 'error');
    }
    updateDnsmosPanel();
  });
}

function stopDnsmosScoring() {
  api('/api/dnsmos/stop', { method: 'POST' }).then(() => {
    updateDnsmosPanel();
    toast('评分已取消', 'info');
  });
}

function updateDnsmosPanel() {
  api('/api/dnsmos/status').then(status => {
    const startBtn = document.getElementById('dnsmosStartBtn');
    const stopBtn = document.getElementById('dnsmosStopBtn');
    const progressDiv = document.getElementById('dnsmosProgress');
    const fill = document.getElementById('dnsmosProgressFill');
    const text = document.getElementById('dnsmosStatusText');

    if (status.active) {
      startBtn.style.display = 'none';
      stopBtn.style.display = '';
      progressDiv.style.display = 'block';
      const pct = status.total > 0 ? (status.done / status.total * 100) : 0;
      fill.style.width = pct + '%';
      text.textContent = `${status.done} / ${status.total} — 当前: ${String(status.current_id).padStart(4,'0')} → ${status.current_score ? status.current_score.toFixed(2) : '...'}`;
    } else if (status.error) {
      // 评分出错但未激活
      startBtn.style.display = '';
      stopBtn.style.display = 'none';
      progressDiv.style.display = 'block';
      fill.style.width = '0%';
      text.innerHTML = `<span class="dnsmos-error">${status.error}</span>`;
    } else if (status.done > 0) {
      startBtn.style.display = '';
      stopBtn.style.display = 'none';
      if (status.done > 0) {
        progressDiv.style.display = 'block';
        fill.style.width = '100%';
        text.textContent = `评分完成: ${status.done} / ${status.total}`;
        // Refresh list to show new scores
        loadData();
        // Hide progress after 3 seconds
        setTimeout(() => {
          document.getElementById('dnsmosProgress').style.display = 'none';
        }, 3000);
      } else {
        progressDiv.style.display = 'none';
      }
    }
  });
}

function startDnsmosPolling() {
  if (_dnsmosPollInterval) return;
  _dnsmosPollInterval = setInterval(updateDnsmosPanel, 2000);
}

// Start polling when page loads
setTimeout(startDnsmosPolling, 3000);
