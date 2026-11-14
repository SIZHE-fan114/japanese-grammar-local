/**
 * Persistent toggleable AI Tutor drawer & OpenAI-compatible settings modal.
 */

import { api } from './api.js';
import { escapeHtml } from './math-render.js';

function formatSafeTutorMessage(rawText) {
  const escaped = escapeHtml(String(rawText || ''));
  return escaped
    .replace(/`([^`\n]+)`/g, '<code class="aiInlineCode">$1</code>')
    .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

function quickPromptsForContext(ctx) {
  const view = String(ctx?.view || '').toLowerCase();
  if (view === 'answer' || (view === 'paper' && !ctx?.isSubmitted)) {
    return [
      '给我一点解题思路提示（先别剧透答案）',
      '这句话的主语、主题或动作对象分别是什么？',
      '这里应该用简体还是敬体？为什么？',
    ];
  }
  if (view === 'feedback' || (view === 'paper' && ctx?.isSubmitted)) {
    return [
      '为什么这里必须这样填？对比一下常见错误选项',
      '请结合这个语法点再举 2 个简洁例句（附假名与罗马音）',
      '它和相近助词或句型最容易在哪混用？',
    ];
  }
  if (view === 'introduction' || view === 'chunk') {
    return [
      '用更直观的白话帮我总结这张卡片的核心规则',
      '能给一个常见误用对比（错句 vs 对句）吗？',
      '这部分做题时最先看句子的哪个线索？',
    ];
  }
  return [
    '日语「は」和「が」做题时最稳妥的判断步骤是什么？',
    '怎么快速分辨一段动词、五段动词与特例词？',
    '请出一道结合本课难点的对比小练习并提示我检查',
  ];
}

function describeContextPill(ctx) {
  if (!ctx) {
    return { label: '当前页面：通用日语语法问答', heuristic: false };
  }
  const view = String(ctx.view || '').toLowerCase();
  if (view === 'answer' || (view === 'paper' && !ctx.isSubmitted)) {
    return {
      label: `语境：${ctx.topicTitle || '当前练习'} · 未交卷启发模式（默认不剧透）`,
      heuristic: true,
    };
  }
  if (view === 'feedback' || (view === 'paper' && ctx.isSubmitted)) {
    return {
      label: `语境：${ctx.topicTitle || '当前题目'} · 已交卷精讲模式`,
      heuristic: false,
    };
  }
  if (view === 'introduction') {
    const step = ctx.stepIndex && ctx.stepTotal ? `（第 ${ctx.stepIndex}/${ctx.stepTotal} 张）` : '';
    return {
      label: `语境：${ctx.topicTitle || '语法讲义'}${step}`,
      heuristic: false,
    };
  }
  if (view === 'chunk') {
    return {
      label: `语境：${ctx.topicTitle || '记忆组块'} · ${ctx.stepTitle || '组块总结'}`,
      heuristic: false,
    };
  }
  return {
    label: `语境：${ctx.label || ctx.topicTitle || '日语语法学习系统'}`,
    heuristic: false,
  };
}

export function createAiAssistant({
  drawerHost,
  drawerToggleBtn,
  settingsBtn,
  modalHost,
  getContext,
  showToast,
}) {
  const state = {
    open: false,
    config: null,
    attachContext: true,
    messages: [],
    streaming: false,
    abortController: null,
    imeComposing: false,
    lastHeuristic: null,
  };

  async function refreshConfig({ silent = true } = {}) {
    try {
      state.config = await api.aiConfig();
    } catch (err) {
      if (!silent) {
        showToast?.(err.message || '读取 AI 配置失败', { error: true });
      }
    }
    renderDrawer();
    return state.config;
  }

  function setDrawerOpen(open) {
    state.open = Boolean(open);
    if (drawerHost) {
      drawerHost.classList.toggle('hidden', !state.open);
      drawerHost.setAttribute('aria-hidden', String(!state.open));
    }
    drawerToggleBtn?.setAttribute('aria-expanded', String(state.open));
    document.body.classList.toggle('ai-drawer-open', state.open);
    if (state.open) {
      if (!state.config) {
        refreshConfig();
      } else {
        renderDrawer();
      }
      const ta = drawerHost?.querySelector('#aiChatInput');
      requestAnimationFrame(() => ta?.focus());
    }
  }

  function renderDrawer() {
    if (!drawerHost || !state.open) {
      return;
    }
    const existingInput = drawerHost.querySelector('#aiChatInput')?.value ?? '';
    const ctx = getContext ? getContext() : null;
    const ctxDesc = describeContextPill(ctx);
    const cfg = state.config;
    const configured = Boolean(cfg?.configured);
    const statusText = cfg
      ? configured
        ? `${cfg.model} · ${cfg.sources?.api_key === 'env' ? '环境变量' : '本地配置'}`
        : '未配置 Key'
      : '读取配置中…';

    const quickPrompts = quickPromptsForContext(ctx);
    const messagesHtml = state.messages.length
      ? state.messages
          .map((m, idx) => {
            const roleLabel = m.role === 'user' ? '你' : 'AI 助教';
            const contentHtml =
              m.role === 'assistant' && !m.content && state.streaming && idx === state.messages.length - 1
                ? '<span class="mutedText">思考中…</span>'
                : formatSafeTutorMessage(m.content || '');
            return `
              <div class="aiMsg aiMsg--${m.role === 'user' ? 'user' : 'assistant'}">
                <div class="aiMsgMeta">
                  <span>${roleLabel}</span>
                  ${m.badge ? `<span class="aiMsgBadge">${escapeHtml(m.badge)}</span>` : ''}
                </div>
                <div class="aiMsgBubble">${contentHtml}</div>
              </div>
            `;
          })
          .join('')
      : `
        <div class="aiEmptyState">
          <div class="aiEmptyTitle">日语语法随时问答</div>
          <p class="mutedText" style="margin:6px 0 0;">
            无需切出当前页面即可追问讲义难点或做题思路。未提交题目时，助教将先做启发式引导，不会直接泄漏答案。
          </p>
          ${
            configured
              ? ''
              : '<p class="aiWarnText">尚未检测到可用 API Key，请先点击右上角「接口设置」填入密钥或配置环境变量 OPENAI_API_KEY。</p>'
          }
        </div>
      `;

    drawerHost.innerHTML = `
      <div class="aiDrawerHeader">
        <div>
          <div class="aiDrawerTitle">日语 AI 助教</div>
          <div class="aiDrawerSub">
            <span class="aiStatusDot ${configured ? 'is-ready' : 'is-warn'}"></span>
            <span>${escapeHtml(statusText)}</span>
          </div>
        </div>
        <div class="aiDrawerHeaderActions">
          <button type="button" class="btn btn--ghost btn--sm" id="aiDrawerSettingsBtn">接口设置</button>
          <button type="button" class="btn btn--ghost btn--sm" id="aiClearChatBtn" ${state.streaming || !state.messages.length ? 'disabled' : ''}>清空</button>
          <button type="button" class="btn btn--secondary btn--sm" id="aiDrawerCloseBtn" aria-label="关闭助教面板">关闭</button>
        </div>
      </div>

      <div class="aiContextBar">
        <label class="aiContextToggle">
          <input type="checkbox" id="aiAttachContextChk" ${state.attachContext ? 'checked' : ''} />
          <span>自动附带当前学习语境</span>
        </label>
        <div class="aiContextPill ${ctxDesc.heuristic ? 'is-socratic' : ''}">${escapeHtml(ctxDesc.label)}</div>
      </div>

      <div class="aiMessages" id="aiMessagesBox">${messagesHtml}</div>

      <div class="aiQuickChips" id="aiQuickChipsBar">
        ${quickPrompts
          .map(
            (promptText, i) =>
              `<button type="button" class="aiChipBtn" data-quick-idx="${i}" ${state.streaming ? 'disabled' : ''}>${escapeHtml(promptText)}</button>`,
          )
          .join('')}
      </div>

      <form class="aiComposer" id="aiChatForm">
        <textarea
          id="aiChatInput"
          class="aiInput"
          rows="2"
          placeholder="${configured ? '输入你的疑问（Enter 发送，Shift+Enter 换行）…' : '请先点击上方「接口设置」配置 API Key…'}"
        ></textarea>
        <div class="aiComposerActions">
          <span class="mutedText" style="font-size:11.5px;">${state.config?.stream === false ? '标准响应' : '流式实时输出'}</span>
          ${
            state.streaming
              ? '<button type="button" class="btn btn--danger btn--sm" id="aiStopBtn">停止生成</button>'
              : '<button type="submit" class="btn btn--primary btn--sm" id="aiSendBtn">发送提问</button>'
          }
        </div>
      </form>
    `;

    const inputEl = drawerHost.querySelector('#aiChatInput');
    if (inputEl && existingInput) {
      inputEl.value = existingInput;
    }

    const msgBox = drawerHost.querySelector('#aiMessagesBox');
    if (msgBox) {
      msgBox.scrollTop = msgBox.scrollHeight;
    }

    drawerHost.querySelector('#aiDrawerCloseBtn')?.addEventListener('click', () => setDrawerOpen(false));
    drawerHost.querySelector('#aiDrawerSettingsBtn')?.addEventListener('click', () => openSettingsModal());
    drawerHost.querySelector('#aiClearChatBtn')?.addEventListener('click', () => {
      if (state.streaming) {
        return;
      }
      state.messages = [];
      renderDrawer();
    });
    drawerHost.querySelector('#aiAttachContextChk')?.addEventListener('change', (e) => {
      state.attachContext = Boolean(e.target.checked);
    });
    drawerHost.querySelector('#aiStopBtn')?.addEventListener('click', () => {
      state.abortController?.abort();
    });

    drawerHost.querySelectorAll('[data-quick-idx]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const idx = Number(btn.dataset.quickIdx);
        const promptText = quickPrompts[idx];
        if (promptText) {
          sendQuestion(promptText);
        }
      });
    });

    inputEl?.addEventListener('compositionstart', () => {
      state.imeComposing = true;
    });
    inputEl?.addEventListener('compositionend', () => {
      state.imeComposing = false;
    });
    inputEl?.addEventListener('keydown', (event) => {
      if (state.imeComposing || event.isComposing || event.keyCode === 229) {
        return;
      }
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        drawerHost.querySelector('#aiChatForm')?.requestSubmit();
      }
    });

    drawerHost.querySelector('#aiChatForm')?.addEventListener('submit', (event) => {
      event.preventDefault();
      const text = String(inputEl?.value || '').trim();
      if (!text || state.streaming) {
        return;
      }
      if (inputEl) {
        inputEl.value = '';
      }
      sendQuestion(text);
    });
  }

  async function sendQuestion(promptText) {
    const cleanText = String(promptText || '').trim();
    if (!cleanText || state.streaming) {
      return;
    }
    if (!state.config) {
      await refreshConfig();
    }
    if (!state.config?.configured) {
      showToast?.('请先完成 AI 接口配置（API Key / Base URL）', { error: true });
      openSettingsModal();
      return;
    }

    const ctx = getContext ? getContext() : null;
    const reqContext = ctx
      ? {
          topic_id: ctx.topicId || undefined,
          view: ctx.view || undefined,
          paper_id: ctx.paperId || undefined,
          card_id: ctx.cardId || undefined,
          step_index: ctx.stepIndex || undefined,
          step_total: ctx.stepTotal || undefined,
          step_title: ctx.stepTitle || undefined,
          step_text: ctx.stepText ? String(ctx.stepText).slice(0, 2500) : undefined,
          user_draft: ctx.userDraft ? String(ctx.userDraft).slice(0, 600) : undefined,
        }
      : null;

    state.messages.push({ role: 'user', content: cleanText });
    const historyToSend = state.messages
      .slice(-16)
      .map((m) => ({ role: m.role, content: m.content }));

    const assistantEntry = { role: 'assistant', content: '', badge: '' };
    state.messages.push(assistantEntry);
    state.streaming = true;
    const controller = new AbortController();
    state.abortController = controller;
    renderDrawer();

    try {
      await api.aiChatStream({
        messages: historyToSend,
        attachContext: state.attachContext,
        context: reqContext,
        stream: state.config?.stream,
        signal: controller.signal,
        onMeta: (meta) => {
          state.lastHeuristic = Boolean(meta?.heuristic_mode);
          assistantEntry.badge = meta?.heuristic_mode ? '启发引导模式' : '';
        },
        onDelta: (chunk) => {
          assistantEntry.content += chunk;
          const box = drawerHost?.querySelector('#aiMessagesBox');
          if (box) {
            const bubbles = box.querySelectorAll('.aiMsgBubble');
            const lastBubble = bubbles[bubbles.length - 1];
            const badges = box.querySelectorAll('.aiMsg--assistant .aiMsgMeta');
            if (lastBubble) {
              lastBubble.innerHTML = formatSafeTutorMessage(assistantEntry.content);
              if (assistantEntry.badge && badges.length) {
                const lastMeta = badges[badges.length - 1];
                if (!lastMeta.querySelector('.aiMsgBadge')) {
                  const span = document.createElement('span');
                  span.className = 'aiMsgBadge';
                  span.textContent = assistantEntry.badge;
                  lastMeta.appendChild(span);
                }
              }
              box.scrollTop = box.scrollHeight;
            }
          }
        },
        onDone: () => {},
      });
      if (!assistantEntry.content.trim()) {
        assistantEntry.content = '（模型未返回正文内容，请检查模型名称或稍后重试。）';
      }
    } catch (err) {
      if (err?.name === 'AbortError') {
        if (!assistantEntry.content.trim()) {
          assistantEntry.content = '（已手动停止本次回答）';
        }
      } else {
        assistantEntry.content = `请求失败：${err?.message || '未知错误'}`;
        showToast?.(err?.message || 'AI 请求失败', { error: true });
      }
    } finally {
      state.streaming = false;
      state.abortController = null;
      renderDrawer();
    }
  }

  async function openSettingsModal() {
    if (!modalHost) {
      return;
    }
    const cfg = (await refreshConfig({ silent: false })) || {
      base_url: 'https://api.openai.com/v1',
      model: 'gpt-4o-mini',
      stream: true,
      api_key_set: false,
      api_key_masked: '',
      sources: {},
      local_overrides: {},
      env_available: {},
    };

    modalHost.replaceChildren();
    modalHost.classList.remove('hidden');
    modalHost.setAttribute('aria-hidden', 'false');

    const dialog = document.createElement('div');
    dialog.className = 'modalDialog';
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.style.maxWidth = '600px';

    const closeModal = () => {
      modalHost.classList.add('hidden');
      modalHost.setAttribute('aria-hidden', 'true');
      modalHost.replaceChildren();
    };

    const sourceLabel = (src) =>
      src === 'local' ? '本地设置覆盖' : src === 'env' ? '环境变量回退' : src === 'default' ? '系统默认值' : '未设置';

    dialog.innerHTML = `
      <div class="modalHeader">
        <h3 class="cardTitle" style="margin:0;">OpenAI 兼容 AI 接口设置</h3>
        <button type="button" class="btn btn--secondary btn--sm" id="aiModalCloseBtn">关闭</button>
      </div>
      <div class="modalBody">
        <p class="mutedText" style="margin-top:0;">
          支持本地网页保存（存于 <code>.runtime/japanese-grammar/ai_config.json</code>，绝不进入 Git）与系统环境变量（<code>OPENAI_API_KEY</code> / <code>OPENAI_BASE_URL</code> / <code>OPENAI_MODEL</code>）。本地配置优先于环境变量；清空本地字段即自动回退环境变量。
        </p>

        <div class="aiSettingField">
          <label class="aiSettingLabel" for="aiBaseUrlInput">
            <span>API Base URL</span>
            <span class="pill">${escapeHtml(sourceLabel(cfg.sources?.base_url))}</span>
          </label>
          <input type="url" id="aiBaseUrlInput" class="aiTextInput" value="${escapeHtml(cfg.local_overrides?.has_base_url ? cfg.base_url : '')}" placeholder="${escapeHtml(cfg.base_url || 'https://api.openai.com/v1')}" />
          <div class="mutedText" style="font-size:12px;">当前生效：<code>${escapeHtml(cfg.base_url)}</code></div>
        </div>

        <div class="aiSettingField">
          <label class="aiSettingLabel" for="aiApiKeyInput">
            <span>API Key（密钥仅存本机后端）</span>
            <span class="pill">${escapeHtml(sourceLabel(cfg.sources?.api_key))}</span>
          </label>
          <div class="aiKeyRow">
            <input type="password" id="aiApiKeyInput" class="aiTextInput" autocomplete="new-password" placeholder="${cfg.api_key_set ? `已生效 (${escapeHtml(cfg.api_key_masked)})；留空保持不变` : '输入 sk-... 或兼容平台密钥'}" />
            <button type="button" class="btn btn--ghost btn--sm" id="aiKeyVisBtn">显示</button>
          </div>
          ${
            cfg.local_overrides?.has_api_key
              ? '<div class="mutedText" style="font-size:12px;">已保存本地密钥覆盖。若需切回环境变量 Key，可点击下方「恢复环境变量」。</div>'
              : cfg.env_available?.has_api_key
                ? '<div class="mutedText" style="font-size:12px;">当前正使用后端环境变量 OPENAI_API_KEY。</div>'
                : '<div class="mutedText" style="font-size:12px;">环境变量未配置 OPENAI_API_KEY，请在上方填写。</div>'
          }
        </div>

        <div class="aiSettingField">
          <label class="aiSettingLabel" for="aiModelInput">
            <span>Model 模型名称</span>
            <span class="pill">${escapeHtml(sourceLabel(cfg.sources?.model))}</span>
          </label>
          <input type="text" id="aiModelInput" class="aiTextInput" value="${escapeHtml(cfg.local_overrides?.has_model ? cfg.model : '')}" placeholder="${escapeHtml(cfg.model || 'gpt-4o-mini')}" />
          <div class="mutedText" style="font-size:12px;">当前生效：<code>${escapeHtml(cfg.model)}</code></div>
        </div>

        <label class="aiContextToggle" style="margin-top:10px;">
          <input type="checkbox" id="aiStreamChk" ${cfg.stream !== false ? 'checked' : ''} />
          <span>启用流式输出（Streaming SSE）</span>
        </label>

        <div id="aiTestResultBox" class="aiTestResult hidden"></div>

        <div class="actionRow" style="justify-content:space-between;margin-top:16px;">
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button type="button" class="btn btn--secondary btn--sm" id="aiTestConnBtn">测试连接</button>
            <button type="button" class="btn btn--ghost btn--sm" id="aiResetEnvBtn">恢复环境变量</button>
          </div>
          <button type="button" class="btn btn--primary btn--sm" id="aiSaveCfgBtn">保存设置</button>
        </div>
      </div>
    `;

    modalHost.appendChild(dialog);
    const onOverlayClick = (event) => {
      if (event.target === modalHost) {
        modalHost.removeEventListener('click', onOverlayClick);
        closeModal();
      }
    };
    modalHost.addEventListener('click', onOverlayClick);
    dialog.querySelector('#aiModalCloseBtn')?.addEventListener('click', () => {
      modalHost.removeEventListener('click', onOverlayClick);
      closeModal();
    });

    const baseInput = dialog.querySelector('#aiBaseUrlInput');
    const keyInput = dialog.querySelector('#aiApiKeyInput');
    const modelInput = dialog.querySelector('#aiModelInput');
    const streamChk = dialog.querySelector('#aiStreamChk');
    const testBox = dialog.querySelector('#aiTestResultBox');

    dialog.querySelector('#aiKeyVisBtn')?.addEventListener('click', (e) => {
      const isPw = keyInput.type === 'password';
      keyInput.type = isPw ? 'text' : 'password';
      e.target.textContent = isPw ? '隐藏' : '显示';
    });

    dialog.querySelector('#aiTestConnBtn')?.addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      testBox.className = 'aiTestResult';
      testBox.textContent = '正在探测接口连通性…';
      try {
        const res = await api.testAiConnection({
          base_url: baseInput.value.trim() || undefined,
          api_key: keyInput.value.trim() || undefined,
          model: modelInput.value.trim() || undefined,
        });
        testBox.className = 'aiTestResult is-ok';
        const extra = res.probe === 'models' && res.available_models_count ? `，检测到 ${res.available_models_count} 个可用模型` : '';
        testBox.textContent = `✓ 连接成功！(${res.probe}, ${res.latency_ms} ms, 模型: ${res.model}${extra})`;
      } catch (err) {
        testBox.className = 'aiTestResult is-err';
        testBox.textContent = `✗ 测试失败：${err.message || '请检查地址或密钥'}`;
      } finally {
        btn.disabled = false;
      }
    });

    dialog.querySelector('#aiResetEnvBtn')?.addEventListener('click', async () => {
      try {
        state.config = await api.updateAiConfig({ reset_to_env: true });
        showToast?.('已清空本地覆盖并恢复环境变量配置');
        closeModal();
        renderDrawer();
      } catch (err) {
        showToast?.(err.message || '重置失败', { error: true });
      }
    });

    dialog.querySelector('#aiSaveCfgBtn')?.addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      const updatePayload = {
        base_url: baseInput.value.trim(),
        model: modelInput.value.trim(),
        stream: Boolean(streamChk.checked),
      };
      if (keyInput.value.trim()) {
        updatePayload.api_key = keyInput.value.trim();
      }
      try {
        state.config = await api.updateAiConfig(updatePayload);
        showToast?.('AI 接口配置已保存到本机');
        closeModal();
        renderDrawer();
      } catch (err) {
        testBox.className = 'aiTestResult is-err';
        testBox.textContent = `✗ 保存失败：${err.message || '配置格式有误'}`;
      } finally {
        btn.disabled = false;
      }
    });
  }

  drawerToggleBtn?.addEventListener('click', () => setDrawerOpen(!state.open));
  settingsBtn?.addEventListener('click', () => openSettingsModal());

  return {
    notifyContextChanged() {
      if (state.open) {
        renderDrawer();
      }
    },
    setOpen: setDrawerOpen,
    openSettings: openSettingsModal,
    refreshConfig,
  };
}
