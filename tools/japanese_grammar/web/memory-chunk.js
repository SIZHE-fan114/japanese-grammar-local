import { escapeHtml, setRichHtml, setRichText } from './math-render.js';

function textNodesUnder(root) {
  const nodes = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue) {
        return NodeFilter.FILTER_REJECT;
      }
      const parent = node.parentElement;
      if (!parent) {
        return NodeFilter.FILTER_REJECT;
      }
      if (parent.closest('script, style, svg, math, .katex, .mermaid-source, .mermaid-output')) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  let current = walker.nextNode();
  while (current) {
    nodes.push(current);
    current = walker.nextNode();
  }
  return nodes;
}

function cpToUtf16Index(str, cpOffset) {
  if (cpOffset <= 0) {
    return 0;
  }
  let cp = 0;
  let utf16 = 0;
  while (utf16 < str.length && cp < cpOffset) {
    const code = str.codePointAt(utf16);
    utf16 += code > 0xffff ? 2 : 1;
    cp += 1;
  }
  return utf16;
}

function utf16ToCpOffset(str, utf16Offset) {
  let cp = 0;
  let utf16 = 0;
  const target = Math.min(utf16Offset, str.length);
  while (utf16 < target) {
    const code = str.codePointAt(utf16);
    utf16 += code > 0xffff ? 2 : 1;
    cp += 1;
  }
  return cp;
}

function buildTextMap(nodes) {
  const entries = [];
  const parts = [];
  let cursor = 0;
  for (const node of nodes) {
    const value = node.nodeValue || '';
    const cpLen = Array.from(value).length;
    const inRubyAnnotation = Boolean(node.parentElement?.closest('rt, rp'));
    entries.push({
      node,
      start: cursor,
      end: cursor + cpLen,
      cpLen,
      inRubyAnnotation,
    });
    parts.push(value);
    cursor += cpLen;
  }
  return {
    entries,
    plain: parts.join(''),
    plainArr: Array.from(parts.join('')),
  };
}

function buildBaseTextMap(entries) {
  const baseEntries = [];
  const parts = [];
  let cursor = 0;
  for (const entry of entries) {
    if (entry.inRubyAnnotation) {
      continue;
    }
    baseEntries.push({
      fullStart: entry.start,
      fullEnd: entry.end,
      baseStart: cursor,
      baseEnd: cursor + entry.cpLen,
      node: entry.node,
    });
    parts.push(entry.node.nodeValue || '');
    cursor += entry.cpLen;
  }
  return {
    baseEntries,
    basePlain: parts.join(''),
  };
}

function resolveAnchorRanges(fullMap, anchors) {
  if (!Array.isArray(anchors) || !anchors.length) {
    return [];
  }
  const { entries, plain, plainArr } = fullMap;
  const baseMap = buildBaseTextMap(entries);
  const ranges = [];

  for (const anchor of anchors) {
    if (!anchor || typeof anchor !== 'object') {
      continue;
    }
    const start = Number.isInteger(anchor.start) ? anchor.start : null;
    const end = Number.isInteger(anchor.end) ? anchor.end : null;
    const quote = typeof anchor.quote === 'string' ? anchor.quote : '';

    if (start !== null && end !== null && start >= 0 && end > start && end <= plainArr.length) {
      const sliced = plainArr.slice(start, end).join('');
      if (!quote || sliced === quote) {
        ranges.push({ start, end });
        continue;
      }
    }

    if (quote) {
      const idx = plain.indexOf(quote);
      if (idx !== -1) {
        const cpStart = utf16ToCpOffset(plain, idx);
        const cpEnd = cpStart + Array.from(quote).length;
        ranges.push({ start: cpStart, end: cpEnd });
        continue;
      }

      const baseIdx = baseMap.basePlain.indexOf(quote);
      if (baseIdx !== -1) {
        const baseStart = utf16ToCpOffset(baseMap.basePlain, baseIdx);
        const baseEnd = baseStart + Array.from(quote).length;
        for (const seg of baseMap.baseEntries) {
          const ovStart = Math.max(baseStart, seg.baseStart);
          const ovEnd = Math.min(baseEnd, seg.baseEnd);
          if (ovEnd > ovStart) {
            ranges.push({
              start: seg.fullStart + (ovStart - seg.baseStart),
              end: seg.fullStart + (ovEnd - seg.baseStart),
            });
          }
        }
      }
    }
  }

  if (!ranges.length) {
    return [];
  }
  ranges.sort((a, b) => a.start - b.start || a.end - b.end);
  const merged = [ranges[0]];
  for (let i = 1; i < ranges.length; i += 1) {
    const prev = merged[merged.length - 1];
    const curr = ranges[i];
    if (curr.start <= prev.end) {
      prev.end = Math.max(prev.end, curr.end);
    } else {
      merged.push({ ...curr });
    }
  }
  return merged;
}

export function underlineAnchors(root, anchors = []) {
  if (!root || !Array.isArray(anchors) || !anchors.length) {
    return [];
  }
  const nodes = textNodesUnder(root);
  if (!nodes.length) {
    return [];
  }
  const fullMap = buildTextMap(nodes);
  const ranges = resolveAnchorRanges(fullMap, anchors);
  if (!ranges.length) {
    return [];
  }

  const createdMarks = [];
  for (let eIdx = fullMap.entries.length - 1; eIdx >= 0; eIdx -= 1) {
    const entry = fullMap.entries[eIdx];
    // Never insert <mark> inside <rt> or <rp>, which breaks ruby layout.
    if (entry.inRubyAnnotation) {
      continue;
    }

    const overlaps = [];
    for (const r of ranges) {
      const ovStart = Math.max(r.start, entry.start);
      const ovEnd = Math.min(r.end, entry.end);
      if (ovEnd > ovStart) {
        overlaps.push({
          localStart: ovStart - entry.start,
          localEnd: ovEnd - entry.start,
        });
      }
    }
    if (!overlaps.length) {
      continue;
    }

    overlaps.sort((a, b) => b.localStart - a.localStart);
    let currentNode = entry.node;
    for (const ov of overlaps) {
      const value = currentNode.nodeValue || '';
      const utfStart = cpToUtf16Index(value, ov.localStart);
      const utfEnd = cpToUtf16Index(value, ov.localEnd);
      if (utfEnd <= utfStart) {
        continue;
      }
      if (utfEnd < value.length) {
        currentNode.splitText(utfEnd);
      }
      const middleNode = utfStart > 0 ? currentNode.splitText(utfStart) : currentNode;
      const mark = document.createElement('mark');
      mark.className = 'atomicSourceMark';
      middleNode.parentNode.insertBefore(mark, middleNode);
      mark.appendChild(middleNode);
      createdMarks.push(mark);
    }
  }

  return createdMarks.reverse();
}

export function centerSource(scrollHost, anchors = []) {
  if (!scrollHost) {
    return;
  }
  const target = scrollHost.querySelector('.atomicSourceMark');
  if (!target) {
    return;
  }
  const hostRect = scrollHost.getBoundingClientRect();
  const targetRect = target.getBoundingClientRect();
  if (!hostRect.height) {
    target.scrollIntoView({ block: 'center', behavior: 'smooth' });
    return;
  }
  const offset = targetRect.top - hostRect.top + scrollHost.scrollTop - hostRect.height * 0.35;
  scrollHost.scrollTop = Math.max(0, offset);
}

export async function renderSourcePanel(chunk) {
  const wrapper = document.createElement('div');
  wrapper.className = 'chunkSourceBox';

  const sourceTitle = chunk?.introduction?.title || chunk?.source_title || '对应课程讲解原文';
  const titleEl = document.createElement('div');
  titleEl.className = 'chunkSourceTitle';
  titleEl.textContent = sourceTitle;

  const contentEl = document.createElement('div');
  contentEl.className = 'lessonContent memoryChunkSummary';
  const sourceHtml = chunk?.content_html || chunk?.source_html || chunk?.introduction?.html || chunk?.html || '';
  await setRichHtml(contentEl, sourceHtml, { literalMath: false });
  underlineAnchors(contentEl, chunk?.anchors || []);

  wrapper.append(titleEl, contentEl);
  return wrapper;
}

export async function renderMemoryChunkView(container, chunk, options = {}) {
  if (!container) {
    return;
  }
  const {
    actionLabel = '我已记住，开始语法填空',
    onContinue = null,
    busy = false,
  } = options;

  container.replaceChildren();

  const card = document.createElement('section');
  card.className = 'panelCard';

  const header = document.createElement('div');
  header.className = 'questionCardHeader';
  header.innerHTML = `
    <div>
      <p class="sectionEyebrow">知识组块学习 · Memory Chunk</p>
      <h2 class="cardTitle">${escapeHtml(chunk?.title || '语法知识组块')}</h2>
    </div>
    <span class="pill pill--accent">先理解要点，再进入填空检索</span>
  `;

  const split = document.createElement('div');
  split.className = 'chunkSplitLayout';

  const sourcePanel = await renderSourcePanel(chunk);

  const rightCard = document.createElement('div');
  rightCard.className = 'chunkPointsCard';

  const pointsHeader = document.createElement('div');
  pointsHeader.className = 'chunkSourceTitle';
  pointsHeader.textContent = '核心语法要点';
  rightCard.appendChild(pointsHeader);

  const points = Array.isArray(chunk?.points) ? chunk.points : [];
  if (points.length) {
    const list = document.createElement('ol');
    list.className = 'chunkPointList';
    for (const point of points) {
      const li = document.createElement('li');
      li.className = 'chunkPointItem memoryPointText';
      await setRichText(li, point?.html || point?.text || point?.title || String(point || ''), { literalMath: false });
      list.appendChild(li);
    }
    rightCard.appendChild(list);
  } else if (!chunk?.editor_html) {
    const fallbackNote = document.createElement('p');
    fallbackNote.className = 'mutedText';
    fallbackNote.textContent = '请重点阅读左侧高亮标记的语法规则与例句结构。';
    rightCard.appendChild(fallbackNote);
  }

  if (chunk?.editor_html) {
    const summary = document.createElement('div');
    summary.className = 'lessonContent chunkEditorSummary';
    await setRichHtml(summary, chunk.editor_html, { literalMath: false });
    rightCard.appendChild(summary);
  }

  const mnemonicHtml = chunk?.editor_mnemonic_html ?? (chunk?.mnemonic_html || chunk?.mnemonic?.html || chunk?.mnemonic?.text);
  if (mnemonicHtml) {
    const mnemonicBox = document.createElement('div');
    mnemonicBox.className = 'chunkMnemonicBox lessonContent';
    const label = document.createElement('div');
    label.innerHTML = '<strong>记忆线索：</strong>';
    const body = document.createElement('div');
    await setRichText(body, mnemonicHtml, { literalMath: false });
    mnemonicBox.append(label, body);
    rightCard.appendChild(mnemonicBox);
  }

  const actionRow = document.createElement('div');
  actionRow.className = 'actionRow';
  const continueBtn = document.createElement('button');
  continueBtn.type = 'button';
  continueBtn.className = 'btn btn--primary';
  continueBtn.disabled = Boolean(busy);
  continueBtn.textContent = actionLabel;
  if (typeof onContinue === 'function') {
    continueBtn.addEventListener('click', () => onContinue(continueBtn));
  }
  actionRow.appendChild(continueBtn);
  rightCard.appendChild(actionRow);

  split.append(sourcePanel, rightCard);
  card.append(header, split);
  container.appendChild(card);

  requestAnimationFrame(() => centerSource(sourcePanel, chunk?.anchors || []));
}

export async function openChunkPeekModal(modalHost, chunk, { revealTitle = false } = {}) {
  if (!modalHost || !chunk) {
    return;
  }
  modalHost.replaceChildren();
  modalHost.classList.remove('hidden');
  modalHost.setAttribute('aria-hidden', 'false');

  const dialog = document.createElement('div');
  dialog.className = 'modalDialog';
  dialog.setAttribute('role', 'dialog');
  dialog.setAttribute('aria-modal', 'true');

  const header = document.createElement('div');
  header.className = 'modalHeader';
  header.innerHTML = revealTitle
    ? `<h3 class="cardTitle" style="margin:0;">原讲义组块 · ${escapeHtml(chunk.title || '语法讲解')}</h3>`
    : '<h3 class="cardTitle" style="margin:0;">相关讲义参考</h3>';

  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'btn btn--secondary btn--sm';
  closeBtn.textContent = '关闭';
  const closeModal = () => {
    modalHost.classList.add('hidden');
    modalHost.setAttribute('aria-hidden', 'true');
    modalHost.replaceChildren();
  };
  closeBtn.addEventListener('click', closeModal);
  header.appendChild(closeBtn);

  const body = document.createElement('div');
  body.className = 'modalBody';
  const sourcePanel = await renderSourcePanel(chunk);
  body.appendChild(sourcePanel);

  dialog.append(header, body);
  modalHost.appendChild(dialog);

  const onBackdropClick = (event) => {
    if (event.target === modalHost) {
      closeModal();
      modalHost.removeEventListener('click', onBackdropClick);
    }
  };
  modalHost.addEventListener('click', onBackdropClick);

  const onEsc = (event) => {
    if (event.key === 'Escape') {
      closeModal();
      document.removeEventListener('keydown', onEsc);
    }
  };
  document.addEventListener('keydown', onEsc);

  requestAnimationFrame(() => centerSource(sourcePanel, chunk.anchors || []));
}
