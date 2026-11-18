import { api, newRequestId } from './api.js';
import { sanitizeHtmlFragment, setRichHtml } from './math-render.js';

const BLANK = /\{\{blank:([A-Za-z][A-Za-z0-9_-]{0,39})\}\}/g;
const viewId = newRequestId('edit-view');
const richFieldLabels = { html: '正文', mnemonic_html: '记忆线索' };

function addBlankBadges(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) {
    if (walker.currentNode.nodeValue.includes('{{blank:')) nodes.push(walker.currentNode);
  }
  let position = 0;
  for (const node of nodes) {
    const raw = node.nodeValue;
    const fragment = document.createDocumentFragment();
    let offset = 0;
    for (const match of raw.matchAll(BLANK)) {
      fragment.append(raw.slice(offset, match.index));
      const badge = document.createElement('span');
      badge.className = 'pageEditorBlank';
      badge.contentEditable = 'false';
      badge.dataset.editBlank = match[1];
      badge.textContent = `第 ${++position} 空`;
      fragment.appendChild(badge);
      offset = match.index + match[0].length;
    }
    if (offset) {
      fragment.append(raw.slice(offset));
      node.replaceWith(fragment);
    }
  }
}

function setEditable(control, html) {
  control.replaceChildren(sanitizeHtmlFragment(html));
  addBlankBadges(control);
}

function getEditable(control) {
  const normalized = control.cloneNode(true);
  for (const badge of normalized.querySelectorAll('[data-edit-blank]')) {
    badge.replaceWith(document.createTextNode(`{{blank:${badge.dataset.editBlank}}}`));
  }
  // Browser formatting commands may emit inline styles, which the page format does not use.
  for (const node of normalized.querySelectorAll('[style]')) node.removeAttribute('style');
  return normalized.innerHTML;
}

function addFormatting(toolbar, editable) {
  const commands = [
    ['加粗', 'bold'], ['斜体', 'italic'], ['项目列表', 'insertUnorderedList'], ['编号列表', 'insertOrderedList'],
  ];
  for (const [label, command] of commands) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn--ghost btn--sm';
    button.textContent = label;
    button.addEventListener('mousedown', (event) => event.preventDefault());
    button.addEventListener('click', () => {
      editable.focus();
      document.execCommand(command, false);
    });
    toolbar.appendChild(button);
  }
}

export function createPageEditor({ showToast }) {
  let session = null;
  let sequence = 0;

  function close() {
    const active = session;
    if (!active) return;
    session = null;
    active.controller.abort();
    active.dialog.close();
    active.dialog.remove();
    if (active.token) api.closePageEdit(active.token).catch(() => {});
  }

  async function open(launcher, target, onSaved, label) {
    close();
    const dialog = document.createElement('dialog');
    dialog.className = 'modalDialog pageEditorDialog';
    dialog.setAttribute('aria-labelledby', 'pageEditorTitle');
    dialog.innerHTML = `
      <div class="modalHeader">
        <h2 class="cardTitle" id="pageEditorTitle">编辑本页</h2>
        <button type="button" class="btn btn--ghost btn--sm" data-edit="close">关闭</button>
      </div>
      <div class="modalBody pageEditorBody">
        <p class="mutedText" data-edit="label"></p>
        <p class="pageEditorNotice" data-edit="notice" hidden></p>
        <div class="pageEditorFields" data-edit="fields"></div>
        <details class="pageEditorAi" data-edit="ai" hidden>
          <summary>让 AI 修改本页</summary>
          <label for="pageEditorInstruction">修改要求</label>
          <textarea id="pageEditorInstruction" rows="2" maxlength="1500" placeholder="例如，缩短这段讲解并保留日语例句"></textarea>
          <button type="button" class="btn btn--secondary btn--sm" data-edit="suggest">生成建议</button>
        </details>
        <section class="pageEditorPreview" data-edit="preview" aria-label="内容预览" hidden></section>
        <p class="pageEditorStatus" data-edit="status" role="status"></p>
      </div>
      <div class="pageEditorFooter">
        <button type="button" class="btn btn--ghost" data-edit="preview-button" disabled>预览</button>
        <button type="button" class="btn btn--ghost" data-edit="discard" hidden>放弃建议</button>
        <button type="button" class="btn btn--secondary" data-edit="adopt" hidden>采用 AI 建议</button>
        <button type="button" class="btn btn--primary" data-edit="save" disabled>保存</button>
      </div>`;
    const part = (name) => dialog.querySelector(`[data-edit="${name}"]`);
    const active = { dialog, controller: new AbortController(), token: null };
    session = active;
    const isCurrent = () => session === active && launcher.isConnected;
    part('label').textContent = label;
    part('status').textContent = '正在读取当前页…';
    part('close').addEventListener('click', close);
    dialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      if (!part('close').disabled) close();
    });
    document.body.appendChild(dialog);
    dialog.showModal();

    let page;
    try {
      page = await api.openPageEdit({ view_id: viewId, sequence: ++sequence, ...target }, active.controller.signal);
    } catch (error) {
      if (isCurrent()) part('status').textContent = error.message || '无法打开编辑器';
      return;
    }
    if (!isCurrent()) {
      api.closePageEdit(page.token).catch(() => {});
      return;
    }
    active.token = page.token;
    if (page.updated_elsewhere) {
      const notice = part('notice');
      notice.textContent = '这次展示使用较早的版本。保存时会以你眼前的内容为基础。';
      notice.hidden = false;
    }
    const revision = page.revision;
    const controls = new Map();
    for (const [key, value] of Object.entries(page.fields)) {
      const group = document.createElement('div');
      group.className = 'pageEditorField';
      const id = `pageEditorField-${key}`;
      if (key === 'title') {
        const fieldLabel = document.createElement('label');
        const input = document.createElement('input');
        fieldLabel.htmlFor = id;
        fieldLabel.textContent = '标题';
        input.id = id;
        input.value = value;
        group.append(fieldLabel, input);
        controls.set(key, { get: () => input.value, set: (content) => { input.value = content; } });
      } else {
        const fieldLabel = document.createElement('span');
        fieldLabel.id = `${id}-label`;
        fieldLabel.textContent = richFieldLabels[key];
        const toolbar = document.createElement('div');
        toolbar.className = 'pageEditorFormatting';
        const editable = document.createElement('div');
        editable.id = id;
        editable.className = 'pageEditorEditable lessonContent';
        editable.contentEditable = 'true';
        editable.setAttribute('role', 'textbox');
        editable.setAttribute('aria-multiline', 'true');
        editable.setAttribute('aria-labelledby', fieldLabel.id);
        editable.addEventListener('paste', (event) => {
          event.preventDefault();
          document.execCommand('insertText', false, event.clipboardData?.getData('text/plain') || '');
        });
        editable.addEventListener('drop', (event) => event.preventDefault());
        setEditable(editable, value);
        addFormatting(toolbar, editable);
        group.append(fieldLabel, toolbar, editable);
        controls.set(key, { get: () => getEditable(editable), set: (content) => setEditable(editable, content) });
      }
      part('fields').appendChild(group);
    }

    let suggestion = null;
    let busy = false;
    const status = part('status');
    const preview = part('preview');
    const suggest = part('suggest');
    const save = part('save');
    const adopt = part('adopt');
    const discard = part('discard');
    const instruction = dialog.querySelector('#pageEditorInstruction');
    const readFields = () => Object.fromEntries([...controls].map(([key, control]) => [key, control.get()]));

    const renderPreview = async (fields, titleText) => {
      const content = document.createElement('div');
      const heading = document.createElement('h3');
      heading.className = 'cardTitle';
      heading.textContent = titleText;
      content.appendChild(heading);
      if (fields.title !== undefined) {
        const title = document.createElement('p');
        title.textContent = fields.title;
        content.appendChild(title);
      }
      for (const key of ['html', 'mnemonic_html']) {
        if (!fields[key]) continue;
        const section = document.createElement('div');
        section.className = 'lessonContent';
        await setRichHtml(section, fields[key]);
        addBlankBadges(section);
        content.appendChild(section);
      }
      if (isCurrent()) {
        preview.replaceChildren(content);
        preview.hidden = false;
      }
    };

    const setBusy = (value, saving = false) => {
      busy = value;
      part('fields').inert = saving;
      save.disabled = value || Boolean(suggestion);
      suggest.disabled = value;
      adopt.disabled = value;
      discard.disabled = value;
      part('close').disabled = saving;
      part('preview-button').disabled = value || Boolean(suggestion);
    };

    part('ai').hidden = false;
    status.textContent = target.kind === 'question' ? '填空位置及判分答案保留。' : '';
    setBusy(false);

    part('preview-button').addEventListener('click', async () => {
      await renderPreview(readFields(), '预览');
      preview.scrollIntoView({ block: 'nearest' });
    });

    suggest.addEventListener('click', async () => {
      const request = instruction.value.trim();
      if (!request) {
        instruction.focus();
        return;
      }
      setBusy(true);
      status.textContent = '正在根据已保存的本页内容生成建议…';
      try {
        const result = await api.suggestPageEdit({ token: active.token, revision, instruction: request }, active.controller.signal);
        if (!isCurrent()) return;
        await renderPreview(result.fields, 'AI 建议');
        if (!isCurrent()) return;
        suggestion = result.fields;
        adopt.hidden = false;
        discard.hidden = false;
        status.textContent = '采用建议会把它载入编辑器。还需点击保存才会更新页面。';
        preview.scrollIntoView({ block: 'nearest' });
      } catch (error) {
        if (isCurrent()) status.textContent = error.message || '未能生成建议';
      } finally {
        if (isCurrent()) setBusy(false);
      }
    });

    const clearSuggestion = () => {
      suggestion = null;
      adopt.hidden = true;
      discard.hidden = true;
      preview.hidden = true;
      setBusy(false);
    };
    adopt.addEventListener('click', () => {
      if (!suggestion) return;
      for (const [key, control] of controls) control.set(suggestion[key]);
      clearSuggestion();
      status.textContent = '已将 AI 建议载入编辑器。';
    });
    discard.addEventListener('click', () => {
      clearSuggestion();
      status.textContent = '';
    });

    save.addEventListener('click', async () => {
      if (busy || suggestion) return;
      setBusy(true, true);
      status.textContent = '正在保存…';
      try {
        const result = await api.savePageEdit({ token: active.token, revision, fields: readFields() }, active.controller.signal);
        if (!isCurrent()) return;
        let focusTarget;
        try {
          focusTarget = await onSaved(result.fields);
          showToast?.('已保存本页');
        } catch {
          showToast?.('本页已保存。请刷新以查看更新。', { error: true });
        }
        if (session === active) close();
        if (focusTarget?.isConnected) focusTarget.focus({ preventScroll: true });
      } catch (error) {
        if (isCurrent()) {
          const message = error.message || '未能保存本页';
          status.textContent = error.status === 409 ? `${message} 请保留草稿后重新打开此页编辑器。` : message;
        }
      } finally {
        if (isCurrent()) setBusy(false);
      }
    });
  }

  return {
    close,
    mount(parent, target, onSaved, { label = '编辑本页', context = '' } = {}) {
      const button = document.createElement('button');
      const mountedRoute = window.location.hash;
      button.type = 'button';
      button.className = 'btn btn--secondary btn--sm';
      button.textContent = label;
      button.addEventListener('click', () => {
        if (window.location.hash === mountedRoute) open(button, target, onSaved, context);
      });
      parent.appendChild(button);
      return button;
    },
  };
}
