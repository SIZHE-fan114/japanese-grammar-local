import { escapeHtml } from './math-render.js';

export function normalizeGraph(graphPayload, catalogTopics = []) {
  const topicLookup = new Map();
  for (const topic of catalogTopics || []) {
    const id = topic.id || topic.topic_id;
    if (id) {
      topicLookup.set(id, topic);
    }
  }

  const rawNodes = Array.isArray(graphPayload?.nodes) ? graphPayload.nodes : [];
  const rawEdges = Array.isArray(graphPayload?.edges) ? graphPayload.edges : [];

  const nodes = rawNodes.map((node, index) => {
    const id = node.id || node.topic_id || node.node_id;
    const catalogMeta = topicLookup.get(id) || {};
    const numMatch = String(id || '').match(/(?:jp|ch|lesson|topic)?0*(\d+)/i);
    const chapter = node.chapter ?? catalogMeta.chapter ?? (numMatch ? Number(numMatch[1]) : index + 1);
    const title = node.title || catalogMeta.title || id;
    const prerequisites = Array.isArray(node.prerequisites)
      ? node.prerequisites
      : rawEdges
          .filter((e) => (e.to || e.target) === id)
          .map((e) => e.from || e.source);

    return {
      ...catalogMeta,
      ...node,
      id,
      topic_id: node.topic_id || id,
      title,
      chapter,
      prerequisites,
    };
  });

  if (!nodes.length && catalogTopics.length) {
    return {
      id: graphPayload?.id || 'japanese-grammar-core',
      title: graphPayload?.title || '日本語文法 · 语法填空先修知识图谱',
      nodes: catalogTopics.map((topic, idx) => {
        const id = topic.id || topic.topic_id;
        const numMatch = String(id || '').match(/(?:jp|ch|lesson)?0*(\d+)/i);
        return {
          ...topic,
          id,
          topic_id: id,
          chapter: topic.chapter ?? (numMatch ? Number(numMatch[1]) : idx + 1),
          prerequisites: idx > 0 ? [catalogTopics[idx - 1].id || catalogTopics[idx - 1].topic_id] : [],
        };
      }),
      edges: catalogTopics.slice(1).map((topic, idx) => ({
        from: catalogTopics[idx].id || catalogTopics[idx].topic_id,
        to: topic.id || topic.topic_id,
      })),
    };
  }

  const nodeIds = new Set(nodes.map((n) => n.id));
  const edges = [];
  const seenEdges = new Set();

  for (const edge of rawEdges) {
    const from = edge.from || edge.source;
    const to = edge.to || edge.target;
    if (!from || !to || !nodeIds.has(from) || !nodeIds.has(to)) {
      continue;
    }
    const key = `${from}=>${to}`;
    if (!seenEdges.has(key)) {
      seenEdges.add(key);
      edges.push({ from, to });
    }
  }

  for (const node of nodes) {
    for (const pre of node.prerequisites || []) {
      if (!nodeIds.has(pre)) {
        continue;
      }
      const key = `${pre}=>${node.id}`;
      if (!seenEdges.has(key)) {
        seenEdges.add(key);
        edges.push({ from: pre, to: node.id });
      }
    }
  }

  return {
    id: graphPayload?.id || graphPayload?.graph_id || 'japanese-grammar-core',
    title: graphPayload?.title || '日本語文法 · 语法填空先修知识图谱',
    nodes,
    edges,
  };
}

export function computeLayers(graph) {
  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  const inDegree = new Map();
  const children = new Map();
  const depth = new Map();

  for (const n of nodes) {
    inDegree.set(n.id, 0);
    children.set(n.id, []);
    depth.set(n.id, 0);
  }
  for (const e of edges) {
    if (!inDegree.has(e.to) || !children.has(e.from)) {
      continue;
    }
    inDegree.set(e.to, inDegree.get(e.to) + 1);
    children.get(e.from).push(e.to);
  }

  const queue = nodes.filter((n) => (inDegree.get(n.id) || 0) === 0).map((n) => n.id);
  const visited = new Set();

  while (queue.length) {
    const id = queue.shift();
    visited.add(id);
    const d = depth.get(id) || 0;
    for (const nextId of children.get(id) || []) {
      depth.set(nextId, Math.max(depth.get(nextId) || 0, d + 1));
      const deg = (inDegree.get(nextId) || 1) - 1;
      inDegree.set(nextId, deg);
      if (deg === 0) {
        queue.push(nextId);
      }
    }
  }

  for (const n of nodes) {
    if (!visited.has(n.id)) {
      depth.set(n.id, 0);
    }
  }

  const layers = [];
  for (const n of nodes) {
    const layerIdx = depth.get(n.id) || 0;
    if (!layers[layerIdx]) {
      layers[layerIdx] = [];
    }
    layers[layerIdx].push(n);
  }

  return layers.filter(Boolean);
}

export function ancestorsOf(graph, targetId) {
  const parents = new Map();
  for (const e of graph?.edges || []) {
    if (!parents.has(e.to)) {
      parents.set(e.to, []);
    }
    parents.get(e.to).push(e.from);
  }
  const visited = new Set();
  const stack = [...(parents.get(targetId) || [])];
  while (stack.length) {
    const id = stack.pop();
    if (visited.has(id)) {
      continue;
    }
    visited.add(id);
    for (const p of parents.get(id) || []) {
      if (!visited.has(p)) {
        stack.push(p);
      }
    }
  }
  return visited;
}

export function renderCourseGraph(container, graphPayload, options = {}) {
  if (!container) {
    return;
  }
  const {
    catalogTopics = [],
    activeTopicId = null,
    onSelectTopic = null,
    topicStates = new Map(),
  } = options;

  const graph = normalizeGraph(graphPayload, catalogTopics);
  const layers = computeLayers(graph);

  if (!layers.length) {
    container.innerHTML = '<p class="mutedText">暂无课程先修关系图数据。</p>';
    return;
  }

  const nodeW = 232;
  const nodeH = 74;
  const colGap = 54;
  const rowGap = 24;
  const padX = 22;
  const padY = 22;

  const maxRows = Math.max(...layers.map((layer) => layer.length), 1);
  const svgWidth = padX * 2 + layers.length * nodeW + Math.max(0, layers.length - 1) * colGap;
  const svgHeight = padY * 2 + maxRows * nodeH + Math.max(0, maxRows - 1) * rowGap;

  const coords = new Map();
  layers.forEach((layer, colIdx) => {
    const totalLayerHeight = layer.length * nodeH + Math.max(0, layer.length - 1) * rowGap;
    const startY = (svgHeight - totalLayerHeight) / 2;
    const x = padX + colIdx * (nodeW + colGap);
    layer.forEach((node, rowIdx) => {
      const y = startY + rowIdx * (nodeH + rowGap);
      coords.set(node.id, { x, y, node });
    });
  });

  const highlightedAncestors = activeTopicId ? ancestorsOf(graph, activeTopicId) : new Set();

  const headerHtml = `
    <div class="dagPanelHeader">
      <div>
        <h3 class="cardTitle" style="margin:0;">${escapeHtml(graph.title)}</h3>
        <span class="mutedText">按掌握节奏依次解锁日语基础句型，点击任意节点可直接进入该课练习</span>
      </div>
      <div class="dagLegend">
        <span><span class="dagLegendDot" style="background:#1b7f4b;"></span>已掌握</span>
        <span><span class="dagLegendDot" style="background:#9e4756;"></span>当前可学</span>
        <span><span class="dagLegendDot" style="background:#b7a7ac;"></span>待前置解锁</span>
      </div>
    </div>
  `;

  const svgNs = 'http://www.w3.org/2000/svg';
  const frame = document.createElement('div');
  frame.className = 'dagSvgFrame';

  const svg = document.createElementNS(svgNs, 'svg');
  svg.setAttribute('viewBox', `0 0 ${svgWidth} ${svgHeight}`);
  svg.setAttribute('width', String(svgWidth));
  svg.setAttribute('height', String(svgHeight));
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', '日语语法课程先修关系图');

  const defs = document.createElementNS(svgNs, 'defs');
  const createArrow = (id, color) => {
    const marker = document.createElementNS(svgNs, 'marker');
    marker.setAttribute('id', id);
    marker.setAttribute('viewBox', '0 0 10 10');
    marker.setAttribute('refX', '8');
    marker.setAttribute('refY', '5');
    marker.setAttribute('markerWidth', '6');
    marker.setAttribute('markerHeight', '6');
    marker.setAttribute('orient', 'auto-start-reverse');
    const path = document.createElementNS(svgNs, 'path');
    path.setAttribute('d', 'M 0 1 L 10 5 L 0 9 z');
    path.setAttribute('fill', color);
    marker.appendChild(path);
    return marker;
  };
  defs.appendChild(createArrow('jp-dag-arrow', '#b8a3a8'));
  defs.appendChild(createArrow('jp-dag-arrow-active', '#9e4756'));
  svg.appendChild(defs);

  for (const edge of graph.edges) {
    const fromPos = coords.get(edge.from);
    const toPos = coords.get(edge.to);
    if (!fromPos || !toPos) {
      continue;
    }
    const x1 = fromPos.x + nodeW;
    const y1 = fromPos.y + nodeH / 2;
    const x2 = toPos.x;
    const y2 = toPos.y + nodeH / 2;
    const cx1 = x1 + colGap * 0.45;
    const cx2 = x2 - colGap * 0.45;
    const isActiveEdge =
      activeTopicId && (edge.to === activeTopicId || (highlightedAncestors.has(edge.from) && highlightedAncestors.has(edge.to)));

    const path = document.createElementNS(svgNs, 'path');
    path.setAttribute('d', `M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', isActiveEdge ? '#9e4756' : '#c7b8bc');
    path.setAttribute('stroke-width', isActiveEdge ? '2.4' : '1.7');
    path.setAttribute('marker-end', `url(#${isActiveEdge ? 'jp-dag-arrow-active' : 'jp-dag-arrow'})`);
    svg.appendChild(path);
  }

  const parentsByNode = new Map();
  for (const edge of graph.edges) {
    if (!parentsByNode.has(edge.to)) {
      parentsByNode.set(edge.to, []);
    }
    parentsByNode.get(edge.to).push(edge.from);
  }

  for (const [, pos] of coords) {
    const { x, y, node } = pos;
    const runtimeState = topicStates.get(node.id) || {};
    const completed = Boolean(
      node.completed || runtimeState.completed || runtimeState.status === 'completed' || runtimeState.completed_at,
    );
    const locked = Boolean(
      node.locked ||
      runtimeState.locked ||
      node.dependency_ready === false ||
      runtimeState.dependency_ready === false ||
      runtimeState.dependency_blocked,
    );
    const parents = parentsByNode.get(node.id) || [];
    const lockedByReview = locked && parents.length > 0 && parents.every((pid) => {
      const pRuntime = topicStates.get(pid) || {};
      const pNode = coords.get(pid)?.node || {};
      return Boolean(pNode.completed || pRuntime.completed || pRuntime.status === 'completed' || pRuntime.completed_at);
    });
    const selected = activeTopicId === node.id;

    let fill = '#ffffff';
    let stroke = '#d7c4c9';
    let badgeBg = '#f9ecef';
    let badgeInk = '#7d3340';
    if (completed) {
      fill = '#edf8f2';
      stroke = '#1b7f4b';
      badgeBg = '#d8f1e3';
      badgeInk = '#135a34';
    } else if (selected) {
      fill = '#fdf2f4';
      stroke = '#9e4756';
      badgeBg = '#9e4756';
      badgeInk = '#ffffff';
    } else if (locked) {
      fill = '#f5f1f2';
      stroke = '#d5cbce';
      badgeBg = '#e8dfe2';
      badgeInk = '#6e5e63';
    }

    const group = document.createElementNS(svgNs, 'g');
    group.setAttribute('transform', `translate(${x}, ${y})`);
    group.style.cursor = 'pointer';

    const rect = document.createElementNS(svgNs, 'rect');
    rect.setAttribute('width', String(nodeW));
    rect.setAttribute('height', String(nodeH));
    rect.setAttribute('rx', '12');
    rect.setAttribute('fill', fill);
    rect.setAttribute('stroke', stroke);
    rect.setAttribute('stroke-width', selected ? '2.5' : '1.5');
    group.appendChild(rect);

    const badgeRect = document.createElementNS(svgNs, 'rect');
    badgeRect.setAttribute('x', '12');
    badgeRect.setAttribute('y', '11');
    badgeRect.setAttribute('width', '62');
    badgeRect.setAttribute('height', '20');
    badgeRect.setAttribute('rx', '6');
    badgeRect.setAttribute('fill', badgeBg);
    group.appendChild(badgeRect);

    const badgeText = document.createElementNS(svgNs, 'text');
    badgeText.setAttribute('x', '43');
    badgeText.setAttribute('y', '25');
    badgeText.setAttribute('text-anchor', 'middle');
    badgeText.setAttribute('font-size', '11');
    badgeText.setAttribute('font-weight', '700');
    badgeText.setAttribute('fill', badgeInk);
    badgeText.textContent = `第 ${node.chapter} 课`;
    group.appendChild(badgeText);

    const statusText = document.createElementNS(svgNs, 'text');
    statusText.setAttribute('x', String(nodeW - 12));
    statusText.setAttribute('y', '25');
    statusText.setAttribute('text-anchor', 'end');
    statusText.setAttribute('font-size', '11');
    statusText.setAttribute('font-weight', '600');
    statusText.setAttribute('fill', completed ? '#1b7f4b' : locked ? '#8b7b80' : '#9e4756');
    statusText.textContent = completed ? '已掌握' : lockedByReview ? '待前置复习' : locked ? '未解锁' : '可学习';
    group.appendChild(statusText);

    const label = String(node.title || node.id || '');
    const clipped = label.length > 16 ? `${label.slice(0, 15)}…` : label;
    const titleText = document.createElementNS(svgNs, 'text');
    titleText.setAttribute('x', '12');
    titleText.setAttribute('y', '52');
    titleText.setAttribute('font-size', '13.5');
    titleText.setAttribute('font-weight', '700');
    titleText.setAttribute('fill', '#22191c');
    titleText.textContent = clipped;
    group.appendChild(titleText);

    if (typeof onSelectTopic === 'function') {
      group.addEventListener('click', () => onSelectTopic(node.topic_id || node.id));
    }
    svg.appendChild(group);
  }

  frame.appendChild(svg);
  container.innerHTML = headerHtml;
  container.appendChild(frame);
}
