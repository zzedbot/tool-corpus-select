// ========== Zen Mode ==========
let zenActive = false;
let zenQueue = [];
let zenIndex = 0;
let zenCountdownSec = 5;
let zenRating = null;
let zenGenEnded = false;

// Countdown state machine
let zenCountdown = {
  running: false,
  paused: false,
  remaining: 5,
  total: 5,
  interval: null,
};

function countdownStart() {
  countdownStop();
  zenCountdown.remaining = zenCountdown.total;
  countdownTick();
  zenCountdown.interval = setInterval(countdownTick, 1000);
  zenCountdown.running = true;
  zenCountdown.paused = false;
}

function countdownPause() {
  if (!zenCountdown.running || zenCountdown.paused) return;
  clearInterval(zenCountdown.interval);
  zenCountdown.interval = null;
  zenCountdown.paused = true;
  document.getElementById('zenCountdownText').textContent = '⏸ 已暂停';
}

function countdownResume() {
  if (!zenCountdown.running || !zenCountdown.paused) return;
  zenCountdown.paused = false;
  countdownTick();
  zenCountdown.interval = setInterval(countdownTick, 1000);
}

function countdownStop() {
  clearInterval(zenCountdown.interval);
  zenCountdown.interval = null;
  zenCountdown.running = false;
  zenCountdown.paused = false;
  zenCountdown.remaining = zenCountdown.total;
}

function countdownTick() {
  const fill = document.getElementById('zenCountdownFill');
  const text = document.getElementById('zenCountdownText');
  zenCountdown.remaining--;
  fill.style.width = `${(zenCountdown.remaining / zenCountdown.total) * 100}%`;
  if (zenCountdown.remaining <= 0) {
    countdownStop();
    fill.style.width = '100%';
    text.textContent = '等待播放完成...';
    zenNext();
  } else {
    text.textContent = `请在 ${zenCountdown.remaining} 秒内评级`;
  }
}

function updateCountdownDisplay(text, widthPercent) {
  document.getElementById('zenCountdownText').textContent = text;
  document.getElementById('zenCountdownFill').style.width = widthPercent + '%';
}

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
  ['refAudio', 'genAudio'].forEach(id => {
    const el = document.getElementById(id);
    if (el && !el.paused) el.pause();
  });
  zenShowItem();
}

function stopZenMode() {
  zenActive = false;
  countdownStop();
  document.removeEventListener('keydown', zenKeyboardHandler);
  document.getElementById('zenOverlay').style.display = 'none';
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

function zenShowItem() {
  countdownStop();
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

  document.getElementById('zenProgress').textContent = `${zenIndex + 1} / ${zenQueue.length} 条`;
  document.getElementById('zenItemId').textContent = `第 ${String(id).padStart(4, '0')} 条`;
  document.getElementById('zenItemText').textContent = item.text;

  const origRef = refsData.find(r => r.name === item.ref_name);
  document.getElementById('zenRefInfo').textContent = origRef
    ? `当前参考: ${item.ref_name}.WAV [${origRef.style_label}]`
    : '无参考信息';
  if (origRef) {
    document.getElementById('zenRefText').textContent = `「${origRef.text}」`;
    document.getElementById('zenRefAudio').src = '/' + origRef.path;
  }

  const genAudio = document.getElementById('zenGenAudio');
  if (item.generated) {
    genAudio.src = `/wav/${String(id).padStart(4, '0')}.wav?t=${Date.now()}`;
  }

  updateCountdownDisplay('等待播放完成...', 100);

  // Set up gen audio onended → start countdown
  genAudio.onended = () => {
    if (!zenActive) return;
    countdownStart();
  };

  // Auto-play after a short delay
  setTimeout(() => {
    if (!zenActive) return;
    const a = document.getElementById('zenGenAudio');
    if (a) { a.currentTime = 0; a.play().catch(() => {}); }
  }, 300);
}

function zenRate(rating) {
  if (!zenActive) return;
  const id = zenQueue[zenIndex];
  if (!id) return;

  countdownStop();
  const item = corpusData.find(c => c.id === id);
  if (!item) return;

  item.rating = rating;
  api(`/api/rating/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rating })
  });

  const label = RATING_LABELS[rating] || rating;

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

  zenQueue.splice(zenIndex, 1);
  zenShowItem();
}

function zenNext() {
  countdownStop();
  updateCountdownDisplay('等待播放完成...', 100);
  zenIndex++;
  if (zenIndex >= zenQueue.length) {
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
  countdownStop();
  if (zenIndex > 0) zenIndex--;
  updateCountdownDisplay('等待播放完成...', 100);
  zenShowItem();
}

function zenReplayGen() {
  // Stop countdown, replay gen audio, restart countdown on end
  countdownStop();
  const genAudio = document.getElementById('zenGenAudio');
  genAudio.onended = () => {
    if (!zenActive) return;
    countdownStart();
  };
  genAudio.currentTime = 0;
  genAudio.play().catch(() => {});
}

function zenPlayRef() {
  // Pause countdown, play ref audio, resume countdown on end
  countdownPause();
  const refAudio = document.getElementById('zenRefAudio');
  if (refAudio && refAudio.src) {
    refAudio.onended = () => {
      if (!zenActive) return;
      countdownResume();
    };
    refAudio.currentTime = 0;
    refAudio.play().catch(() => {});
  } else {
    // No ref audio available, just resume
    countdownResume();
  }
}

async function zenRandomRegenerate() {
  if (!zenActive) return;
  const id = zenQueue[zenIndex];
  if (!id) return;
  if (refsData.length === 0) { toast('没有可用的参考音频', 'error'); return; }

  const randomRef = refsData[Math.floor(Math.random() * refsData.length)];
  toast(`🎲 随机选择: ${randomRef.name}.WAV [${randomRef.style_label}]`, 'info');

  countdownStop();
  updateCountdownDisplay('正在生成...', 100);

  try {
    const res = await api('/api/regenerate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, ref: randomRef.name })
    });
    if (res.error) {
      toast(`生成失败: ${res.error}`, 'error');
      updateCountdownDisplay('等待播放完成...', 100);
    } else {
      toast(`随机生成成功`, 'success');
      const item = corpusData.find(c => c.id === id);
      if (item) {
        item.generated = true;
        item.ref_name = res.ref;
        item.ref_text = res.ref_text || item.ref_text;
      }
      zenShowItem(); // will auto-play and set up new countdown
    }
  } catch (e) {
    toast(`请求失败: ${e.message}`, 'error');
    updateCountdownDisplay('等待播放完成...', 100);
  }
}
