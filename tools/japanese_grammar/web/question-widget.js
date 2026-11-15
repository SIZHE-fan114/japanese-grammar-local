import { escapeHtml, setRichHtml, setRichText } from './math-render.js';
import {
  containsLatinLetters,
  convertRomajiToHiragana,
  inspectRomajiPreview,
} from './romaji.js';

const ROMAJI_LIVE_STORAGE_KEY = 'grasp-jp-romaji-live-convert';

export const FILL_BLANK_HINT =
  '语法填空：可直接填入日语假名、汉字，或直接填入罗马音（如 no、wa、da、takanakatta 等均可判题）';

function isLiveRomajiStored() {
  try {
    return localStorage.getItem(ROMAJI_LIVE_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function setLiveRomajiStored(enabled) {
  try {
    localStorage.setItem(ROMAJI_LIVE_STORAGE_KEY, enabled ? '1' : '0');
  } catch {
    // Ignore storage quota / privacy restrictions cleanly.
  }
}

const BLANK_MARKER_RE = /\{\{blank:([A-Za-z][A-Za-z0-9_-]{0,39})\}\}/g;

export function isStructuredInteraction(question) {
  const kind = question?.interaction?.type;
  return Boolean(kind && kind !== 'text');
}

export function visualCharUnits(text) {
  let units = 0;
  for (const ch of String(text || '')) {
    units += /[\u3000-\u9fff\uff00-\uffef]/.test(ch) ? 2 : 1;
  }
  return units;
}

export function parseInitialAnswer(rawAnswer, interaction) {
  const raw = typeof rawAnswer === 'string' ? rawAnswer.trim() : '';
  if (!raw) {
    return null;
  }
  if (!interaction || interaction.type === 'text') {
    return rawAnswer;
  }
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

function resolveBlankVerdictMap(question, feedback) {
  const map = new Map();
  const direct = feedback?.blank_results;
  if (direct && typeof direct === 'object') {
    for (const [id, val] of Object.entries(direct)) {
      if (typeof val === 'boolean') {
        map.set(String(id), val);
      }
    }
  }
  const choiceFeedbackItems =
    feedback?.choice_feedback?.items ||
    question?.choice_feedback?.items ||
    [];
  if (Array.isArray(choiceFeedbackItems)) {
    for (const item of choiceFeedbackItems) {
      if (item && item.id !== undefined && typeof item.correct === 'boolean') {
        map.set(String(item.id), item.correct);
      }
    }
  }
  return map;
}

export async function renderAnswerValue(container, answer, interaction) {
  if (!container) {
    return;
  }
  if (answer === undefined || answer === null || answer === '') {
    container.textContent = '（未作答）';
    return;
  }
  const kind = interaction?.type || 'text';
  if (kind === 'text') {
    await setRichText(container, String(answer), { literalMath: false });
    return;
  }

  let parsed = typeof answer === 'string' ? parseInitialAnswer(answer, interaction) : answer;
  if (kind === 'fill_blank') {
    const map = parsed?.values && typeof parsed.values === 'object' ? parsed.values : parsed;
    const blanks = Array.isArray(interaction?.blanks) ? interaction.blanks : [];
    if (map && typeof map === 'object') {
      const list = document.createElement('div');
      list.style.display = 'flex';
      list.style.flexWrap = 'wrap';
      list.style.gap = '6px';
      const orderedKeys = blanks.length ? blanks.map((b) => b.id) : Object.keys(map);
      orderedKeys.forEach((id, idx) => {
        const blankMeta = blanks.find((b) => b.id === id);
        const label = blankMeta?.label || `第${idx + 1}空`;
        const val = map[id] ?? '';
        const chip = document.createElement('span');
        chip.className = 'pill pill--accent';
        chip.textContent = orderedKeys.length > 1 ? `${label}: ${val}` : String(val);
        list.appendChild(chip);
      });
      container.replaceChildren(list);
      return;
    }
  }

  if (kind === 'choice' && parsed && typeof parsed === 'object') {
    const options = Array.isArray(interaction?.options) ? interaction.options : [];
    const selected = Array.isArray(parsed.selected) ? parsed.selected : parsed.selected ? [parsed.selected] : [];
    const labels = selected.map((id) => options.find((o) => o.id === id)?.text || id);
    await setRichText(container, labels.join('、'), { literalMath: false });
    return;
  }

  await setRichText(container, typeof answer === 'string' ? answer : JSON.stringify(answer), { literalMath: false });
}

function applyLiveRomajiToInput(input, { flush = false } = {}) {
  if (!isLiveRomajiStored() || input.disabled) {
    return false;
  }
  const val = input.value;
  if (!containsLatinLetters(val)) {
    return false;
  }
  const selEnd = typeof input.selectionEnd === 'number' ? input.selectionEnd : val.length;
  const head = val.slice(0, selEnd);
  const tail = val.slice(selEnd);
  const convertedHead = convertRomajiToHiragana(head, { flushTerminalN: flush });
  if (convertedHead === head) {
    return false;
  }
  input.value = convertedHead + tail;
  if (document.activeElement === input && typeof input.setSelectionRange === 'function') {
    const nextPos = convertedHead.length;
    input.setSelectionRange(nextPos, nextPos);
  }
  return true;
}

function attachJapaneseImeProtection(input, { onSync, onEnterCommit }) {
  let isComposing = false;
  let lastCompositionEnd = 0;

  input.addEventListener('compositionstart', () => {
    isComposing = true;
  });

  input.addEventListener('compositionend', () => {
    isComposing = false;
    lastCompositionEnd = performance.now();
    applyLiveRomajiToInput(input, { flush: false });
    onSync();
  });

  input.addEventListener('input', (event) => {
    if (!isComposing && !event?.isComposing) {
      const inputType = String(event?.inputType || '');
      if (!inputType.startsWith('delete')) {
        applyLiveRomajiToInput(input, { flush: false });
      }
    }
    onSync();
  });

  input.addEventListener('blur', () => {
    if (!isComposing && applyLiveRomajiToInput(input, { flush: true })) {
      onSync();
    }
  });

  input.addEventListener('keydown', (event) => {
    // Never intercept Enter while IME composition is active (including Safari keyCode 229).
    if (isComposing || event.isComposing || event.keyCode === 229) {
      return;
    }
    if (event.key === 'Enter' && performance.now() - lastCompositionEnd < 30) {
      return;
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      if (applyLiveRomajiToInput(input, { flush: true })) {
        onSync();
      }
      onEnterCommit(event);
    }
  });
}

function createInlineBlankInput(blank, index, totalBlanks, initialValue, disabled, { neutralPlaceholder = false } = {}) {
  const wrap = document.createElement('span');
  wrap.className = 'inlineBlankWrap';

  if (totalBlanks > 1) {
    const idxTag = document.createElement('span');
    idxTag.className = 'inlineBlankIndex';
    idxTag.textContent = String(index + 1);
    wrap.appendChild(idxTag);
  }

  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'inlineBlankInput';
  input.dataset.blankId = blank.id;
  input.lang = 'ja';
  input.autocomplete = 'off';
  input.spellcheck = false;
  input.setAttribute('autocapitalize', 'off');
  input.setAttribute('autocorrect', 'off');
  const neutralLabel = totalBlanks > 1 ? `第 ${index + 1} 空` : '填入日语...';
  const neutralAria = `第 ${index + 1} 空`;
  input.placeholder = neutralPlaceholder ? neutralLabel : (blank.label || '');
  input.setAttribute('aria-label', neutralPlaceholder ? neutralAria : (blank.label || neutralAria));
  input.value = String(initialValue ?? '');
  input.disabled = Boolean(disabled);

  const resize = () => {
    const widthCh = Math.max(8, Math.min(36, visualCharUnits(input.value) + 4));
    input.style.width = `${widthCh}ch`;
  };
  resize();

  wrap.appendChild(input);
  return { wrap, input, resize };
}

export function mountQuestionStemWithBlanks(
  stemContainer,
  question,
  {
    initialValues = null,
    initialAnswer = '',
    disabled = false,
    onChange = null,
    onSubmitShortcut = null,
    feedback = null,
    neutralPlaceholder = false,
  } = {},
) {
  const blanks = Array.isArray(question?.interaction?.blanks) ? question.interaction.blanks : [];
  const blankById = new Map(blanks.map((b, idx) => [b.id, { blank: b, index: idx }]));
  const parsedDraft = parseInitialAnswer(initialAnswer, question?.interaction) || {};
  const sourceValues = initialValues || (parsedDraft?.values && typeof parsedDraft.values === 'object' ? parsedDraft.values : parsedDraft);

  const values = {};
  for (const blank of blanks) {
    values[blank.id] = typeof sourceValues?.[blank.id] === 'string' ? sourceValues[blank.id] : '';
  }

  const inputMap = new Map();
  const mountedIds = new Set();

  if (stemContainer && blanks.length) {
    const walker = document.createTreeWalker(stemContainer, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent) {
          return NodeFilter.FILTER_REJECT;
        }
        if (parent.closest('.katex, code, pre, script, style, ruby, rt, rp, .mermaid-source, .mermaid-output, .inlineBlankWrap')) {
          return NodeFilter.FILTER_REJECT;
        }
        return (node.nodeValue || '').includes('{{blank:') ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });

    const matchedNodes = [];
    let current = walker.nextNode();
    while (current) {
      matchedNodes.push(current);
      current = walker.nextNode();
    }

    for (const textNode of matchedNodes) {
      const raw = textNode.nodeValue || '';
      const regex = new RegExp(BLANK_MARKER_RE.source, 'g');
      let lastIndex = 0;
      let match = regex.exec(raw);
      if (!match) {
        continue;
      }
      const frag = document.createDocumentFragment();
      while (match) {
        if (match.index > lastIndex) {
          frag.appendChild(document.createTextNode(raw.slice(lastIndex, match.index)));
        }
        const blankId = match[1];
        const info = blankById.get(blankId);
        if (info && !mountedIds.has(blankId)) {
          mountedIds.add(blankId);
          const control = createInlineBlankInput(info.blank, info.index, blanks.length, values[blankId], disabled, { neutralPlaceholder });
          inputMap.set(blankId, control);
          frag.appendChild(control.wrap);
        } else {
          frag.appendChild(document.createTextNode(match[0]));
        }
        lastIndex = regex.lastIndex;
        match = regex.exec(raw);
      }
      if (lastIndex < raw.length) {
        frag.appendChild(document.createTextNode(raw.slice(lastIndex)));
      }
      textNode.replaceWith(frag);
    }

    const unmounted = blanks.filter((b) => !mountedIds.has(b.id));
    if (unmounted.length) {
      const grid = document.createElement('div');
      grid.className = 'fallbackBlankGrid';
      for (const blank of unmounted) {
        const info = blankById.get(blank.id);
        const field = document.createElement('div');
        field.className = 'fallbackBlankField';
        const label = document.createElement('label');
        label.textContent = neutralPlaceholder ? `第 ${(info?.index ?? 0) + 1} 空` : (blank.label || `第 ${(info?.index ?? 0) + 1} 空`);
        const control = createInlineBlankInput(blank, info?.index ?? 0, blanks.length, values[blank.id], disabled, { neutralPlaceholder });
        inputMap.set(blank.id, control);
        field.append(label, control.wrap);
        grid.appendChild(field);
      }
      stemContainer.appendChild(grid);
    }
  }

  const orderedControls = blanks.map((b) => inputMap.get(b.id)).filter(Boolean);
  const getPayload = () => {
    const out = {};
    for (const blank of blanks) {
      out[blank.id] = String(values[blank.id] ?? '').trim();
    }
    return out;
  };
  const isValid = () => blanks.length > 0 && blanks.every((b) => {
    const v = String(values[b.id] ?? '').trim();
    return v.length > 0 && v.length <= 2000;
  });
  const getAnswerString = () => JSON.stringify(getPayload());

  for (const blank of blanks) {
    const control = inputMap.get(blank.id);
    if (!control) {
      continue;
    }
    const { input, resize } = control;
    attachJapaneseImeProtection(input, {
      onSync: () => {
        values[blank.id] = input.value;
        resize();
        onChange?.({ answerString: getAnswerString(), valid: isValid(), values: getPayload() });
      },
      onEnterCommit: (event) => {
        if (typeof onSubmitShortcut !== 'function') {
          return;
        }
        event.preventDefault();
        const nextEmpty = orderedControls
          .map((c) => c.input)
          .find((el) => el !== input && !el.disabled && !el.value.trim());
        if (nextEmpty) {
          nextEmpty.focus();
          return;
        }
        onSubmitShortcut();
      },
    });
  }

  const updateFeedback = (fb) => {
    const verdicts = resolveBlankVerdictMap(question, fb);
    for (const blank of blanks) {
      const control = inputMap.get(blank.id);
      if (!control) {
        continue;
      }
      control.input.classList.remove('is-correct', 'is-wrong');
      if (verdicts.has(blank.id)) {
        control.input.classList.add(verdicts.get(blank.id) ? 'is-correct' : 'is-wrong');
      } else if (fb && typeof fb.correct === 'boolean' && blanks.length === 1) {
        control.input.classList.add(fb.correct ? 'is-correct' : 'is-wrong');
      }
    }
  };
  updateFeedback(feedback);

  return {
    getAnswerString,
    isValid,
    focusFirst() {
      const target = orderedControls.find((c) => !c.input.disabled && !c.input.value.trim()) || orderedControls[0];
      target?.input?.focus();
    },
    getControls() {
      return orderedControls.map((c, idx) => ({ blank: blanks[idx], control: c }));
    },
    setBlankValue(blankId, nextVal, { focusInput = true } = {}) {
      const control = inputMap.get(blankId);
      if (!control || control.input.disabled) {
        return;
      }
      control.input.value = String(nextVal ?? '');
      values[blankId] = control.input.value;
      control.resize();
      onChange?.({ answerString: getAnswerString(), valid: isValid(), values: getPayload() });
      if (focusInput) {
        control.input.focus();
      }
    },
    convertExistingToKana({ flush = true } = {}) {
      let changed = false;
      for (const blank of blanks) {
        const control = inputMap.get(blank.id);
        if (!control || control.input.disabled) {
          continue;
        }
        const cur = control.input.value;
        if (!containsLatinLetters(cur)) {
          continue;
        }
        const converted = convertRomajiToHiragana(cur, { flushTerminalN: flush });
        if (converted !== cur) {
          control.input.value = converted;
          values[blank.id] = converted;
          control.resize();
          changed = true;
        }
      }
      if (changed) {
        onChange?.({ answerString: getAnswerString(), valid: isValid(), values: getPayload() });
      }
    },
    updateFeedback,
  };
}

export async function createQuestionInputWidget(
  container,
  question,
  {
    stemContainer = null,
    initialAnswer = '',
    disabled = false,
    onChange = null,
    onSubmitShortcut = null,
    feedback = null,
    neutralPlaceholder = false,
  } = {},
) {
  container.replaceChildren();
  const interaction = question?.interaction || { type: 'text' };
  const kind = interaction.type || 'text';

  if (kind === 'fill_blank') {
    const hintBar = document.createElement('div');
    hintBar.className = 'widgetHint widgetHint--romaji';
    const hintText = document.createElement('span');
    hintText.className = 'widgetHintText';
    hintText.textContent = FILL_BLANK_HINT;
    hintBar.appendChild(hintText);

    let modeToggleBtn = null;
    if (!disabled) {
      modeToggleBtn = document.createElement('button');
      modeToggleBtn.type = 'button';
      modeToggleBtn.className = 'romajiModeToggle';
      hintBar.appendChild(modeToggleBtn);
    }
    container.appendChild(hintBar);

    const previewBar = document.createElement('div');
    previewBar.className = 'romajiPreviewBar hidden';
    container.appendChild(previewBar);

    let targetStem = stemContainer;
    if (!targetStem) {
      targetStem = document.createElement('div');
      targetStem.className = 'questionStem';
      await setRichHtml(targetStem, question?.html || question?.question || '', { literalMath: false });
      container.appendChild(targetStem);
    }

    let stemApi = null;

    const refreshModeBtn = () => {
      if (!modeToggleBtn) {
        return;
      }
      const live = isLiveRomajiStored();
      modeToggleBtn.setAttribute('aria-pressed', String(live));
      modeToggleBtn.classList.toggle('is-active', live);
      modeToggleBtn.textContent = live ? '边打边转假名：开启' : '边打边转假名：关闭（支持直填）';
      modeToggleBtn.title = live
        ? '已开启：键入罗马音时自动实时转为平假名；点击可切换回保留原罗马音字母（两种均可直接判对）'
        : '点击开启后，键入罗马音（如 no / da / takanakatta）会自动实时转为平假名';
    };

    const renderRomajiPreview = (currentValues) => {
      if (disabled || !stemApi) {
        previewBar.classList.add('hidden');
        previewBar.replaceChildren();
        return;
      }
      const blanks = Array.isArray(interaction?.blanks) ? interaction.blanks : [];
      const previews = [];
      blanks.forEach((blank, idx) => {
        const val = currentValues?.[blank.id] ?? '';
        const info = inspectRomajiPreview(val, { includeKanaParticleHints: isLiveRomajiStored() });
        if (info) {
          previews.push({ blank, idx, info });
        }
      });
      if (!previews.length) {
        previewBar.classList.add('hidden');
        previewBar.replaceChildren();
        return;
      }
      previewBar.classList.remove('hidden');
      previewBar.replaceChildren();

      const hasLatinPreview = previews.some((item) => containsLatinLetters(item.info.raw));
      const heading = document.createElement('span');
      heading.className = 'romajiPreviewLabel';
      heading.textContent = hasLatinPreview ? '假名预览：' : '助词切换：';
      previewBar.appendChild(heading);

      for (const item of previews) {
        const group = document.createElement('span');
        group.className = 'romajiPreviewItem';
        const prefix = blanks.length > 1 ? `第${item.idx + 1}空 ` : '';
        const kanaOut = item.info.kana || item.info.partialKana;
        const isLatin = containsLatinLetters(item.info.raw);
        if (kanaOut) {
          const arrowText = document.createElement('span');
          arrowText.textContent = `${prefix}${item.info.raw} → ${kanaOut}`;
          group.appendChild(arrowText);
          if (item.info.kana) {
            const applyBtn = document.createElement('button');
            applyBtn.type = 'button';
            applyBtn.className = 'romajiApplyChip';
            applyBtn.textContent = `填入「${item.info.kana}」`;
            applyBtn.addEventListener('click', () => stemApi.setBlankValue(item.blank.id, item.info.kana));
            group.appendChild(applyBtn);
          }
        } else {
          const rawText = document.createElement('span');
          rawText.textContent = `${prefix}${item.info.raw}`;
          group.appendChild(rawText);
        }

        for (const alt of item.info.particleAlternatives) {
          const altBtn = document.createElement('button');
          altBtn.type = 'button';
          altBtn.className = 'romajiApplyChip romajiApplyChip--particle';
          altBtn.textContent = `转为${alt.label}`;
          altBtn.addEventListener('click', () => stemApi.setBlankValue(item.blank.id, alt.kana));
          group.appendChild(altBtn);
        }

        if (isLatin) {
          const directNote = document.createElement('span');
          directNote.className = 'romajiPreviewNote';
          directNote.textContent = '（也可直接提交罗马音）';
          group.appendChild(directNote);
        }
        previewBar.appendChild(group);
      }
    };

    stemApi = mountQuestionStemWithBlanks(targetStem, question, {
      initialAnswer,
      disabled,
      neutralPlaceholder,
      feedback,
      onChange: (payload) => {
        renderRomajiPreview(payload?.values || {});
        onChange?.(payload);
      },
      onSubmitShortcut,
    });

    if (modeToggleBtn) {
      const onModeBroadcast = () => {
        if (!modeToggleBtn.isConnected) {
          window.removeEventListener('grasp-romaji-mode-change', onModeBroadcast);
          return;
        }
        refreshModeBtn();
      };
      refreshModeBtn();
      modeToggleBtn.addEventListener('click', () => {
        const next = !isLiveRomajiStored();
        setLiveRomajiStored(next);
        refreshModeBtn();
        if (next) {
          stemApi.convertExistingToKana({ flush: false });
        }
        window.dispatchEvent(new CustomEvent('grasp-romaji-mode-change'));
        stemApi.focusFirst();
      });
      window.addEventListener('grasp-romaji-mode-change', onModeBroadcast, { passive: true });
    }

    const parsedInit = parseInitialAnswer(initialAnswer, interaction) || {};
    const initValues = parsedInit?.values && typeof parsedInit.values === 'object' ? parsedInit.values : parsedInit;
    renderRomajiPreview(initValues);

    return {
      getAnswerString: stemApi.getAnswerString,
      isValid: stemApi.isValid,
      focus: stemApi.focusFirst,
      updateFeedback: stemApi.updateFeedback,
    };
  }

  if (kind === 'choice') {
    const multiple = Boolean(interaction.multiple);
    const parsed = parseInitialAnswer(initialAnswer, interaction);
    const selected = new Set(
      multiple
        ? (Array.isArray(parsed?.selected) ? parsed.selected : [])
        : (typeof parsed?.selected === 'string' ? [parsed.selected] : []),
    );
    const list = document.createElement('div');
    list.className = 'choiceList';
    const groupName = `choice-${Math.random().toString(36).slice(2, 9)}`;

    const getAnswerString = () => {
      const vals = [...selected];
      return JSON.stringify({ selected: multiple ? vals : (vals[0] || '') });
    };
    const isValid = () => selected.size > 0;

    for (const opt of interaction.options || []) {
      const label = document.createElement('label');
      label.className = `choiceOption${selected.has(opt.id) ? ' is-selected' : ''}`;
      const input = document.createElement('input');
      input.type = multiple ? 'checkbox' : 'radio';
      input.name = groupName;
      input.value = opt.id;
      input.checked = selected.has(opt.id);
      input.disabled = Boolean(disabled);
      input.addEventListener('change', () => {
        if (multiple) {
          if (input.checked) {
            selected.add(opt.id);
          } else {
            selected.delete(opt.id);
          }
        } else {
          selected.clear();
          selected.add(opt.id);
        }
        for (const row of list.querySelectorAll('.choiceOption')) {
          const ctrl = row.querySelector('input');
          row.classList.toggle('is-selected', Boolean(ctrl?.checked));
        }
        onChange?.({ answerString: getAnswerString(), valid: isValid() });
      });

      const body = document.createElement('div');
      body.style.flex = '1';
      await setRichText(body, opt.html || opt.text || opt.id, { literalMath: false });
      label.append(input, body);
      list.appendChild(label);
    }
    container.appendChild(list);
    return {
      getAnswerString,
      isValid,
      focus: () => list.querySelector('input:not(:disabled)')?.focus(),
      updateFeedback: () => {},
    };
  }

  if (kind === 'true_false') {
    const statements = Array.isArray(interaction.statements) ? interaction.statements : [];
    const parsed = parseInitialAnswer(initialAnswer, interaction) || {};
    const values = {};
    for (const st of statements) {
      if (typeof parsed?.[st.id] === 'boolean') {
        values[st.id] = parsed[st.id];
      }
    }
    const grid = document.createElement('div');
    grid.className = 'tfGrid';
    const getAnswerString = () => JSON.stringify(values);
    const isValid = () => statements.length > 0 && statements.every((st) => typeof values[st.id] === 'boolean');

    for (const st of statements) {
      const row = document.createElement('div');
      row.className = 'tfRow';
      const stmtText = document.createElement('div');
      stmtText.style.flex = '1';
      await setRichText(stmtText, st.html || st.text || '', { literalMath: false });

      const controls = document.createElement('div');
      controls.className = 'tfControls';
      const trueBtn = document.createElement('button');
      const falseBtn = document.createElement('button');
      const syncButtons = () => {
        trueBtn.className = `btn btn--sm ${values[st.id] === true ? 'btn--primary' : 'btn--secondary'}`;
        falseBtn.className = `btn btn--sm ${values[st.id] === false ? 'btn--primary' : 'btn--secondary'}`;
      };
      trueBtn.type = 'button';
      trueBtn.textContent = '正确';
      trueBtn.disabled = Boolean(disabled);
      trueBtn.addEventListener('click', () => {
        values[st.id] = true;
        syncButtons();
        onChange?.({ answerString: getAnswerString(), valid: isValid() });
      });
      falseBtn.type = 'button';
      falseBtn.textContent = '错误';
      falseBtn.disabled = Boolean(disabled);
      falseBtn.addEventListener('click', () => {
        values[st.id] = false;
        syncButtons();
        onChange?.({ answerString: getAnswerString(), valid: isValid() });
      });
      syncButtons();
      controls.append(trueBtn, falseBtn);
      row.append(stmtText, controls);
      grid.appendChild(row);
    }
    container.appendChild(grid);
    return {
      getAnswerString,
      isValid,
      focus: () => grid.querySelector('button:not(:disabled)')?.focus(),
      updateFeedback: () => {},
    };
  }

  if (kind === 'matching') {
    const left = Array.isArray(interaction.left) ? interaction.left : [];
    const right = Array.isArray(interaction.right) ? interaction.right : [];
    const fixedLeft = interaction.fixed_side === 'left' && Array.isArray(interaction.fixed) ? interaction.fixed : left.map((x) => x.id);
    const parsed = parseInitialAnswer(initialAnswer, interaction);
    const pairs = fixedLeft.map((leftId, idx) => {
      const saved = Array.isArray(parsed) ? parsed.find((p) => p?.left === leftId) : null;
      return { left: leftId, right: saved?.right || right[idx]?.id || '' };
    });

    const grid = document.createElement('div');
    grid.className = 'matchingGrid';
    const getAnswerString = () => JSON.stringify(pairs);
    const isValid = () =>
      pairs.length === fixedLeft.length &&
      pairs.every((p) => p.left && p.right) &&
      new Set(pairs.map((p) => p.right)).size === pairs.length;

    for (const pair of pairs) {
      const leftMeta = left.find((x) => x.id === pair.left);
      const row = document.createElement('div');
      row.className = 'matchingRow';
      const leftLabel = document.createElement('div');
      leftLabel.style.flex = '1';
      await setRichText(leftLabel, leftMeta?.html || leftMeta?.text || pair.left, { literalMath: false });

      const select = document.createElement('select');
      select.className = 'matchingSelect';
      select.disabled = Boolean(disabled);
      for (const opt of right) {
        const option = document.createElement('option');
        option.value = opt.id;
        option.textContent = opt.text || opt.id;
        option.selected = pair.right === opt.id;
        select.appendChild(option);
      }
      select.addEventListener('change', () => {
        pair.right = select.value;
        onChange?.({ answerString: getAnswerString(), valid: isValid() });
      });
      row.append(leftLabel, select);
      grid.appendChild(row);
    }
    container.appendChild(grid);
    return {
      getAnswerString,
      isValid,
      focus: () => grid.querySelector('select:not(:disabled)')?.focus(),
      updateFeedback: () => {},
    };
  }

  // Fallback plain Japanese text input (NO LaTeX symbol toolbar).
  const hint = document.createElement('p');
  hint.className = 'widgetHint';
  hint.textContent = '请输入完整日语作答内容（支持假名或日文汉字，按 Ctrl+Enter 提交）。';
  const textarea = document.createElement('textarea');
  textarea.className = 'textAnswerArea';
  textarea.lang = 'ja';
  textarea.autocomplete = 'off';
  textarea.spellcheck = false;
  textarea.value = typeof initialAnswer === 'string' ? initialAnswer : '';
  textarea.disabled = Boolean(disabled);
  textarea.placeholder = '在此输入日语语法或句型答案…';

  const getAnswerString = () => textarea.value.trim();
  const isValid = () => getAnswerString().length > 0 && getAnswerString().length <= 2000;

  let composing = false;
  let lastCompEnd = 0;
  textarea.addEventListener('compositionstart', () => {
    composing = true;
  });
  textarea.addEventListener('compositionend', () => {
    composing = false;
    lastCompEnd = performance.now();
    onChange?.({ answerString: getAnswerString(), valid: isValid() });
  });
  textarea.addEventListener('input', () => {
    onChange?.({ answerString: getAnswerString(), valid: isValid() });
  });
  textarea.addEventListener('keydown', (event) => {
    if (composing || event.isComposing || event.keyCode === 229) {
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && performance.now() - lastCompEnd >= 30) {
      event.preventDefault();
      onSubmitShortcut?.();
    }
  });

  container.append(hint, textarea);
  return {
    getAnswerString,
    isValid,
    focus: () => textarea.focus(),
    updateFeedback: () => {},
  };
}

export async function renderFeedbackPanel(container, feedback, question = null) {
  if (!container) {
    return;
  }
  container.replaceChildren();
  if (!feedback || (feedback.correct === undefined && !feedback.reason && !feedback.explanation_html)) {
    return;
  }

  const isCorrect = Boolean(feedback.correct);
  const panel = document.createElement('div');
  panel.className = `feedbackBanner ${isCorrect ? 'is-correct' : 'is-wrong'}`;

  const title = document.createElement('div');
  title.className = 'feedbackTitle';
  const badge = document.createElement('span');
  badge.textContent = isCorrect ? '✓ 回答正确' : '✗ 回答有误';
  title.appendChild(badge);
  if (feedback.reason && feedback.reason !== '✓' && feedback.reason !== '✗') {
    const reasonSpan = document.createElement('span');
    reasonSpan.className = 'mutedText';
    reasonSpan.style.fontWeight = '500';
    reasonSpan.textContent = `· ${feedback.reason}`;
    title.appendChild(reasonSpan);
  }
  panel.appendChild(title);

  if (feedback.answer_display) {
    const submittedBox = document.createElement('div');
    submittedBox.className = 'answerReadout';
    submittedBox.innerHTML = '<strong>你的作答：</strong> ';
    const valSpan = document.createElement('span');
    await setRichText(valSpan, feedback.answer_display, { literalMath: false });
    submittedBox.appendChild(valSpan);
    panel.appendChild(submittedBox);
  }

  const refHtml = feedback.reference_answer_html || question?.reference_answer_html;
  const refText = feedback.reference_answer || question?.reference_answer;
  if (refHtml || refText) {
    const refBox = document.createElement('div');
    refBox.className = 'answerReadout';
    refBox.innerHTML = '<strong>参考答案：</strong> ';
    const refSpan = document.createElement('span');
    if (refHtml) {
      await setRichHtml(refSpan, refHtml, { literalMath: false });
    } else {
      await setRichText(refSpan, refText, { literalMath: false });
    }
    refBox.appendChild(refSpan);
    panel.appendChild(refBox);
  }

  const expHtml = feedback.explanation_html || question?.explanation_html;
  if (expHtml) {
    const expBox = document.createElement('div');
    expBox.className = 'explanationBox lessonContent';
    const expLabel = document.createElement('div');
    expLabel.innerHTML = '<strong>文法解析：</strong>';
    const expBody = document.createElement('div');
    await setRichHtml(expBody, expHtml, { literalMath: false });
    expBox.append(expLabel, expBody);
    panel.appendChild(expBox);
  }

  container.appendChild(panel);
}
