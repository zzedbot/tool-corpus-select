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
let dnsmosFilter = 'none';
const RATING_LABELS = { excellent: '优秀', good: '良好', fair: '一般', poor: '差' };
