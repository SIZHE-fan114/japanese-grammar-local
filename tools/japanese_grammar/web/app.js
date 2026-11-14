import {
  DEFAULT_SUBJECT_ID,
  DEFAULT_TOPIC_ID,
  api,
  awaitSubmissionResult,
  newRequestId,
} from './api.js';
import { createAiAssistant } from './ai-assistant.js';
import { renderCourseGraph } from './course-graph.js';
import { escapeHtml, setRichHtml, setRichText } from './math-render.js';
import { openChunkPeekModal, renderMemoryChunkView } from './memory-chunk.js';
import { createQuestionInputWidget, renderAnswerValue, renderFeedbackPanel } from './question-widget.js';

const ROMAJI_STORAGE_KEY = 'grasp-jp-hide-romaji';
const LAST_TOPIC_STORAGE_KEY = 'grasp-jp-last-topic';
const DRAFT_PREFIX = 'grasp-jp-draft:';

const dom = {
  brandHomeBtn: document.getElementById('brandHomeBtn'),
  navTabs: [...document.querySelectorAll('.navTab')],
  reviewDueBadge: document.getElementById('reviewDueBadge'),
  romajiToggleBtn: document.getElementById('romajiToggleBtn'),
  romajiToggleState: document.getElementById('romajiToggleState'),
  engineStatusChip: document.getElementById('engineStatusChip'),
  aiSettingsBtn: document.getElementById('aiSettingsBtn'),
  aiDrawerToggleBtn: document.getElementById('aiDrawerToggleBtn'),
  aiDrawerHost: document.getElementById('aiDrawerHost'),
  historyDrawerToggle: document.getElementById('historyDrawerToggle'),
  topicSidebar: document.getElementById('topicSidebar'),
  sidebarBackdrop: document.getElementById('sidebarBackdrop'),
  mainView: document.getElementById('mainView'),
  modalHost: document.getElementById('modalHost'),
  toastHost: document.getElementById('toastHost'),
};

const appState = {
  route: 'overview',
  health: null,
  catalog: null,
  dashboard: null,
  graphs: [],
  activeGraph: null,
  atomicReviews: null,
  reviewPaperInbox: null,
  moduleReviews: null,
  pauses: [],
  studentReport: null,
  activeTopicId: DEFAULT_TOPIC_ID,
  topicState: null,
  topicStatesById: new Map(),
  activePaperId: null,
  activePaperState: null,
  paperActivitySessionId: newRequestId('paper-sess'),
  sidebarOpen: false,
  busy: false,
  cooldownTimerId: null,
  paperTimerId: null,
  presenceTimerId: null,
  lastRenderSeq: 0,
  introStepState: new Map(),
  introExpandState: new Map(),
  aiContext: null,
  aiAssistant: null,
};

function setAiContext(ctx) {
  appState.aiContext = ctx || null;
  appState.aiAssistant?.notifyContextChanged();
}

function extractNodePlainText(node) {
  return String(node?.textContent || '').replace(/\s+/g, ' ').trim();
}

function splitLargeListGroups(leadNodes, listEl, baseTitle) {
  const items = Array.from(listEl.children).filter((ch) => ch.tagName === 'LI');
  if (items.length <= 2) {
    return null;
  }
  const totalLen = items.reduce((acc, li) => acc + extractNodePlainText(li).length, 0);
  if (items.length <= 3 && totalLen < 420) {
    return null;
  }
  const chunkSize = items.length >= 5 || totalLen > 750 ? 2 : Math.ceil(items.length / 2);
  const subSteps = [];
  for (let i = 0; i < items.length; i += chunkSize) {
    const slice = items.slice(i, i + chunkSize);
    const listClone = listEl.cloneNode(false);
    for (const li of slice) {
      listClone.appendChild(li.cloneNode(true));
    }
    const wrapper = document.createElement('div');
    if (i === 0 && leadNodes.length) {
      for (const ln of leadNodes) {
        wrapper.appendChild(ln.cloneNode(true));
      }
    } else if (baseTitle) {
      const h = document.createElement('h4');
      h.textContent = baseTitle;
      wrapper.appendChild(h);
    }
    wrapper.appendChild(listClone);
    subSteps.push({
      title: baseTitle || '语法讲解',
      html: wrapper.innerHTML,
      text: extractNodePlainText(wrapper),
    });
  }
  return subSteps;
}

function splitIntroductionSteps(html, fallbackTitle = '语法核心讲解') {
  const rawHtml = String(html || '').trim() || '<p>请阅读本节语法说明并继续。</p>';
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div id="__intro_root">${rawHtml}</div>`, 'text/html');
  const root = doc.getElementById('__intro_root');
  const children = root ? Array.from(root.children) : [];
  if (!children.length) {
    return [{ title: fallbackTitle, html: rawHtml, text: extractNodePlainText(root) }];
  }

  const sections = [];
  let cur = { title: '', nodes: [] };
  for (const el of children) {
    const tag = el.tagName;
    if ((tag === 'H3' || tag === 'H4') && cur.nodes.length > 0) {
      sections.push(cur);
      cur = { title: extractNodePlainText(el), nodes: [el] };
    } else {
      if ((tag === 'H3' || tag === 'H4') && !cur.title) {
        cur.title = extractNodePlainText(el);
      }
      cur.nodes.push(el);
    }
  }
  if (cur.nodes.length) {
    sections.push(cur);
  }

  if (sections.length > 1 && !sections[0].title) {
    const firstText = sections[0].nodes.map(extractNodePlainText).join(' ').trim();
    if (firstText.length < 90) {
      sections[1].nodes = [...sections[0].nodes, ...sections[1].nodes];
      sections.shift();
    } else {
      sections[0].title = `${fallbackTitle} · 导读`;
    }
  }

  const rawSteps = [];
  const isCompanion = (el) =>
    el.classList?.contains('jp-ex') ||
    el.classList?.contains('jp-bad-ex') ||
    el.classList?.contains('jp-tip');

  for (const sec of sections) {
    const secTitle = sec.title || fallbackTitle;
    const secTextLen = sec.nodes.reduce((s, n) => s + extractNodePlainText(n).length, 0);

    const listNodes = sec.nodes.filter((n) => n.tagName === 'UL' || n.tagName === 'OL');
    if (listNodes.length === 1 && sec.nodes.indexOf(listNodes[0]) >= sec.nodes.length - 2) {
      const listIdx = sec.nodes.indexOf(listNodes[0]);
      const lead = sec.nodes.slice(0, listIdx);
      const tail = sec.nodes.slice(listIdx + 1);
      const splitList = splitLargeListGroups(lead, listNodes[0], secTitle);
      if (splitList && splitList.length > 1) {
        if (tail.length) {
          const last = splitList[splitList.length - 1];
          last.html += tail.map((t) => t.outerHTML).join('');
          last.text = `${last.text} ${tail.map(extractNodePlainText).join(' ')}`.trim();
        }
        splitList.forEach((st, idx) => {
          rawSteps.push({
            ...st,
            title: `${secTitle}（${idx + 1}/${splitList.length}）`,
          });
        });
        continue;
      }
    }

    if (sec.nodes.length <= 2 || secTextLen <= 680) {
      const wrap = document.createElement('div');
      for (const n of sec.nodes) {
        wrap.appendChild(n.cloneNode(true));
      }
      rawSteps.push({
        title: secTitle,
        html: wrap.innerHTML,
        text: extractNodePlainText(wrap),
      });
      continue;
    }

    const buckets = [];
    let bucketNodes = [];
    let bucketLen = 0;
    for (let i = 0; i < sec.nodes.length; i++) {
      const el = sec.nodes[i];
      const len = extractNodePlainText(el).length;
      const keepWithPrev =
        bucketNodes.length === 1 &&
        (bucketNodes[0].tagName === 'H3' || bucketNodes[0].tagName === 'H4');
      if (bucketNodes.length > 0 && !keepWithPrev && !isCompanion(el) && bucketLen >= 460) {
        buckets.push(bucketNodes);
        bucketNodes = [];
        bucketLen = 0;
      }
      bucketNodes.push(el);
      bucketLen += len;
    }
    if (bucketNodes.length) {
      const lastLen = bucketNodes.reduce((s, n) => s + extractNodePlainText(n).length, 0);
      if (buckets.length > 0 && lastLen < 120) {
        buckets[buckets.length - 1].push(...bucketNodes);
      } else {
        buckets.push(bucketNodes);
      }
    }

    buckets.forEach((bNodes, bIdx) => {
      const wrap = document.createElement('div');
      if (bIdx > 0 && bNodes[0]?.tagName !== 'H3' && bNodes[0]?.tagName !== 'H4' && secTitle) {
        const h = document.createElement('h4');
        h.textContent = secTitle;
        wrap.appendChild(h);
      }
      for (const n of bNodes) {
        wrap.appendChild(n.cloneNode(true));
      }
      rawSteps.push({
        title: buckets.length > 1 ? `${secTitle}（${bIdx + 1}/${buckets.length}）` : secTitle,
        html: wrap.innerHTML,
        text: extractNodePlainText(wrap),
      });
    });
  }

  return rawSteps.length
    ? rawSteps
    : [{ title: fallbackTitle, html: rawHtml, text: extractNodePlainText(root) }];
}

function clearTimers() {
  if (appState.cooldownTimerId) {
    clearInterval(appState.cooldownTimerId);
    appState.cooldownTimerId = null;
  }
  if (appState.paperTimerId) {
    clearInterval(appState.paperTimerId);
    appState.paperTimerId = null;
  }
  if (appState.presenceTimerId) {
    clearInterval(appState.presenceTimerId);
    appState.presenceTimerId = null;
  }
}

function showToast(message, { error = false, duration = 3400 } = {}) {
  if (!dom.toastHost) {
    return;
  }
  const toast = document.createElement('div');
  toast.className = `toast${error ? ' toast--error' : ''}`;
  toast.textContent = String(message || '');
  dom.toastHost.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, duration);
}

function isHideRomajiStored() {
  try {
    return localStorage.getItem(ROMAJI_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function applyRomajiPreference(hidden) {
  const isHidden = Boolean(hidden);
  document.body.classList.toggle('hide-romaji', isHidden);
  if (dom.romajiToggleBtn) {
    dom.romajiToggleBtn.setAttribute('aria-pressed', String(isHidden));
    dom.romajiToggleBtn.classList.toggle('is-hidden-romaji', isHidden);
  }
  if (dom.romajiToggleState) {
    dom.romajiToggleState.textContent = isHidden ? '已隐藏' : '显示中';
  }
  try {
    localStorage.setItem(ROMAJI_STORAGE_KEY, isHidden ? '1' : '0');
  } catch {
    // Ignore storage restriction errors in sandboxed iframes.
  }
}

function setSidebarOpen(open) {
  appState.sidebarOpen = Boolean(open);
  dom.topicSidebar?.classList.toggle('is-open', appState.sidebarOpen);
  dom.sidebarBackdrop?.classList.toggle('hidden', !appState.sidebarOpen);
  dom.historyDrawerToggle?.setAttribute('aria-expanded', String(appState.sidebarOpen));
}

function showSidebarShell(visible) {
  dom.topicSidebar?.classList.toggle('hidden', !visible);
  dom.historyDrawerToggle?.classList.toggle('hidden', !visible);
  if (!visible) {
    setSidebarOpen(false);
  }
}

function draftKey(topicId, cardId) {
  return `${DRAFT_PREFIX}${topicId}:${cardId || 'step'}`;
}

function loadDraft(topicId, cardId) {
  try {
    return localStorage.getItem(draftKey(topicId, cardId)) || '';
  } catch {
    return '';
  }
}

function saveDraft(topicId, cardId, value) {
  try {
    if (!value) {
      localStorage.removeItem(draftKey(topicId, cardId));
    } else {
      localStorage.setItem(draftKey(topicId, cardId), value);
    }
  } catch {
    // Ignore quota errors cleanly.
  }
}

function actionGuard(state) {
  if (!state || typeof state !== 'object') {
    return {};
  }
  const guard = {};
  if (state.revision !== undefined && state.revision !== null) {
    guard.expected_revision = state.revision;
  }
  if (state.attempt_id) {
    guard.attempt_id = state.attempt_id;
  }
  if (state.active_step_id) {
    guard.step_id = state.active_step_id;
  }
  return guard;
}

function getCatalogTopics() {
  const cat = appState.catalog?.catalog || appState.catalog || {};
  const dashTopics = Array.isArray(appState.dashboard?.topics)
    ? appState.dashboard.topics
    : Array.isArray(appState.dashboard?.courses)
      ? appState.dashboard.courses.flatMap((c) => c.topics || [])
      : [];
  const graphNodes = Array.isArray(appState.activeGraph?.nodes) ? appState.activeGraph.nodes : [];
  const metaById = new Map();
  for (const item of [...graphNodes, ...dashTopics]) {
    const id = item?.id || item?.topic_id || item?.node_id;
    if (id) {
      metaById.set(id, { ...(metaById.get(id) || {}), ...item, id, topic_id: item.topic_id || id });
    }
  }
  for (const [id, st] of appState.topicStatesById.entries()) {
    metaById.set(id, { ...(metaById.get(id) || {}), ...st, id, topic_id: st.topic_id || id });
  }

  const list = [];
  const seen = new Set();
  const pushTopic = (item) => {
    const raw = typeof item === 'string' ? { id: item } : item;
    const id = raw?.id || raw?.topic_id;
    if (!id || seen.has(id)) {
      return;
    }
    seen.add(id);
    list.push({ ...(metaById.get(id) || {}), ...raw, id, topic_id: raw?.topic_id || id });
  };
  for (const t of cat.topics || []) {
    pushTopic(t);
  }
  for (const c of cat.courses || []) {
    for (const t of c.topics || []) {
      pushTopic(t);
    }
    for (const u of c.units || []) {
      for (const t of u.topics || []) {
        pushTopic(t);
      }
    }
    for (const o of c.outline || []) {
      for (const tid of o.topic_ids || []) {
        pushTopic(tid);
      }
    }
  }
  for (const t of dashTopics) {
    pushTopic(t);
  }
  return list;
}

function getTopicDisplayChapter(topicId, index = 0, explicitChapter = null) {
  if (explicitChapter !== null && explicitChapter !== undefined) {
    return explicitChapter;
  }
  const m = String(topicId || '').match(/(?:jp|ch|lesson)?0*(\d+)/i);
  return m ? Number(m[1]) : index + 1;
}

function getAtomicDueCount() {
  const atomicItems = Array.isArray(appState.atomicReviews?.items) ? appState.atomicReviews.items : [];
  const atomicSum = atomicItems.reduce((acc, item) => acc + Number(item?.due_count || 0), 0);
  const paperCount = Number(appState.reviewPaperInbox?.due_count || 0);
  const modCount = Array.isArray(appState.moduleReviews?.items)
    ? appState.moduleReviews.items.filter((x) => x?.due_now || x?.due).length
    : 0;
  return Math.max(atomicSum, paperCount) + modCount;
}

function updateNavBadges() {
  const due = getAtomicDueCount();
  if (dom.reviewDueBadge) {
    dom.reviewDueBadge.textContent = String(due);
    dom.reviewDueBadge.classList.toggle('hidden', due <= 0);
  }
  for (const tab of dom.navTabs) {
    tab.classList.toggle('is-active', tab.dataset.route === appState.route);
  }
}

function updateStatusChip() {
  if (!dom.engineStatusChip) {
    return;
  }
  const health = appState.health;
  if (!health) {
    dom.engineStatusChip.className = 'statusChip statusChip--err';
    dom.engineStatusChip.textContent = '后端离线';
    return;
  }
  if (health.ok === false) {
    dom.engineStatusChip.className = 'statusChip statusChip--warn';
    dom.engineStatusChip.textContent = health.message || '引擎待检';
    return;
  }
  dom.engineStatusChip.className = 'statusChip statusChip--ok';
  dom.engineStatusChip.textContent = '本地引擎在线';
}

function normalizePauses(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (Array.isArray(payload?.items)) {
    return payload.items;
  }
  if (Array.isArray(payload?.pauses)) {
    return payload.pauses;
  }
  return [];
}

async function refreshSharedSummary() {
  const [healthRes, catalogRes, dashRes, graphsRes, atomicRevRes, inboxRes, pausesRes, modRevRes] = await Promise.allSettled([
    api.health(),
    api.catalog(DEFAULT_SUBJECT_ID),
    api.dashboard(DEFAULT_SUBJECT_ID),
    api.graphs(DEFAULT_SUBJECT_ID),
    api.atomicReviews(DEFAULT_SUBJECT_ID),
    api.reviewPaperInbox(DEFAULT_SUBJECT_ID),
    api.pauses(null, DEFAULT_SUBJECT_ID),
    api.reviews(DEFAULT_SUBJECT_ID),
  ]);

  if (healthRes.status === 'fulfilled') {
    appState.health = healthRes.value;
  } else {
    appState.health = null;
  }
  if (catalogRes.status === 'fulfilled') {
    appState.catalog = catalogRes.value;
  }
  if (dashRes.status === 'fulfilled') {
    appState.dashboard = dashRes.value;
    const dashTopics = dashRes.value?.topics || dashRes.value?.courses?.flatMap((c) => c.topics || []) || [];
    for (const item of dashTopics) {
      const id = item.id || item.topic_id;
      if (id) {
        appState.topicStatesById.set(id, { ...(appState.topicStatesById.get(id) || {}), ...item });
      }
    }
  }
  if (graphsRes.status === 'fulfilled') {
    const graphs = graphsRes.value?.graphs || (Array.isArray(graphsRes.value) ? graphsRes.value : []);
    appState.graphs = graphs;
    if (graphs.length) {
      const firstId = graphs[0].id || graphs[0].graph_id || graphs[0];
      if (typeof firstId === 'string') {
        try {
          appState.activeGraph = await api.graph(firstId, DEFAULT_SUBJECT_ID);
        } catch {
          appState.activeGraph = graphs[0];
        }
      } else {
        appState.activeGraph = graphs[0];
      }
    }
  }
  if (atomicRevRes.status === 'fulfilled') {
    appState.atomicReviews = atomicRevRes.value;
  }
  if (inboxRes.status === 'fulfilled') {
    appState.reviewPaperInbox = inboxRes.value;
  }
  if (pausesRes.status === 'fulfilled') {
    appState.pauses = normalizePauses(pausesRes.value);
  }
  if (modRevRes.status === 'fulfilled') {
    appState.moduleReviews = modRevRes.value;
  } else {
    appState.moduleReviews = { items: [] };
  }

  const topics = getCatalogTopics();
  if (topics.length && !topics.some((t) => t.id === appState.activeTopicId)) {
    appState.activeTopicId = topics[0].id;
  }

  updateStatusChip();
  updateNavBadges();
}

function pickDefaultTopicId() {
  try {
    const saved = localStorage.getItem(LAST_TOPIC_STORAGE_KEY);
    const topics = getCatalogTopics();
    if (saved && topics.some((t) => t.id === saved)) {
      return saved;
    }
  } catch {
    // Ignore
  }
  const topics = getCatalogTopics();
  const nextUp = topics.find((t) => {
    const st = appState.topicStatesById.get(t.id) || t;
    const completed = Boolean(st.completed || st.status === 'completed' || st.completed_at);
    const locked = Boolean(st.locked || st.dependency_blocked || st.dependency_ready === false);
    return !completed && !locked;
  });
  return nextUp?.id || topics[0]?.id || DEFAULT_TOPIC_ID;
}

function navigate(hash) {
  const target = hash.startsWith('#') ? hash : `#${hash}`;
  if (window.location.hash === target) {
    handleRouteChange();
  } else {
    window.location.hash = target;
  }
}

function parseRoute() {
  const raw = (window.location.hash || '#/overview').replace(/^#/, '');
  const parts = raw.split('/').filter(Boolean);
  if (!parts.length || parts[0] === 'overview') {
    return { route: 'overview' };
  }
  if (parts[0] === 'learn') {
    return { route: 'learn', topicId: pickDefaultTopicId() };
  }
  if (parts[0] === 'topic' && parts[1]) {
    return { route: 'topic', topicId: decodeURIComponent(parts[1]) };
  }
  if (parts[0] === 'review') {
    if (parts[1] === 'paper' && parts[2]) {
      return { route: 'review', paperId: decodeURIComponent(parts[2]) };
    }
    return { route: 'review' };
  }
  if (parts[0] === 'stats' || parts[0] === 'dashboard') {
    return { route: 'stats' };
  }
  return { route: 'overview' };
}

function formatDurationSeconds(totalSeconds) {
  const sec = Math.max(0, Math.floor(totalSeconds));
  const mins = Math.floor(sec / 60);
  const rem = sec % 60;
  if (mins >= 60) {
    const hrs = Math.floor(mins / 60);
    return `${hrs} 小时 ${mins % 60} 分 ${rem} 秒`;
  }
  if (mins > 0) {
    return `${mins} 分 ${rem} 秒`;
  }
  return `${rem} 秒`;
}

function formatDateTime(iso) {
  if (!iso) {
    return '—';
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return String(iso);
  }
  return d.toLocaleString('zh-CN', { hour12: false });
}

function renderPauseAlert(container, pauses, onUnlocked) {
  if (!pauses?.length) {
    return;
  }
  for (const pause of pauses) {
    const banner = document.createElement('div');
    banner.className = 'banner banner--danger';
    const info = document.createElement('div');
    info.innerHTML = `
      <div><strong>触发练习暂停：</strong>${escapeHtml(pause.topic_title || pause.topic_id || '当前课程')}</div>
      <div class="mutedText">原因：${escapeHtml(pause.reason || '连续错误达到保护阈值，请回顾语法规则后解锁继续')}</div>
    `;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn--danger btn--sm';
    btn.textContent = '解除暂停并继续';
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await api.unlockPause(
          {
            topic_id: pause.topic_id,
            module_id: pause.module_id || 'atomic',
            pause_event_id: pause.event_id || pause.pause_event_id,
          },
          DEFAULT_SUBJECT_ID,
        );
        showToast('已解除本地练习暂停');
        await onUnlocked();
      } catch (err) {
        showToast(err.message || '解锁失败', { error: true });
        btn.disabled = false;
      }
    });
    banner.append(info, btn);
    container.appendChild(banner);
  }
}

/* ---------------- Overview View ---------------- */
async function renderOverviewView() {
  showSidebarShell(false);
  const topics = getCatalogTopics();
  const dueCount = getAtomicDueCount();
  const completedCount = topics.filter((t) => {
    const st = appState.topicStatesById.get(t.id) || t;
    return Boolean(st.completed || st.status === 'completed' || st.completed_at);
  }).length;
  const recommendedId = pickDefaultTopicId();

  const root = document.createElement('div');

  const hero = document.createElement('section');
  hero.className = 'heroBanner';
  hero.innerHTML = `
    <div class="heroCopy">
      <div class="heroEyebrow">JAPANESE GRAMMAR WORKBENCH · 日语文法精练</div>
      <h1 class="heroTitle">日语基础语法与结构填空精练</h1>
      <p class="heroDesc">围绕「体言・助词」「动词基本型」「否定与过去式」「连体修饰」「并列与条件」循序掌握，结合组块记忆与间隔复习巩固直觉。</p>
      <div class="actionRow" style="margin-top:14px;">
        <button type="button" class="btn btn--primary" id="heroStartBtn">继续学习：${escapeHtml(topics.find((t) => t.id === recommendedId)?.title || '第 1 课')}</button>
        ${dueCount > 0 ? `<button type="button" class="btn btn--secondary" id="heroReviewBtn">进入间隔复习（${dueCount} 项到期）</button>` : ''}
      </div>
    </div>
    <div class="heroStats">
      <div class="heroStatBox">
        <div class="heroStatNum">${completedCount} / ${topics.length}</div>
        <div class="heroStatLabel">已完成课时</div>
      </div>
      <div class="heroStatBox">
        <div class="heroStatNum">${dueCount}</div>
        <div class="heroStatLabel">当前到期复习</div>
      </div>
    </div>
  `;
  root.appendChild(hero);

  renderPauseAlert(root, appState.pauses, async () => {
    await refreshSharedSummary();
    await renderOverviewView();
  });

  const graphPanel = document.createElement('section');
  graphPanel.className = 'panelCard';
  renderCourseGraph(graphPanel, appState.activeGraph, {
    catalogTopics: topics,
    activeTopicId: recommendedId,
    topicStates: appState.topicStatesById,
    onSelectTopic: (topicId) => navigate(`/topic/${encodeURIComponent(topicId)}`),
  });
  root.appendChild(graphPanel);

  const listPanel = document.createElement('section');
  listPanel.className = 'panelCard';
  listPanel.innerHTML = `
    <div class="dagPanelHeader">
      <div>
        <h2 class="cardTitle" style="margin:0;">全部语法课时目录</h2>
        <span class="mutedText">每课包含分段指导、核心组块（Memory Chunk）与纯语境语法填空检索</span>
      </div>
      <span class="pill pill--accent">支持切换隐藏假名/罗马音盲测</span>
    </div>
  `;

  const grid = document.createElement('div');
  grid.className = 'topicGrid';

  topics.forEach((topic, idx) => {
    const st = appState.topicStatesById.get(topic.id) || topic;
    const chapter = getTopicDisplayChapter(topic.id, idx, topic.chapter);
    const completed = Boolean(st.completed || st.status === 'completed' || st.completed_at);
    const locked = Boolean(st.locked || st.dependency_blocked || st.dependency_ready === false);
    const learnedPts = Number(st.learned_count ?? st.topic_progress?.points?.completed ?? 0);
    const totalPts = Number(st.point_count ?? st.topic_progress?.points?.total ?? 0);
    const pct = totalPts > 0 ? Math.min(100, Math.round((learnedPts / totalPts) * 100)) : completed ? 100 : 0;

    const card = document.createElement('article');
    card.className = `topicCard${locked ? ' is-locked' : ''}`;
    card.innerHTML = `
      <div>
        <div class="topicCardTop">
          <span class="topicChapterTag">第 ${chapter} 课</span>
          <span class="pill ${completed ? 'pill--success' : locked ? 'pill--muted' : 'pill--accent'}">
            ${completed ? '已掌握' : locked ? '待解锁' : '学习中'}
          </span>
        </div>
        <h3 class="topicCardTitle">${escapeHtml(topic.title || topic.id)}</h3>
        <p class="topicCardDesc">${escapeHtml(topic.summary || topic.description || '语境组块精读 + 日语助词与活用形语法填空')}</p>
        ${totalPts > 0 ? `
          <div class="topicProgressBar" aria-label="记忆点掌握进度">
            <div class="topicProgressFill" style="width:${pct}%"></div>
          </div>
        ` : ''}
      </div>
      <div class="topicCardFooter">
        <span class="mutedText">${totalPts > 0 ? `记忆点 ${learnedPts} / ${totalPts}` : (completed ? '已完成初次学习' : locked ? '请先完成前置课时' : '点击进入学习')}</span>
        <button type="button" class="btn btn--sm ${completed ? 'btn--secondary' : 'btn--primary'}" data-open-topic="${escapeHtml(topic.id)}">
          ${completed ? '回顾 / 复习' : locked ? '查看先修' : '开始学习'}
        </button>
      </div>
    `;
    grid.appendChild(card);
  });

  if (!topics.length) {
    grid.innerHTML = '<p class="mutedText">暂无已安装的日语语法课程包，请确认后端课程包目录。</p>';
  }

  listPanel.appendChild(grid);
  root.appendChild(listPanel);

  dom.mainView.replaceChildren(root);
  setAiContext({
    view: 'overview',
    isSubmitted: true,
    label: '日语语法课程总览与学习地图',
  });

  hero.querySelector('#heroStartBtn')?.addEventListener('click', () => {
    navigate(`/topic/${encodeURIComponent(recommendedId)}`);
  });
  hero.querySelector('#heroReviewBtn')?.addEventListener('click', () => {
    navigate('/review');
  });
  for (const btn of root.querySelectorAll('[data-open-topic]')) {
    btn.addEventListener('click', () => {
      navigate(`/topic/${encodeURIComponent(btn.dataset.openTopic)}`);
    });
  }
}

/* ---------------- Topic Sidebar & History Inspection ---------------- */
function openHistoryCardModal(record) {
  if (!dom.modalHost || !record) {
    return;
  }
  dom.modalHost.replaceChildren();
  dom.modalHost.classList.remove('hidden');
  dom.modalHost.setAttribute('aria-hidden', 'false');

  const dialog = document.createElement('div');
  dialog.className = 'modalDialog';
  dialog.setAttribute('role', 'dialog');
  dialog.setAttribute('aria-modal', 'true');

  const header = document.createElement('div');
  header.className = 'modalHeader';
  header.innerHTML = `<h3 class="cardTitle" style="margin:0;">已掌握卡片回顾 · ${escapeHtml(record.title || record.card_id || '语法练习')}</h3>`;
  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'btn btn--secondary btn--sm';
  closeBtn.textContent = '关闭';
  const closeModal = () => {
    dom.modalHost.classList.add('hidden');
    dom.modalHost.setAttribute('aria-hidden', 'true');
    dom.modalHost.replaceChildren();
  };
  closeBtn.addEventListener('click', closeModal);
  header.appendChild(closeBtn);

  const body = document.createElement('div');
  body.className = 'modalBody historyDetailBody';

  const stemEl = document.createElement('div');
  stemEl.className = 'questionStem';
  setRichHtml(stemEl, record.html || record.question || '', { literalMath: false });
  body.appendChild(stemEl);

  const ansBox = document.createElement('div');
  ansBox.className = 'answerReadout';
  ansBox.innerHTML = '<strong>最近一次作答：</strong>';
  const ansSpan = document.createElement('div');
  renderAnswerValue(ansSpan, record.answer_display || record.answer, record.interaction);
  ansBox.appendChild(ansSpan);
  body.appendChild(ansBox);

  if (record.explanation_html) {
    const exp = document.createElement('div');
    exp.className = 'explanationBox lessonContent';
    setRichHtml(exp, record.explanation_html, { literalMath: false });
    body.appendChild(exp);
  }

  dialog.append(header, body);
  dom.modalHost.appendChild(dialog);
  dom.modalHost.onclick = (e) => {
    if (e.target === dom.modalHost) {
      closeModal();
    }
  };
}

function renderTopicSidebar(state) {
  if (!dom.topicSidebar) {
    return;
  }
  showSidebarShell(true);
  dom.topicSidebar.replaceChildren();

  const header = document.createElement('div');
  header.className = 'sidebarBlock';
  header.innerHTML = `
    <div class="sidebarSectionTitle">当前课时大纲</div>
    <div style="font-weight:700; font-size:15px; margin-bottom:8px;">${escapeHtml(state?.title || appState.activeTopicId)}</div>
    <button type="button" class="btn btn--ghost btn--sm" id="sidebarBackOverview">← 返回课程总览</button>
  `;
  header.querySelector('#sidebarBackOverview')?.addEventListener('click', () => {
    setSidebarOpen(false);
    navigate('/overview');
  });
  dom.topicSidebar.appendChild(header);

  const sections = Array.isArray(state?.learning_sections) ? state.learning_sections : [];
  if (sections.length) {
    const secBlock = document.createElement('div');
    secBlock.className = 'sidebarBlock';
    secBlock.innerHTML = '<div class="sidebarSectionTitle">学习分段与组块</div>';
    sections.forEach((sec, idx) => {
      const item = document.createElement('div');
      const isCurrentIntro = state?.introduction?.id && state.introduction.id === sec.id;
      const chunks = Array.isArray(sec.chunks) ? sec.chunks : [];
      const currentChunkId = state?.chunk?.id;
      const isCurrent = isCurrentIntro || chunks.some((c) => c.id === currentChunkId);
      item.className = `sidebarSectionItem${isCurrent ? ' is-current' : ''}`;
      item.innerHTML = `
        <div class="sidebarSectionHead">
          <span>${idx + 1}. ${escapeHtml(sec.title || '语法指导')}</span>
          <span class="pill ${sec.read ? 'pill--success' : ''}">${sec.read ? '已读' : '待读'}</span>
        </div>
      `;
      if (chunks.length) {
        const ul = document.createElement('ul');
        ul.className = 'sidebarChunkList';
        for (const c of chunks) {
          const li = document.createElement('li');
          li.textContent = `${c.title || c.id}${c.seen ? ' ✓' : c.id === currentChunkId ? '（当前）' : ''}`;
          ul.appendChild(li);
        }
        item.appendChild(ul);
      }
      secBlock.appendChild(item);
    });
    dom.topicSidebar.appendChild(secBlock);
  }

  const history = Array.isArray(state?.history) ? state.history : (Array.isArray(state?.atomic_history) ? state.atomic_history : []);
  const histBlock = document.createElement('div');
  histBlock.className = 'sidebarBlock';
  histBlock.innerHTML = '<div class="sidebarSectionTitle">练习记录</div>';
  if (!history.length) {
    const empty = document.createElement('p');
    empty.className = 'mutedText';
    empty.textContent = '尚无已提交练习记录。';
    histBlock.appendChild(empty);
  } else {
    [...history].reverse().slice(0, 30).forEach((rec, i) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      const viewable = Boolean(rec.viewable ?? rec.mastered);
      btn.className = `sidebarHistoryItem${viewable ? '' : ' is-locked'}`;
      btn.disabled = !viewable;
      const label = rec.title || rec.card_id || `练习 #${history.length - i}`;
      btn.innerHTML = `
        <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(label)}</span>
        <span class="pill ${rec.correct ? 'pill--success' : 'pill--danger'}">${viewable ? (rec.correct ? '✓' : '✗') : '未掌握锁定'}</span>
      `;
      if (viewable) {
        btn.addEventListener('click', () => openHistoryCardModal(rec));
      }
      histBlock.appendChild(btn);
    });
  }
  dom.topicSidebar.appendChild(histBlock);
}

/* ---------------- Topic Learning View ---------------- */
async function loadAndRenderTopic(topicId) {
  appState.activeTopicId = topicId;
  try {
    localStorage.setItem(LAST_TOPIC_STORAGE_KEY, topicId);
  } catch {
    // Ignore
  }

  clearTimers();
  appState.presenceTimerId = setInterval(() => {
    api.presence(topicId, DEFAULT_SUBJECT_ID).catch(() => {});
  }, 30000);
  api.presence(topicId, DEFAULT_SUBJECT_ID).catch(() => {});

  const seq = ++appState.lastRenderSeq;
  let state;
  try {
    state = await api.state(topicId, DEFAULT_SUBJECT_ID);
  } catch (err) {
    if (seq !== appState.lastRenderSeq) {
      return;
    }
    showSidebarShell(false);
    dom.mainView.innerHTML = `
      <div class="panelCard">
        <p class="sectionEyebrow">加载失败</p>
        <h2 class="pageTitle">无法读取该课时的学习状态</h2>
        <p class="mutedText">${escapeHtml(err.message || '未知错误')}</p>
        <div class="actionRow">
          <button type="button" class="btn btn--primary" id="errBackBtn">返回课程总览</button>
        </div>
      </div>
    `;
    dom.mainView.querySelector('#errBackBtn')?.addEventListener('click', () => navigate('/overview'));
    return;
  }

  if (seq !== appState.lastRenderSeq) {
    return;
  }
  appState.topicState = state;
  appState.topicStatesById.set(topicId, { ...(appState.topicStatesById.get(topicId) || {}), ...state });
  await renderTopicState(state);
}

async function runTopicMutation(actionFn) {
  if (appState.busy) {
    return;
  }
  appState.busy = true;
  try {
    const nextState = await actionFn();
    if (nextState && typeof nextState === 'object' && nextState.phase) {
      appState.topicState = nextState;
      appState.topicStatesById.set(appState.activeTopicId, {
        ...(appState.topicStatesById.get(appState.activeTopicId) || {}),
        ...nextState,
      });
      await renderTopicState(nextState);
    } else {
      await loadAndRenderTopic(appState.activeTopicId);
    }
    await refreshSharedSummary();
  } catch (err) {
    if (err.code === 'stale_revision') {
      showToast('学习进度已在其他标签页更新，正在为您自动同步…');
      await loadAndRenderTopic(appState.activeTopicId);
    } else {
      showToast(err.message || '操作未能完成', { error: true });
      await renderTopicState(appState.topicState);
    }
  } finally {
    appState.busy = false;
  }
}

async function renderTopicState(state) {
  clearTimers();
  const topicId = state?.topic_id || appState.activeTopicId;
  appState.presenceTimerId = setInterval(() => {
    api.presence(topicId, DEFAULT_SUBJECT_ID).catch(() => {});
  }, 30000);

  renderTopicSidebar(state);
  const root = document.createElement('div');

  const tp = state?.topic_progress || {};
  const learnedCount = Number(state?.learned_count ?? tp.points?.completed ?? 0);
  const pointCount = Number(state?.point_count ?? tp.points?.total ?? 0);
  const chunkDone = Number(tp.chunks?.completed ?? 0);
  const chunkTotal = Number(tp.chunks?.total ?? 0);

  const topHeader = document.createElement('section');
  topHeader.className = 'panelCard topicHeaderCard';
  topHeader.innerHTML = `
    <div>
      <p class="sectionEyebrow">日本語文法精練 · ${escapeHtml(topicId)}</p>
      <h1 class="pageTitle" style="margin:0;">${escapeHtml(state?.title || topicId)}</h1>
    </div>
    <div class="topicProgressSummary">
      ${pointCount > 0 ? `<span class="pill pill--accent">记忆点 ${learnedCount} / ${pointCount}</span>` : ''}
      ${chunkTotal > 0 ? `<span class="pill">组块 ${chunkDone} / ${chunkTotal}</span>` : ''}
      <span class="pill">${state?.mode === 'review' ? '原子复习模式' : '初学模式'}</span>
      <button type="button" class="btn btn--secondary btn--sm" id="topicBackOverviewBtn">课程总览</button>
    </div>
  `;
  topHeader.querySelector('#topicBackOverviewBtn')?.addEventListener('click', () => navigate('/overview'));
  root.appendChild(topHeader);

  // 1. Dependency blocker check
  if (state?.dependency_blocked) {
    const blockers = state.blocking_topics || state.missing_prerequisites || [];
    const blockCard = document.createElement('section');
    blockCard.className = 'panelCard';
    blockCard.innerHTML = `
      <p class="sectionEyebrow">先修课程尚未完成</p>
      <h2 class="cardTitle">请先完成以下前置语法课程后再学习本课</h2>
      <div class="actionRow" id="blockerBtnRow"></div>
    `;
    const btnRow = blockCard.querySelector('#blockerBtnRow');
    for (const blk of blockers) {
      const id = typeof blk === 'string' ? blk : (blk.topic_id || blk.id);
      const label = typeof blk === 'string' ? blk : (blk.title || id);
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn btn--primary';
      b.textContent = `前往：${label}`;
      b.addEventListener('click', () => navigate(`/topic/${encodeURIComponent(id)}`));
      btnRow.appendChild(b);
    }
    if (!blockers.length) {
      const backBtn = document.createElement('button');
      backBtn.type = 'button';
      backBtn.className = 'btn btn--secondary';
      backBtn.textContent = '返回课程总览查看解锁路线';
      backBtn.addEventListener('click', () => navigate('/overview'));
      btnRow.appendChild(backBtn);
    }
    root.appendChild(blockCard);
    dom.mainView.replaceChildren(root);
    setAiContext({
      view: 'overview',
      topicId,
      topicTitle: state.title || topicId,
      isSubmitted: true,
      label: `先修锁定 · ${state.title || topicId}`,
    });
    return;
  }

  // 2. Active pause check
  const pauseObj = state?.pause || state?.topic_pause;
  if (pauseObj) {
    renderPauseAlert(
      root,
      [{ ...pauseObj, topic_id: topicId, topic_title: state.title }],
      async () => {
        await refreshSharedSummary();
        await loadAndRenderTopic(topicId);
      },
    );
    dom.mainView.replaceChildren(root);
    setAiContext({
      view: 'overview',
      topicId,
      topicTitle: state.title || topicId,
      isSubmitted: true,
      label: `练习暂停 · ${state.title || topicId}`,
    });
    return;
  }

  const phase = state?.phase;

  // 3. Introduction stage (covers both UnifiedLearningService section intro & initial AtomicLearningService intro)
  if (phase === 'introduction' || state?.display === 'introduction') {
    const intro = state.introduction || {};
    const introKey = `${topicId}:${intro.id || intro.title || 'intro'}`;
    const steps = splitIntroductionSteps(
      intro.html || intro.body_html || '<p>请阅读本节语法说明并继续。</p>',
      intro.title || '语法核心讲解',
    );
    const totalSteps = steps.length;
    const savedIdx = Number(appState.introStepState.get(introKey) || 0);
    let stepIdx = Math.max(0, Math.min(totalSteps - 1, savedIdx));
    let expandAll = Boolean(appState.introExpandState.get(introKey));

    const actions = Array.isArray(state.actions) ? state.actions : [];
    const canContinue = actions.includes('continue') || state.unified_topic || state.started_at;

    const card = document.createElement('section');
    card.className = 'panelCard';
    card.innerHTML = `
      <div class="introStepHeader">
        <div>
          <p class="sectionEyebrow" style="margin-bottom:4px;">本节语法指导 · Introduction</p>
          <h2 class="pageTitle" style="margin:0;">${escapeHtml(intro.title || '语法核心讲解')}</h2>
        </div>
        <div class="introStepTools" id="introStepTools"></div>
      </div>
      <div class="introStepPills" id="introStepPills"></div>
      <div class="introBody lessonContent" id="introHtmlBody"></div>
      <div class="introStepNav" id="introStepNav"></div>
    `;

    const toolsEl = card.querySelector('#introStepTools');
    const pillsEl = card.querySelector('#introStepPills');
    const bodyEl = card.querySelector('#introHtmlBody');
    const navEl = card.querySelector('#introStepNav');

    const makeAdvanceBtn = (primaryLabel, isPrimary = true) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `btn ${isPrimary ? 'btn--primary' : 'btn--ghost btn--sm'}`;
      if (canContinue) {
        btn.textContent = primaryLabel || '我已阅读指导，继续下一步';
        btn.addEventListener('click', () => runTopicMutation(() => api.continueStep(topicId, actionGuard(state), DEFAULT_SUBJECT_ID)));
      } else {
        btn.textContent = primaryLabel || '开始本课记忆与填空训练';
        btn.addEventListener('click', () => runTopicMutation(() => api.choose(topicId, 'learn', actionGuard(state), DEFAULT_SUBJECT_ID)));
      }
      return btn;
    };

    const renderIntroStep = async () => {
      const activeStep = steps[stepIdx] || steps[0];
      appState.introStepState.set(introKey, stepIdx);
      appState.introExpandState.set(introKey, expandAll);

      toolsEl.replaceChildren();
      if (totalSteps > 1) {
        const badge = document.createElement('span');
        badge.className = 'pill pill--accent';
        badge.textContent = expandAll ? `全览模式 · 共 ${totalSteps} 张` : `第 ${stepIdx + 1} / ${totalSteps} 张`;
        toolsEl.appendChild(badge);

        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'btn btn--ghost btn--sm';
        toggleBtn.textContent = expandAll ? '切回分步卡片' : '展开本节全览';
        toggleBtn.addEventListener('click', () => {
          expandAll = !expandAll;
          renderIntroStep();
        });
        toolsEl.appendChild(toggleBtn);
      }

      pillsEl.replaceChildren();
      if (totalSteps > 1 && !expandAll) {
        pillsEl.classList.remove('hidden');
        steps.forEach((st, idx) => {
          const pill = document.createElement('button');
          pill.type = 'button';
          pill.className = `introStepPill${idx === stepIdx ? ' is-active' : idx < stepIdx ? ' is-visited' : ''}`;
          pill.title = st.title;
          pill.innerHTML = `<span class="introStepPillNum">${idx + 1}</span><span class="introStepPillText">${escapeHtml(st.title)}</span>`;
          pill.addEventListener('click', () => {
            stepIdx = idx;
            renderIntroStep();
          });
          pillsEl.appendChild(pill);
        });
      } else {
        pillsEl.classList.add('hidden');
      }

      const htmlToRender = expandAll
        ? (intro.html || intro.body_html || '<p>请阅读本节语法说明并继续。</p>')
        : (activeStep?.html || '<p>请阅读本节语法说明并继续。</p>');
      await setRichHtml(bodyEl, htmlToRender, { literalMath: false });

      navEl.replaceChildren();
      const leftRow = document.createElement('div');
      leftRow.className = 'introStepNavLeft';
      if (totalSteps > 1 && !expandAll) {
        const prevBtn = document.createElement('button');
        prevBtn.type = 'button';
        prevBtn.className = 'btn btn--secondary';
        prevBtn.textContent = '← 上一张';
        prevBtn.disabled = stepIdx === 0;
        prevBtn.addEventListener('click', () => {
          if (stepIdx > 0) {
            stepIdx -= 1;
            renderIntroStep();
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
        });
        leftRow.appendChild(prevBtn);

        if (stepIdx < totalSteps - 1) {
          const nextStepBtn = document.createElement('button');
          nextStepBtn.type = 'button';
          nextStepBtn.className = 'btn btn--primary';
          nextStepBtn.textContent = `下一张（${stepIdx + 2} / ${totalSteps}）→`;
          nextStepBtn.addEventListener('click', () => {
            stepIdx += 1;
            renderIntroStep();
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          });
          leftRow.appendChild(nextStepBtn);
        }
      }

      const rightRow = document.createElement('div');
      rightRow.className = 'introStepNavRight';
      if (expandAll || totalSteps <= 1 || stepIdx >= totalSteps - 1) {
        rightRow.appendChild(makeAdvanceBtn(canContinue ? '我已阅读指导，继续下一步' : '开始本课记忆与填空训练', true));
        if (!canContinue && state.completed_at) {
          const revBtn = document.createElement('button');
          revBtn.type = 'button';
          revBtn.className = 'btn btn--secondary';
          revBtn.textContent = '进入原子卡片复习';
          revBtn.addEventListener('click', () => runTopicMutation(() => api.choose(topicId, 'review', actionGuard(state), DEFAULT_SUBJECT_ID)));
          rightRow.appendChild(revBtn);
        }
      } else {
        rightRow.appendChild(makeAdvanceBtn(canContinue ? '跳过讲解直接继续' : '跳过讲解开始训练', false));
        if (!canContinue && state.completed_at) {
          const revBtn = document.createElement('button');
          revBtn.type = 'button';
          revBtn.className = 'btn btn--secondary btn--sm';
          revBtn.textContent = '进入原子卡片复习';
          revBtn.addEventListener('click', () => runTopicMutation(() => api.choose(topicId, 'review', actionGuard(state), DEFAULT_SUBJECT_ID)));
          rightRow.appendChild(revBtn);
        }
      }

      navEl.append(leftRow, rightRow);

      setAiContext({
        view: 'introduction',
        topicId,
        topicTitle: state.title || topicId,
        isSubmitted: true,
        stepIndex: expandAll ? null : stepIdx + 1,
        stepTotal: expandAll ? null : totalSteps,
        stepTitle: expandAll ? (intro.title || '语法核心讲解') : (activeStep?.title || intro.title || '语法讲解'),
        stepText: extractNodePlainText(bodyEl),
        label: expandAll ? `${intro.title || '语法讲解'}（全览）` : `第 ${stepIdx + 1}/${totalSteps} 张：${activeStep?.title || ''}`,
      });
    };

    root.appendChild(card);
    dom.mainView.replaceChildren(root);
    await renderIntroStep();
    return;
  }

  // 4. Memory Chunk stage
  if ((phase === 'chunk' || phase === 'memory_chunk') && state?.chunk) {
    const chunkHost = document.createElement('div');
    await renderMemoryChunkView(chunkHost, state.chunk, {
      busy: appState.busy,
      onContinue: () => runTopicMutation(() => api.continueStep(topicId, actionGuard(state), DEFAULT_SUBJECT_ID)),
    });
    root.appendChild(chunkHost);
    dom.mainView.replaceChildren(root);
    setAiContext({
      view: 'chunk',
      topicId,
      topicTitle: state.title || topicId,
      isSubmitted: true,
      stepTitle: state.chunk.title || '语法记忆组块',
      stepText: extractNodePlainText(chunkHost),
      label: `组块精读：${state.chunk.title || '语法组块'}`,
    });
    return;
  }

  // 5. Atomic Answer / Feedback card stage
  if ((phase === 'answer' || phase === 'feedback') && state?.current) {
    const current = state.current;
    const isFeedback = phase === 'feedback' || Boolean(current.phase === 'feedback');
    const revealed = Boolean(isFeedback || current.revealed);
    const card = document.createElement('section');
    card.className = 'panelCard';

    const cardHeader = document.createElement('div');
    cardHeader.className = 'questionCardHeader';
    cardHeader.innerHTML = `
      <div>
        <p class="sectionEyebrow">${current.mode === 'review' ? '原子间隔复习卡片' : '语境语法填空检索'}</p>
        <h2 class="cardTitle" style="margin:0;">${escapeHtml(revealed ? (current.title || '完成日语句子中的语法填空') : '完成日语句子中的语法填空')}</h2>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;" id="chunkPeekBar"></div>
    `;
    const peekBar = cardHeader.querySelector('#chunkPeekBar');
    const chunks = current.memory_chunks || [];
    chunks.forEach((chunk, chunkIdx) => {
      const peekBtn = document.createElement('button');
      peekBtn.type = 'button';
      peekBtn.className = 'btn btn--ghost btn--sm';
      peekBtn.textContent = revealed
        ? `查看原讲义：${chunk.title || '语法组块'}`
        : (chunks.length > 1 ? `需要提示？查看相关讲义 ${chunkIdx + 1}` : '需要提示？查看相关讲义');
      peekBtn.addEventListener('click', () => openChunkPeekModal(dom.modalHost, chunk, { revealTitle: revealed }));
      peekBar.appendChild(peekBtn);
    });

    const stemEl = document.createElement('div');
    stemEl.className = 'questionStem';
    await setRichHtml(stemEl, current.html || current.question || '', { literalMath: false });

    const widgetHost = document.createElement('div');
    const feedbackHost = document.createElement('div');
    const actionRow = document.createElement('div');
    actionRow.className = 'actionRow';

    const shownAt = Date.now();
    const savedDraft = isFeedback ? (current.answer || '') : loadDraft(topicId, current.card_id || current.id);
    const feedbackPayload = isFeedback ? current : null;

    let submitBtn = null;
    let widget = null;

    const triggerSubmit = async (selfRating = null) => {
      if (!widget || appState.busy) {
        return;
      }
      if (selfRating === null && !widget.isValid()) {
        showToast('请先填写完整的所有空格答案', { error: true });
        return;
      }
      const answerStr = widget.getAnswerString();
      const elapsedMs = Math.max(0, Date.now() - shownAt);
      appState.busy = true;
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = '判题中...';
      }
      try {
        const res = await api.submit(
          topicId,
          {
            ...actionGuard(state),
            answer: answerStr,
            elapsed_ms: elapsedMs,
            ...(selfRating !== null ? { self_rating: selfRating } : {}),
          },
          DEFAULT_SUBJECT_ID,
        );
        saveDraft(topicId, current.card_id || current.id, '');
        let finalState = res?.state;
        if (res?.submission_id && (res.status === 'pending' || res.status === 'running')) {
          const done = await awaitSubmissionResult(res.submission_id, topicId, { subjectId: DEFAULT_SUBJECT_ID });
          finalState = done?.state;
        }
        if (finalState && finalState.phase) {
          appState.topicState = finalState;
          appState.topicStatesById.set(topicId, { ...(appState.topicStatesById.get(topicId) || {}), ...finalState });
          await renderTopicState(finalState);
        } else {
          await loadAndRenderTopic(topicId);
        }
        await refreshSharedSummary();
      } catch (err) {
        if (err.code === 'stale_revision') {
          showToast('状态已同步更新');
          await loadAndRenderTopic(topicId);
        } else {
          showToast(err.message || '提交失败', { error: true });
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = '提交答案';
          }
        }
      } finally {
        appState.busy = false;
      }
    };

    widget = await createQuestionInputWidget(widgetHost, current, {
      stemContainer: stemEl,
      initialAnswer: savedDraft,
      disabled: isFeedback,
      neutralPlaceholder: !revealed,
      feedback: feedbackPayload,
      onChange: ({ answerString, valid }) => {
        if (!isFeedback) {
          saveDraft(topicId, current.card_id || current.id, answerString);
          if (appState.aiContext && appState.aiContext.cardId === (current.card_id || current.id)) {
            appState.aiContext.userDraft = answerString;
          }
          if (submitBtn) {
            submitBtn.disabled = !valid;
          }
        }
      },
      onSubmitShortcut: () => {
        if (!isFeedback && !current.revealed) {
          triggerSubmit(null);
        }
      },
    });

    if (!isFeedback) {
      if (current.can_self_rate && !current.revealed) {
        submitBtn = document.createElement('button');
        submitBtn.type = 'button';
        submitBtn.className = 'btn btn--primary';
        submitBtn.textContent = '提交答案';
        submitBtn.disabled = !widget.isValid();
        submitBtn.addEventListener('click', () => triggerSubmit(null));
        actionRow.appendChild(submitBtn);

        const revealBtn = document.createElement('button');
        revealBtn.type = 'button';
        revealBtn.className = 'btn btn--secondary';
        revealBtn.textContent = '显示参考答案（自评）';
        revealBtn.addEventListener('click', () => runTopicMutation(() => api.reveal(topicId, actionGuard(state), DEFAULT_SUBJECT_ID)));
        actionRow.appendChild(revealBtn);
      } else if (current.can_self_rate && current.revealed) {
        await renderFeedbackPanel(
          feedbackHost,
          {
            reference_answer: current.reference_answer,
            reference_answer_html: current.reference_answer_html,
            explanation_html: current.explanation_html,
          },
          current,
        );
        const ratingBar = document.createElement('div');
        ratingBar.className = 'selfRatingRow';
        const ratings = [
          { score: 1, label: '1 · 完全不会（重学）', cls: 'btn--danger' },
          { score: 2, label: '2 · 较困难', cls: 'btn--secondary' },
          { score: 3, label: '3 · 良好', cls: 'btn--primary' },
          { score: 4, label: '4 · 非常熟练', cls: 'btn--secondary' },
          { score: 5, label: '5 · 已彻底掌握（停止推送）', cls: 'btn--ghost' },
        ];
        for (const r of ratings) {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = `btn btn--sm ${r.cls}`;
          btn.textContent = r.label;
          btn.addEventListener('click', () => triggerSubmit(r.score));
          ratingBar.appendChild(btn);
        }
        actionRow.appendChild(ratingBar);
      } else {
        submitBtn = document.createElement('button');
        submitBtn.type = 'button';
        submitBtn.className = 'btn btn--primary';
        submitBtn.textContent = '提交答案';
        submitBtn.disabled = !widget.isValid();
        submitBtn.addEventListener('click', () => triggerSubmit(null));
        actionRow.appendChild(submitBtn);
      }
    } else {
      await renderFeedbackPanel(feedbackHost, feedbackPayload, current);
      const nextBtn = document.createElement('button');
      nextBtn.type = 'button';
      nextBtn.className = 'btn btn--primary';
      nextBtn.textContent = '继续下一题 →';
      nextBtn.addEventListener('click', () => runTopicMutation(() => api.continueStep(topicId, actionGuard(state), DEFAULT_SUBJECT_ID)));
      actionRow.appendChild(nextBtn);
    }

    card.append(cardHeader, stemEl, widgetHost, feedbackHost, actionRow);
    root.appendChild(card);
    dom.mainView.replaceChildren(root);
    setAiContext({
      view: revealed ? 'feedback' : 'answer',
      topicId,
      topicTitle: state.title || topicId,
      cardId: current.card_id || current.id || null,
      isSubmitted: revealed,
      stepTitle: revealed ? (current.title || '') : '',
      stepText: extractNodePlainText(stemEl),
      userDraft: savedDraft || '',
      label: `${state.title || topicId} · ${revealed ? '已交卷精讲' : '语法填空作答中'}`,
    });

    if (!isFeedback) {
      requestAnimationFrame(() => widget.focus());
    }
    return;
  }

  // 6. Waiting cooldown stage
  if (phase === 'waiting') {
    const card = document.createElement('section');
    card.className = 'panelCard';
    const nextIso = state.next_available_at;
    const serverMs = state.server_time ? new Date(state.server_time).getTime() : Date.now();
    const targetMs = nextIso ? new Date(nextIso).getTime() : Date.now() + 10000;
    const skewMs = Date.now() - serverMs;

    card.innerHTML = `
      <p class="sectionEyebrow">短暂巩固等待 · Cooldown</p>
      <h2 class="pageTitle">本组记忆点正在间隔冷却中</h2>
      <p class="mutedText">FSRS 会在短暂间隔后自动解锁下一张强化填空卡，帮助在大脑略微遗忘前巩固记忆。</p>
      <div class="banner banner--info" style="margin-top:12px;">
        <div>
          <div><strong>距离下次可继续训练：</strong><span id="cooldownText">计算中…</span></div>
          <div class="mutedText">预计可用时间：${escapeHtml(formatDateTime(nextIso))}</div>
        </div>
        <button type="button" class="btn btn--primary" id="cooldownCheckBtn">检查是否可继续</button>
      </div>
      <div class="actionRow">
        <button type="button" class="btn btn--secondary" id="waitOverviewBtn">先看其他课程</button>
        <button type="button" class="btn btn--secondary" id="waitReviewBtn">查看复习中心</button>
      </div>
    `;

    const cooldownText = card.querySelector('#cooldownText');
    const tick = () => {
      const remainSec = Math.ceil((targetMs - (Date.now() - skewMs)) / 1000);
      if (remainSec <= 0) {
        if (cooldownText) {
          cooldownText.textContent = '已就绪，点击右侧按钮继续！';
        }
        clearInterval(appState.cooldownTimerId);
        appState.cooldownTimerId = null;
        return;
      }
      if (cooldownText) {
        cooldownText.textContent = formatDurationSeconds(remainSec);
      }
    };
    tick();
    appState.cooldownTimerId = setInterval(tick, 1000);

    card.querySelector('#cooldownCheckBtn')?.addEventListener('click', () =>
      runTopicMutation(() => api.continueStep(topicId, actionGuard(state), DEFAULT_SUBJECT_ID)),
    );
    card.querySelector('#waitOverviewBtn')?.addEventListener('click', () => navigate('/overview'));
    card.querySelector('#waitReviewBtn')?.addEventListener('click', () => navigate('/review'));
    root.appendChild(card);
    dom.mainView.replaceChildren(root);
    setAiContext({
      view: 'overview',
      topicId,
      topicTitle: state.title || topicId,
      isSubmitted: true,
      label: `冷却巩固 · ${state.title || topicId}`,
    });
    return;
  }

  // 7. Completed stage
  const topics = getCatalogTopics();
  const idx = topics.findIndex((t) => t.id === topicId);
  const nextTopic = idx >= 0 && idx + 1 < topics.length ? topics[idx + 1] : null;
  const doneCard = document.createElement('section');
  doneCard.className = 'panelCard';
  doneCard.innerHTML = `
    <p class="sectionEyebrow">课时已掌握 · Completed</p>
    <h2 class="pageTitle">恭喜完成「${escapeHtml(state?.title || topicId)}」！</h2>
    <p class="mutedText">本课全部记忆点已通过检索验证，后续将在 FSRS 间隔到期时于复习中心自动推送。</p>
    <div class="actionRow">
      ${nextTopic ? `<button type="button" class="btn btn--primary" id="nextTopicBtn">进入下一课：${escapeHtml(nextTopic.title || nextTopic.id)} →</button>` : ''}
      <button type="button" class="btn btn--secondary" id="doneReviewBtn">查看间隔复习中心</button>
      <button type="button" class="btn btn--ghost" id="doneOverviewBtn">返回课程总览</button>
    </div>
  `;
  doneCard.querySelector('#nextTopicBtn')?.addEventListener('click', () => navigate(`/topic/${encodeURIComponent(nextTopic.id)}`));
  doneCard.querySelector('#doneReviewBtn')?.addEventListener('click', () => navigate('/review'));
  doneCard.querySelector('#doneOverviewBtn')?.addEventListener('click', () => navigate('/overview'));
  root.appendChild(doneCard);
  dom.mainView.replaceChildren(root);
  setAiContext({
    view: 'overview',
    topicId,
    topicTitle: state.title || topicId,
    isSubmitted: true,
    label: `已掌握课时：${state.title || topicId}`,
  });
}

/* ---------------- Review Center & Review Paper ---------------- */
async function renderReviewCenterView(paperId = null) {
  showSidebarShell(false);
  clearTimers();

  if (paperId) {
    await renderActiveReviewPaper(paperId);
    return;
  }

  const inbox = appState.reviewPaperInbox || {};
  const atomicItems = Array.isArray(appState.atomicReviews?.items) ? appState.atomicReviews.items : [];
  const activePapers = Array.isArray(inbox.active) ? inbox.active : [];
  const candidates = Array.isArray(inbox.items) ? inbox.items : [];
  const modItems = Array.isArray(appState.moduleReviews?.items) ? appState.moduleReviews.items : [];

  const root = document.createElement('div');
  const headerCard = document.createElement('section');
  headerCard.className = 'panelCard';
  headerCard.innerHTML = `
    <p class="sectionEyebrow">FSRS SPACED REPETITION · 间隔复习中心</p>
    <h1 class="pageTitle">日语语法间隔复习队列</h1>
    <p class="mutedText">按遗忘曲线精准提取已到期记忆卡片，支持单卡速练与整卷巩固；全部答案均支持日文汉字/假名等效判定。</p>
  `;
  root.appendChild(headerCard);

  renderPauseAlert(root, appState.pauses, async () => {
    await refreshSharedSummary();
    await renderReviewCenterView();
  });

  if (activePapers.length) {
    const activePanel = document.createElement('section');
    activePanel.className = 'panelCard';
    activePanel.innerHTML = '<h2 class="cardTitle">进行中的复习任务</h2>';
    for (const item of activePapers) {
      const row = document.createElement('div');
      row.className = 'reviewItemRow';
      row.innerHTML = `
        <div>
          <div style="font-weight:700;">${escapeHtml(item.title || item.id)}</div>
          <div class="mutedText">已完成 ${Number(item.done || 0)} / ${Number(item.count || 0)} 题</div>
        </div>
        <button type="button" class="btn btn--primary btn--sm" data-open-paper="${escapeHtml(item.id)}">继续作答</button>
      `;
      activePanel.appendChild(row);
    }
    root.appendChild(activePanel);
  }

  const split = document.createElement('div');
  split.className = 'reviewSplit';
  split.style.marginTop = '18px';

  const paperCol = document.createElement('section');
  paperCol.className = 'panelCard';
  paperCol.innerHTML = '<h2 class="cardTitle">可发起的综合/单卡复习</h2>';
  if (!candidates.length) {
    paperCol.innerHTML += `
      <p class="mutedText">当前暂无到期的组合或单卡复习任务${appState.atomicReviews?.next_due_at ? `（下次到期时间：${escapeHtml(formatDateTime(appState.atomicReviews.next_due_at))}）` : ''}。</p>
    `;
  } else {
    for (const cand of candidates) {
      const row = document.createElement('div');
      row.className = 'reviewItemRow';
      const isPaperCand = cand.kind === 'paper';
      const safeTitle = isPaperCand ? (cand.title || '综合语法复习卷') : '到期单卡精准强化';
      row.innerHTML = `
        <div>
          <div style="font-weight:700;">${escapeHtml(safeTitle)}</div>
          <div class="mutedText">${isPaperCand ? `综合复习卷 · 共 ${cand.count} 题` : '单点精准强化 · 1 题（作答后揭晓考点）'}</div>
        </div>
        <button type="button" class="btn btn--primary btn--sm" data-start-candidate="${escapeHtml(cand.id)}">开始复习</button>
      `;
      paperCol.appendChild(row);
    }
  }
  split.appendChild(paperCol);

  const topicCol = document.createElement('section');
  topicCol.className = 'panelCard';
  topicCol.innerHTML = '<h2 class="cardTitle">各课时到期明细</h2>';
  if (!atomicItems.length) {
    topicCol.innerHTML += '<p class="mutedText">尚未产生课时学习后的间隔复习排程。</p>';
  } else {
    for (const item of atomicItems) {
      const row = document.createElement('div');
      row.className = 'reviewItemRow';
      row.innerHTML = `
        <div>
          <div style="font-weight:700;">${escapeHtml(item.title || item.topic_id)}</div>
          <div class="mutedText">
            到期 ${Number(item.due_count || 0)} 项
            ${item.next_due_at ? ` · 下次到期：${escapeHtml(formatDateTime(item.next_due_at))}` : ''}
            ${item.paused ? ' · 已暂停' : ''}
          </div>
        </div>
        <button type="button" class="btn btn--secondary btn--sm" data-goto-topic="${escapeHtml(item.topic_id)}">进入课时</button>
      `;
      topicCol.appendChild(row);
    }
  }
  split.appendChild(topicCol);
  root.appendChild(split);

  if (modItems.length) {
    const modPanel = document.createElement('section');
    modPanel.className = 'panelCard';
    modPanel.innerHTML = '<h2 class="cardTitle">模块复习排程</h2>';
    for (const mod of modItems) {
      const row = document.createElement('div');
      row.className = 'reviewItemRow';
      row.innerHTML = `
        <div>
          <div style="font-weight:700;">${escapeHtml(mod.title || mod.module_title || mod.module_id)}</div>
          <div class="mutedText">${escapeHtml(mod.topic_title || mod.topic_id || '')}</div>
        </div>
        <button type="button" class="btn btn--secondary btn--sm" data-goto-topic="${escapeHtml(mod.topic_id)}">查看</button>
      `;
      modPanel.appendChild(row);
    }
    root.appendChild(modPanel);
  }

  dom.mainView.replaceChildren(root);
  setAiContext({
    view: 'review',
    isSubmitted: true,
    label: 'FSRS 间隔复习中心',
  });

  for (const btn of root.querySelectorAll('[data-open-paper]')) {
    btn.addEventListener('click', () => navigate(`/review/paper/${encodeURIComponent(btn.dataset.openPaper)}`));
  }
  for (const btn of root.querySelectorAll('[data-goto-topic]')) {
    btn.addEventListener('click', () => navigate(`/topic/${encodeURIComponent(btn.dataset.gotoTopic)}`));
  }
  for (const btn of root.querySelectorAll('[data-start-candidate]')) {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        const paper = await api.reviewPaperOpen(btn.dataset.startCandidate, newRequestId('paper'), DEFAULT_SUBJECT_ID);
        appState.activePaperState = paper;
        navigate(`/review/paper/${encodeURIComponent(paper.id)}`);
      } catch (err) {
        showToast(err.message || '开启复习失败，请刷新列表重试', { error: true });
        await refreshSharedSummary();
        await renderReviewCenterView();
      }
    });
  }
}

async function pollPaperUntilSettled(paperId, initialPaper = null) {
  let paper = initialPaper || (await api.reviewPaperState(paperId, DEFAULT_SUBJECT_ID));
  const deadline = Date.now() + 20000;
  while (paper && paper.phase === 'grading' && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 350));
    paper = await api.reviewPaperState(paperId, DEFAULT_SUBJECT_ID);
  }
  return paper;
}

async function renderActiveReviewPaper(paperId) {
  let paper;
  try {
    paper = await api.reviewPaperState(paperId, DEFAULT_SUBJECT_ID);
    if (paper?.phase === 'grading') {
      paper = await pollPaperUntilSettled(paperId, paper);
    }
  } catch (err) {
    showToast(err.message || '无法加载复习卷', { error: true });
    navigate('/review');
    return;
  }
  appState.activePaperId = paperId;
  appState.activePaperState = paper;

  const root = document.createElement('div');
  const card = document.createElement('section');
  card.className = 'panelCard';

  const isDone = paper.phase === 'done' || paper.phase === 'expired' || paper.phase === 'cancelled';
  card.innerHTML = `
    <div class="paperToolbar">
      <div>
        <p class="sectionEyebrow">间隔复习作答 · ${escapeHtml(paper.kind === 'paper' ? '综合复习卷' : '专项巩固')}</p>
        <h1 class="pageTitle" style="margin:0;">${escapeHtml(isDone ? (paper.title || '日语语法复习') : (paper.kind === 'paper' ? '综合语法间隔复习卷' : '单项语法间隔强化'))}</h1>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <span class="pill pill--accent">共 ${(paper.items || []).length} 题</span>
        ${paper.phase === 'answer' ? '<button type="button" class="btn btn--ghost btn--sm" id="cancelPaperBtn">取消本次复习</button>' : ''}
        <button type="button" class="btn btn--secondary btn--sm" id="backReviewListBtn">返回复习中心</button>
      </div>
    </div>
  `;

  const widgets = new Map();
  let saveTimer = null;
  let currentRevision = paper.revision;
  let activeFocusCtx = null;

  const flushDraft = async (index, answerString) => {
    if (!paper.can_edit) {
      return;
    }
    try {
      const updated = await api.reviewPaperDraft(
        {
          paper_id: paper.id,
          expected_revision: currentRevision,
          answers: [{ index, answer: answerString, elapsed_ms: 1000 }],
        },
        DEFAULT_SUBJECT_ID,
      );
      if (updated && updated.revision !== undefined) {
        currentRevision = updated.revision;
      }
    } catch {
      // Non-fatal draft sync error; learner's live DOM holds latest text.
    }
  };

  for (const item of paper.items || []) {
    const itemDone = Boolean(isDone || item.completed || item.result);
    const block = document.createElement('div');
    block.className = 'paperItemBlock';
    const head = document.createElement('div');
    head.className = 'questionCardHeader';
    const metaTitleHtml = itemDone && (item.source_title || item.title)
      ? ` · ${escapeHtml(item.source_title || item.title)}`
      : ' · 提交整卷后显示所属语法点';
    head.innerHTML = `
      <div>
        <strong>第 ${item.index + 1} 题</strong>
        <span class="mutedText">${metaTitleHtml}</span>
      </div>
      ${item.result ? `<span class="pill ${item.result.correct ? 'pill--success' : 'pill--danger'}">${item.result.correct ? '✓ 正确' : '✗ 有误'}</span>` : ''}
    `;

    const stemEl = document.createElement('div');
    stemEl.className = 'questionStem';
    await setRichHtml(stemEl, item.html || '', { literalMath: false });

    const widgetHost = document.createElement('div');
    const feedbackHost = document.createElement('div');
    const itemFeedback = item.result ? { ...item.result, explanation_html: item.explanation_html, answer_display: item.answer_display, reference_answer: item.reference_answer, reference_answer_html: item.reference_answer_html, choice_feedback: item.choice_feedback } : null;

    const itemCtxPayload = (draftOverride = null) => ({
      view: 'paper',
      topicId: item.topic_id || undefined,
      topicTitle: itemDone ? (item.source_title || paper.title || '复习巩固') : (paper.kind === 'paper' ? '综合语法间隔复习卷' : '单项语法间隔强化'),
      paperId: paper.id,
      cardId: item.card_id || item.id || undefined,
      isSubmitted: itemDone,
      stepTitle: `第 ${item.index + 1} 题`,
      stepText: extractNodePlainText(stemEl),
      userDraft: draftOverride !== null ? draftOverride : (widgets.get(item.index)?.getAnswerString() || item.answer || ''),
      label: itemDone ? `复习卷精讲 · 第 ${item.index + 1} 题` : `综合复习作答 · 第 ${item.index + 1} 题`,
    });

    if (!activeFocusCtx) {
      activeFocusCtx = itemCtxPayload(item.answer || '');
    }

    const widget = await createQuestionInputWidget(widgetHost, { interaction: item.interaction, choice_feedback: item.choice_feedback }, {
      stemContainer: stemEl,
      initialAnswer: item.answer || '',
      disabled: isDone || Boolean(item.completed) || !paper.can_edit,
      neutralPlaceholder: !itemDone,
      feedback: itemFeedback,
      onChange: ({ answerString }) => {
        if (appState.aiContext?.paperId === paper.id && appState.aiContext?.cardId === (item.card_id || item.id)) {
          appState.aiContext.userDraft = answerString;
        }
        clearTimeout(saveTimer);
        saveTimer = setTimeout(() => flushDraft(item.index, answerString), 450);
      },
    });
    widgets.set(item.index, widget);

    block.addEventListener('focusin', () => {
      setAiContext(itemCtxPayload());
    });

    if (itemFeedback) {
      await renderFeedbackPanel(feedbackHost, itemFeedback, item);
    }
    block.append(head, stemEl, widgetHost, feedbackHost);
    card.appendChild(block);
  }

  if (paper.phase === 'answer' && paper.can_submit) {
    const row = document.createElement('div');
    row.className = 'actionRow';
    const submitAllBtn = document.createElement('button');
    submitAllBtn.type = 'button';
    submitAllBtn.className = 'btn btn--primary';
    submitAllBtn.textContent = '提交全部复习作答';
    submitAllBtn.addEventListener('click', async () => {
      const pendingItems = (paper.items || []).filter((i) => !i.completed);
      for (const item of pendingItems) {
        const w = widgets.get(item.index);
        if (!w?.isValid()) {
          showToast(`第 ${item.index + 1} 题尚未填写完整`, { error: true });
          return;
        }
      }
      submitAllBtn.disabled = true;
      submitAllBtn.textContent = '正在保存并判分…';
      try {
        // Save all drafts cleanly in batches of <= 2 per backend schema limit.
        for (let i = 0; i < pendingItems.length; i += 2) {
          const batch = pendingItems.slice(i, i + 2).map((item) => ({
            index: item.index,
            answer: widgets.get(item.index).getAnswerString(),
            elapsed_ms: 1500,
          }));
          const updated = await api.reviewPaperDraft(
            { paper_id: paper.id, expected_revision: currentRevision, answers: batch },
            DEFAULT_SUBJECT_ID,
          );
          if (updated?.revision !== undefined) {
            currentRevision = updated.revision;
          }
        }
        const submitted = await api.reviewPaperSubmit(
          { paper_id: paper.id, expected_revision: currentRevision },
          DEFAULT_SUBJECT_ID,
        );
        if (submitted?.phase === 'grading') {
          await pollPaperUntilSettled(paper.id, submitted);
        }
        await refreshSharedSummary();
        await renderActiveReviewPaper(paper.id);
      } catch (err) {
        showToast(err.message || '提交失败', { error: true });
        submitAllBtn.disabled = false;
        submitAllBtn.textContent = '提交全部复习作答';
      }
    });
    row.appendChild(submitAllBtn);
    card.appendChild(row);
  }

  root.appendChild(card);
  dom.mainView.replaceChildren(root);
  setAiContext(
    activeFocusCtx || {
      view: 'paper',
      paperId: paper.id,
      isSubmitted: isDone,
      label: isDone ? (paper.title || '复习卷精讲') : '综合语法间隔复习卷',
    },
  );

  card.querySelector('#backReviewListBtn')?.addEventListener('click', async () => {
    await refreshSharedSummary();
    navigate('/review');
  });
  card.querySelector('#cancelPaperBtn')?.addEventListener('click', async () => {
    try {
      await api.reviewPaperCancel(paper.id, DEFAULT_SUBJECT_ID);
      await refreshSharedSummary();
      navigate('/review');
    } catch (err) {
      showToast(err.message || '取消失败', { error: true });
    }
  });
}

/* ---------------- Learning Stats View ---------------- */
async function renderStatsView() {
  showSidebarShell(false);
  clearTimers();

  let report = null;
  try {
    report = await api.studentReport(30, DEFAULT_SUBJECT_ID);
    appState.studentReport = report;
  } catch {
    report = null;
  }

  const topics = getCatalogTopics();
  const dueCount = getAtomicDueCount();
  const completedCount = topics.filter((t) => {
    const st = appState.topicStatesById.get(t.id) || t;
    return Boolean(st.completed || st.status === 'completed' || st.completed_at);
  }).length;

  const summary = report?.summary || appState.dashboard?.summary || {};
  const totalAttempts = summary.attempts ?? summary.total_submissions ?? '—';
  const accuracy = summary.accuracy !== undefined && summary.accuracy !== null ? `${Math.round(Number(summary.accuracy) * 100)}%` : '—';

  const root = document.createElement('div');
  const grid = document.createElement('section');
  grid.className = 'statsGrid';
  grid.innerHTML = `
    <div class="statCard">
      <div class="statNum">${completedCount} / ${topics.length}</div>
      <div class="statLabel">已完成语法课时</div>
    </div>
    <div class="statCard">
      <div class="statNum">${dueCount}</div>
      <div class="statLabel">当前到期复习卡</div>
    </div>
    <div class="statCard">
      <div class="statNum">${escapeHtml(String(totalAttempts))}</div>
      <div class="statLabel">累计提交作答次数</div>
    </div>
    <div class="statCard">
      <div class="statNum">${escapeHtml(String(accuracy))}</div>
      <div class="statLabel">近 30 日总体正确率</div>
    </div>
  `;
  root.appendChild(grid);

  const tableCard = document.createElement('section');
  tableCard.className = 'panelCard';
  tableCard.innerHTML = `
    <p class="sectionEyebrow">COURSE MASTERY · 分课掌握状态</p>
    <h2 class="cardTitle">各课时学习与 FSRS 排程概览</h2>
    <table class="dataTable">
      <thead>
        <tr>
          <th>课时</th>
          <th>标题</th>
          <th>状态</th>
          <th>记忆点进度</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody id="statsTopicTbody"></tbody>
    </table>
  `;

  const tbody = tableCard.querySelector('#statsTopicTbody');
  const atomicById = new Map((appState.atomicReviews?.items || []).map((it) => [it.topic_id, it]));

  topics.forEach((topic, idx) => {
    const st = appState.topicStatesById.get(topic.id) || topic;
    const rev = atomicById.get(topic.id);
    const chapter = getTopicDisplayChapter(topic.id, idx, topic.chapter);
    const completed = Boolean(st.completed || st.status === 'completed' || st.completed_at);
    const learnedPts = Number(st.learned_count ?? st.topic_progress?.points?.completed ?? 0);
    const totalPts = Number(st.point_count ?? st.topic_progress?.points?.total ?? 0);

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>第 ${chapter} 课</td>
      <td><strong>${escapeHtml(topic.title || topic.id)}</strong></td>
      <td>
        <span class="pill ${completed ? 'pill--success' : 'pill--accent'}">${completed ? '已掌握' : '学习中'}</span>
        ${rev?.due_count ? `<span class="pill pill--warning">到期 ${rev.due_count}</span>` : ''}
      </td>
      <td>${totalPts > 0 ? `${learnedPts} / ${totalPts}` : (completed ? '已达标' : '进行中')}</td>
      <td><button type="button" class="btn btn--secondary btn--sm" data-stat-topic="${escapeHtml(topic.id)}">打开课时</button></td>
    `;
    tbody.appendChild(tr);
  });

  if (!topics.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="mutedText">暂无课程统计数据。</td></tr>';
  }

  root.appendChild(tableCard);
  dom.mainView.replaceChildren(root);
  setAiContext({
    view: 'stats',
    isSubmitted: true,
    label: '日语学习统计与 FSRS 排程概览',
  });

  for (const btn of root.querySelectorAll('[data-stat-topic]')) {
    btn.addEventListener('click', () => navigate(`/topic/${encodeURIComponent(btn.dataset.statTopic)}`));
  }
}

/* ---------------- Route Dispatcher & Global Bindings ---------------- */
async function handleRouteChange() {
  const parsed = parseRoute();
  appState.route = parsed.route === 'topic' ? 'learn' : parsed.route;
  updateNavBadges();

  if (parsed.route === 'overview') {
    await renderOverviewView();
  } else if (parsed.route === 'learn' || parsed.route === 'topic') {
    await loadAndRenderTopic(parsed.topicId);
  } else if (parsed.route === 'review') {
    await renderReviewCenterView(parsed.paperId || null);
  } else if (parsed.route === 'stats') {
    await renderStatsView();
  }
}

function bindGlobalEvents() {
  dom.brandHomeBtn?.addEventListener('click', () => navigate('/overview'));

  for (const tab of dom.navTabs) {
    tab.addEventListener('click', () => {
      const route = tab.dataset.route;
      if (route === 'learn') {
        navigate('/learn');
      } else {
        navigate(`/${route}`);
      }
    });
  }

  dom.romajiToggleBtn?.addEventListener('click', () => {
    const currentlyHidden = document.body.classList.contains('hide-romaji');
    applyRomajiPreference(!currentlyHidden);
  });

  dom.historyDrawerToggle?.addEventListener('click', () => {
    setSidebarOpen(!appState.sidebarOpen);
  });

  dom.sidebarBackdrop?.addEventListener('click', () => {
    setSidebarOpen(false);
  });

  window.addEventListener('hashchange', () => {
    handleRouteChange();
  });
}

async function init() {
  applyRomajiPreference(isHideRomajiStored());
  appState.aiAssistant = createAiAssistant({
    drawerHost: dom.aiDrawerHost,
    drawerToggleBtn: dom.aiDrawerToggleBtn,
    settingsBtn: dom.aiSettingsBtn,
    modalHost: dom.modalHost,
    getContext: () => appState.aiContext,
    showToast,
  });
  bindGlobalEvents();
  appState.aiAssistant.refreshConfig({ silent: true });
  await refreshSharedSummary();
  await handleRouteChange();
}

init();
