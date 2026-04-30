// ========== API ==========
async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  return res.json();
}
