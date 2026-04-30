// ========== Event Listeners ==========
document.getElementById('selectAll').addEventListener('change', function() {
  if (this.checked) {
    const search = getSearchQuery();
    const statusFilter = getVisibleFilter();
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

document.getElementById('searchInput').addEventListener('input', renderList);
document.getElementById('statusFilter').addEventListener('change', renderList);
document.getElementById('ratingSort').addEventListener('change', renderList);

// ========== Init ==========
loadData();
