let katexPromise = null;
let mermaidPromise = null;

export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function isSafeRelativeOrDataUrl(rawUrl, allowImageData = false) {
  const trimmed = String(rawUrl || '').trim();
  if (!trimmed) {
    return false;
  }
  if (/^(javascript|vbscript|file):/i.test(trimmed)) {
    return false;
  }
  if (/^data:/i.test(trimmed)) {
    return allowImageData && /^data:image\/(png|jpeg|jpg|gif|webp|svg\+xml);/i.test(trimmed);
  }
  if (/^(https?:)?\/\//i.test(trimmed)) {
    return false;
  }
  return trimmed.startsWith('/') || trimmed.startsWith('./') || trimmed.startsWith('../') || trimmed.startsWith('#') || !trimmed.includes(':');
}

const FORBIDDEN_ELEMENTS = 'script, iframe, object, embed, link, meta, base, style, noscript, template';
const ALLOWED_HTML_TAGS = new Set([
  'a', 'abbr', 'b', 'blockquote', 'br', 'caption', 'code', 'col', 'colgroup',
  'dd', 'del', 'details', 'dfn', 'div', 'dl', 'dt', 'em', 'figcaption', 'figure',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'ins', 'kbd', 'li',
  'mark', 'ol', 'p', 'pre', 'q', 'rp', 'rt', 'ruby', 's', 'samp', 'section',
  'small', 'span', 'strong', 'sub', 'summary', 'sup', 'table', 'tbody', 'td',
  'tfoot', 'th', 'thead', 'tr', 'u', 'ul', 'var', 'wbr',
]);

export function sanitizeHtmlFragment(html) {
  const template = document.createElement('template');
  template.innerHTML = String(html ?? '');

  for (const el of template.content.querySelectorAll(FORBIDDEN_ELEMENTS)) {
    el.remove();
  }

  const all = [...template.content.querySelectorAll('*')];
  for (const el of all) {
    const tag = el.tagName.toLowerCase();
    const isSvg = el.namespaceURI === 'http://www.w3.org/2000/svg';
    const isMath = el.namespaceURI === 'http://www.w3.org/1998/Math/MathML';

    if (!isSvg && !isMath && !ALLOWED_HTML_TAGS.has(tag)) {
      const span = document.createElement('span');
      span.replaceChildren(...el.childNodes);
      el.replaceWith(span);
      continue;
    }

    for (const attr of [...el.attributes]) {
      const name = attr.name.toLowerCase();
      const val = attr.value;
      if (name.startsWith('on') || name === 'srcdoc') {
        el.removeAttribute(attr.name);
        continue;
      }
      if (name === 'style' && /url\s*\(|@import|expression\s*\(/i.test(val)) {
        el.removeAttribute(attr.name);
        continue;
      }
      if (name === 'href' || name === 'xlink:href') {
        if (!isSafeRelativeOrDataUrl(val, false)) {
          el.removeAttribute(attr.name);
        } else if (val.startsWith('/') && !isSvg) {
          el.setAttribute('rel', 'noopener noreferrer');
        }
        continue;
      }
      if (name === 'src') {
        if (!isSafeRelativeOrDataUrl(val, true)) {
          el.removeAttribute(attr.name);
        }
      }
    }
  }

  return template.content;
}

async function loadKatex() {
  if (!katexPromise) {
    katexPromise = import('./vendor/katex/katex.js').then((mod) => mod.default || mod).catch(() => null);
  }
  return katexPromise;
}

async function loadMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import('./vendor/mermaid/index.js').catch(() => null);
  }
  return mermaidPromise;
}

const MATH_DELIMITER_RE = /\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$(?!\s)(?:\\.|[^$\\\n])+?(?<!\s)\$/;

export async function renderMathInElement(root) {
  if (!root || !MATH_DELIMITER_RE.test(root.textContent || '')) {
    return;
  }
  const katex = await loadKatex();
  if (!katex || typeof katex.render !== 'function') {
    return;
  }

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent) {
        return NodeFilter.FILTER_REJECT;
      }
      if (parent.closest('script, style, textarea, code, pre, svg, math, .katex, ruby, rt, rp, .mermaid-source, .mermaid-output, .inlineBlankWrap, [data-tex], .no-math')) {
        return NodeFilter.FILTER_REJECT;
      }
      return MATH_DELIMITER_RE.test(node.nodeValue || '') ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
    },
  });

  const nodes = [];
  let cur = walker.nextNode();
  while (cur) {
    nodes.push(cur);
    cur = walker.nextNode();
  }

  const tokenRe = /(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$(?!\s)(?:\\.|[^$\\\n])+?(?<!\s)\$)/g;
  for (const node of nodes) {
    const raw = node.nodeValue || '';
    const parts = raw.split(tokenRe);
    if (parts.length <= 1) {
      continue;
    }
    const frag = document.createDocumentFragment();
    for (const part of parts) {
      if (!part) {
        continue;
      }
      let tex = null;
      let displayMode = false;
      if (part.startsWith('$$') && part.endsWith('$$') && part.length > 4) {
        tex = part.slice(2, -2);
        displayMode = true;
      } else if (part.startsWith('\\[') && part.endsWith('\\]') && part.length > 4) {
        tex = part.slice(2, -2);
        displayMode = true;
      } else if (part.startsWith('\\(') && part.endsWith('\\)') && part.length > 4) {
        tex = part.slice(2, -2);
      } else if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
        tex = part.slice(1, -1);
      }
      if (tex === null) {
        frag.appendChild(document.createTextNode(part));
        continue;
      }
      const holder = document.createElement(displayMode ? 'div' : 'span');
      holder.dataset.tex = tex;
      try {
        katex.render(tex, holder, { displayMode, throwOnError: false, strict: 'ignore' });
      } catch {
        holder.textContent = part;
      }
      frag.appendChild(holder);
    }
    node.replaceWith(frag);
  }
}

export function prepareLiteralMath(root) {
  if (!root) {
    return;
  }
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent) {
        return NodeFilter.FILTER_REJECT;
      }
      if (parent.closest('mjx-container, .katex, math, svg, code, pre, a, ruby, rt, rp, [data-tex], .mermaid-source, .mermaid-output, .inlineBlankWrap')) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const nodes = [];
  let cur = walker.nextNode();
  while (cur) {
    nodes.push(cur);
    cur = walker.nextNode();
  }
  for (const node of nodes) {
    if (typeof node.nodeValue === 'string' && node.nodeValue.includes('\\(')) {
      node.nodeValue = node.nodeValue;
    }
  }
}

export async function mountMermaidDiagrams(root) {
  if (!root) {
    return;
  }
  const fencedMermaid = root.querySelectorAll('pre > code.language-mermaid, pre > code.lang-mermaid');
  for (const codeEl of fencedMermaid) {
    const pre = codeEl.parentElement;
    if (!pre || pre.closest('.local-mermaid')) {
      continue;
    }
    const wrapper = document.createElement('div');
    wrapper.className = 'local-mermaid';
    const output = document.createElement('div');
    output.className = 'mermaid-output';
    const newPre = document.createElement('pre');
    const newCode = document.createElement('code');
    newCode.className = 'mermaid-source';
    newCode.textContent = codeEl.textContent || '';
    newPre.appendChild(newCode);
    wrapper.append(output, newPre);
    pre.replaceWith(wrapper);
  }

  const targets = root.querySelectorAll('.local-mermaid');
  if (!targets.length) {
    return;
  }
  const mod = await loadMermaid();
  if (mod && typeof mod.mountMermaid === 'function') {
    await mod.mountMermaid(root);
  }
}

export async function enhanceContent(root, { literalMath = false } = {}) {
  if (!root) {
    return;
  }
  if (literalMath) {
    prepareLiteralMath(root);
  }
  await renderMathInElement(root);
  await mountMermaidDiagrams(root);
}

export async function setRichHtml(container, html, options = {}) {
  if (!container) {
    return;
  }
  const fragment = sanitizeHtmlFragment(html);
  container.replaceChildren(fragment);
  await enhanceContent(container, options);
}

const RICH_HTML_TAG_RE = /<\/?(?:p|div|span|ruby|rt|rp|mark|ul|ol|li|pre|code|blockquote|table|thead|tbody|tr|th|td|details|summary|strong|em|br|a|img|h[1-6]|b|i|u)\b/i;

export async function setRichText(container, text, options = { literalMath: false }) {
  if (!container) {
    return;
  }
  const raw = String(text ?? '');
  if (RICH_HTML_TAG_RE.test(raw)) {
    await setRichHtml(container, raw, options);
    return;
  }
  container.textContent = raw;
  await enhanceContent(container, options);
}
