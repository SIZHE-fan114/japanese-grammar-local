export const DEFAULT_SUBJECT_ID = 'japanese';
export const DEFAULT_COURSE_ID = 'japanese-grammar-core';
export const DEFAULT_TOPIC_ID = 'jp01-copula-particles';

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'api_error', payload = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.payload = payload;
  }
}

export function newRequestId(prefix = 'req') {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return `${prefix}-${globalThis.crypto.randomUUID()}`;
  }
  const stamp = Date.now().toString(36);
  const rand = Math.random().toString(36).slice(2, 10);
  return `${prefix}-${stamp}-${rand}`;
}

export function withQuery(path, params = {}) {
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '');
  if (!entries.length) {
    return path;
  }
  const search = new URLSearchParams();
  for (const [key, value] of entries) {
    search.set(key, String(value));
  }
  const joiner = path.includes('?') ? '&' : '?';
  return `${path}${joiner}${search.toString()}`;
}

function extractErrorMessage(payload, status) {
  if (!payload) {
    return status ? `请求失败（HTTP ${status}）` : '网络连接失败';
  }
  if (typeof payload === 'string') {
    return payload;
  }
  const detail = payload.detail;
  if (typeof detail === 'string') {
    return detail;
  }
  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string' && detail.message) {
      return detail.message;
    }
    if (typeof detail.code === 'string' && detail.code) {
      return detail.code;
    }
  }
  if (typeof payload.message === 'string' && payload.message) {
    return payload.message;
  }
  if (typeof payload.error === 'string' && payload.error) {
    return payload.error;
  }
  return status ? `请求失败（HTTP ${status}）` : '未知错误';
}

function extractErrorCode(payload) {
  if (!payload || typeof payload !== 'object') {
    return 'api_error';
  }
  if (payload.detail && typeof payload.detail === 'object' && typeof payload.detail.code === 'string') {
    return payload.detail.code;
  }
  if (typeof payload.code === 'string') {
    return payload.code;
  }
  return 'api_error';
}

export async function request(path, options = {}) {
  const { method = 'GET', body, headers = {}, signal } = options;
  const init = {
    method,
    headers: {
      Accept: 'application/json',
      ...headers,
    },
    signal,
  };
  if (body !== undefined) {
    init.body = typeof body === 'string' ? body : JSON.stringify(body);
    if (!init.headers['Content-Type']) {
      init.headers['Content-Type'] = 'application/json';
    }
  }

  let response;
  try {
    response = await fetch(path, init);
  } catch (err) {
    throw new ApiError(`无法连接到本地服务：${err?.message || '网络错误'}`, { status: 0, code: 'network_error' });
  }

  if (response.status === 204) {
    return null;
  }

  const rawText = await response.text();
  let payload = null;
  if (rawText) {
    try {
      payload = JSON.parse(rawText);
    } catch {
      payload = rawText;
    }
  }

  if (!response.ok) {
    throw new ApiError(extractErrorMessage(payload, response.status), {
      status: response.status,
      code: extractErrorCode(payload),
      payload,
    });
  }
  return payload;
}

const enc = (value) => encodeURIComponent(String(value));

export const api = {
  health() {
    return request('/api/health');
  },

  subjects() {
    return request('/api/subjects');
  },

  catalog(subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/catalog', { subject_id: subjectId }));
  },

  dashboard(subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/dashboard', { subject_id: subjectId }));
  },

  graphs(subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/graphs', { subject_id: subjectId }));
  },

  graph(graphId, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery(`/api/graphs/${enc(graphId)}`, { subject_id: subjectId }));
  },

  state(topicId, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/state', { topic_id: topicId, subject_id: subjectId }));
  },

  openPageEdit(body, signal) {
    return request(withQuery('/api/page-edits/open', { subject_id: DEFAULT_SUBJECT_ID }), { method: 'POST', body, signal });
  },

  suggestPageEdit(body, signal) {
    return request(withQuery('/api/page-edits/suggest', { subject_id: DEFAULT_SUBJECT_ID }), { method: 'POST', body, signal });
  },

  savePageEdit(body, signal) {
    return request(withQuery('/api/page-edits/current', { subject_id: DEFAULT_SUBJECT_ID }), { method: 'PUT', body, signal });
  },

  closePageEdit(token) {
    return request(withQuery('/api/page-edits/close', { subject_id: DEFAULT_SUBJECT_ID }), { method: 'POST', body: { token } });
  },

  choose(topicId, choice, payload = {}, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/choose', { topic_id: topicId, subject_id: subjectId }), {
      method: 'POST',
      body: {
        request_id: payload.request_id || newRequestId('choose'),
        topic_id: topicId,
        choice,
        ...payload,
      },
    });
  },

  continueStep(topicId, payload = {}, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/continue', { topic_id: topicId, subject_id: subjectId }), {
      method: 'POST',
      body: {
        request_id: payload.request_id || newRequestId('cont'),
        topic_id: topicId,
        ...payload,
      },
    });
  },

  select(topicId, payload = {}, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/select', { topic_id: topicId, subject_id: subjectId }), {
      method: 'POST',
      body: {
        request_id: payload.request_id || newRequestId('sel'),
        topic_id: topicId,
        ...payload,
      },
    });
  },

  skip(topicId, payload = {}, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/skip', { topic_id: topicId, subject_id: subjectId }), {
      method: 'POST',
      body: {
        request_id: payload.request_id || newRequestId('skip'),
        topic_id: topicId,
        ...payload,
      },
    });
  },

  submit(topicId, payload = {}, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/submit', { topic_id: topicId, subject_id: subjectId }), {
      method: 'POST',
      body: {
        request_id: payload.request_id || newRequestId('sub'),
        topic_id: topicId,
        ...payload,
      },
    });
  },

  reveal(topicId, payload = {}, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/reveal', { topic_id: topicId, subject_id: subjectId }), {
      method: 'POST',
      body: {
        request_id: payload.request_id || newRequestId('rev'),
        topic_id: topicId,
        ...payload,
      },
    });
  },

  submission(submissionId, topicId, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery(`/api/submissions/${enc(submissionId)}`, { topic_id: topicId, subject_id: subjectId }));
  },

  pauses(topicId = null, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/pauses', { topic_id: topicId, subject_id: subjectId }));
  },

  unlockPause(payload = {}, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/pauses/unlock', { subject_id: subjectId }), {
      method: 'POST',
      body: payload,
    });
  },

  atomicReviews(subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/atomic/reviews', { subject_id: subjectId }));
  },

  reviewPaperInbox(subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/review-papers/inbox', { subject_id: subjectId }));
  },

  reviewPaperOpen(candidateId, requestId = null, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/review-papers/open', { subject_id: subjectId }), {
      method: 'POST',
      body: {
        candidate_id: candidateId,
        request_id: requestId || newRequestId('paper'),
      },
    });
  },

  reviewPaperState(paperId, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/review-papers/state', { paper_id: paperId, subject_id: subjectId }));
  },

  reviewPaperDraft(payload, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/review-papers/draft', { subject_id: subjectId }), {
      method: 'POST',
      body: payload,
    });
  },

  reviewPaperActivity(payload, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/review-papers/activity', { subject_id: subjectId }), {
      method: 'POST',
      body: payload,
    });
  },

  reviewPaperReveal(payload, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/review-papers/reveal', { subject_id: subjectId }), {
      method: 'POST',
      body: payload,
    });
  },

  reviewPaperSubmit(payload, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/review-papers/submit', { subject_id: subjectId }), {
      method: 'POST',
      body: {
        request_id: payload?.request_id || newRequestId('psub'),
        ...payload,
      },
    });
  },

  reviewPaperCancel(paperId, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/review-papers/cancel', { subject_id: subjectId }), {
      method: 'POST',
      body: { paper_id: paperId },
    });
  },

  reviewPaperPreferences(subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/review-papers/preferences', { subject_id: subjectId }));
  },

  setReviewPaperPreferences(payload, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/review-papers/preferences', { subject_id: subjectId }), {
      method: 'POST',
      body: payload,
    });
  },

  reviews(subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/reviews', { subject_id: subjectId }));
  },

  beginModuleReview(topicId, moduleId, requestId = null, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/review/begin', { topic_id: topicId, subject_id: subjectId }), {
      method: 'POST',
      body: {
        module_id: moduleId,
        request_id: requestId || newRequestId('revbegin'),
      },
    });
  },

  moduleReviewState(sessionId, topicId, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery(`/api/review/sessions/${enc(sessionId)}`, { topic_id: topicId, subject_id: subjectId }));
  },

  moduleReviewContinue(sessionId, topicId, payload = {}, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery(`/api/review/sessions/${enc(sessionId)}/continue`, { topic_id: topicId, subject_id: subjectId }), {
      method: 'POST',
      body: {
        request_id: payload.request_id || newRequestId('revcont'),
        ...payload,
      },
    });
  },

  moduleReviewSubmit(sessionId, topicId, payload = {}, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery(`/api/review/sessions/${enc(sessionId)}/submit`, { topic_id: topicId, subject_id: subjectId }), {
      method: 'POST',
      body: {
        request_id: payload.request_id || newRequestId('revsub'),
        ...payload,
      },
    });
  },

  moduleReviewReveal(sessionId, topicId, payload = {}, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery(`/api/review/sessions/${enc(sessionId)}/reveal`, { topic_id: topicId, subject_id: subjectId }), {
      method: 'POST',
      body: {
        request_id: payload.request_id || newRequestId('revrev'),
        ...payload,
      },
    });
  },

  moduleReviewSubmission(submissionId, topicId, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery(`/api/review/submissions/${enc(submissionId)}`, { topic_id: topicId, subject_id: subjectId }));
  },

  studentReport(days = 30, subjectId = DEFAULT_SUBJECT_ID) {
    let tz = 'Asia/Shanghai';
    try {
      tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai';
    } catch {
      tz = 'Asia/Shanghai';
    }
    return request(withQuery('/api/student-report', { days, subject_id: subjectId, timezone: tz }));
  },

  adminStudents(subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/admin-students', { subject_id: subjectId }));
  },

  presence(topicId, subjectId = DEFAULT_SUBJECT_ID) {
    return request(withQuery('/api/presence', { subject_id: subjectId }), {
      method: 'POST',
      body: {
        topic_id: topicId,
        active: true,
        kind: 'topic',
      },
    });
  },

  aiConfig() {
    return request('/api/ai/config');
  },

  updateAiConfig(payload = {}) {
    return request('/api/ai/config', {
      method: 'PUT',
      body: payload,
    });
  },

  testAiConnection(payload = {}) {
    return request('/api/ai/test', {
      method: 'POST',
      body: payload,
    });
  },

  async aiChatStream({
    messages,
    attachContext = true,
    context = null,
    stream = null,
    signal = null,
    onMeta = null,
    onDelta = null,
    onDone = null,
  }) {
    const reqBody = {
      messages,
      attach_context: Boolean(attachContext),
    };
    if (context) {
      reqBody.context = context;
    }
    if (typeof stream === 'boolean') {
      reqBody.stream = stream;
    }

    let response;
    try {
      response = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream, application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(reqBody),
        signal,
      });
    } catch (err) {
      if (err?.name === 'AbortError') {
        throw err;
      }
      throw new ApiError(`无法连接到 AI 代理服务：${err?.message || '网络错误'}`, {
        status: 0,
        code: 'network_error',
      });
    }

    if (!response.ok) {
      const rawText = await response.text();
      let payload = null;
      if (rawText) {
        try {
          payload = JSON.parse(rawText);
        } catch {
          payload = rawText;
        }
      }
      throw new ApiError(extractErrorMessage(payload, response.status), {
        status: response.status,
        code: extractErrorCode(payload),
        payload,
      });
    }

    const contentType = (response.headers.get('content-type') || '').toLowerCase();
    if (!contentType.includes('text/event-stream') || !response.body) {
      const data = await response.json();
      if (typeof data?.heuristic_mode === 'boolean') {
        onMeta?.({ heuristic_mode: data.heuristic_mode, effective_mode: data.effective_mode });
      }
      if (data?.reply) {
        onDelta?.(data.reply, data);
      }
      onDone?.(data);
      return data;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let finalData = { reply: '', model: '' };

    const handleFrame = (rawLine) => {
      const line = rawLine.trim();
      if (!line || !line.startsWith('data:')) {
        return;
      }
      const rawJson = line.slice(5).trim();
      if (!rawJson || rawJson === '[DONE]') {
        return;
      }
      let frame;
      try {
        frame = JSON.parse(rawJson);
      } catch {
        return;
      }
      if (frame.meta) {
        onMeta?.(frame.meta);
      }
      if (frame.error) {
        throw new ApiError(String(frame.error), { status: 502, code: 'ai_stream_error', payload: frame });
      }
      if (frame.delta) {
        finalData.reply += frame.delta;
        if (frame.model) {
          finalData.model = frame.model;
        }
        onDelta?.(frame.delta, frame);
      }
      if (frame.done) {
        if (frame.model) {
          finalData.model = frame.model;
        }
        finalData.usage = frame.usage || null;
        onDone?.(finalData);
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          handleFrame(line);
        }
      }
      buffer += decoder.decode();
      if (buffer.trim()) {
        for (const line of buffer.split(/\r?\n/)) {
          handleFrame(line);
        }
      }
    } finally {
      reader.releaseLock();
    }
    return finalData;
  },
};

export async function awaitSubmissionResult(
  submissionId,
  topicId,
  {
    subjectId = DEFAULT_SUBJECT_ID,
    fetcher = (id, tId) => api.submission(id, tId, subjectId),
    intervalMs = 420,
    timeoutMs = 45000,
  } = {},
) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await fetcher(submissionId, topicId);
    if (!result || (result.status !== 'pending' && result.status !== 'running')) {
      return result;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new ApiError('判题超时，请稍后刷新状态重试。', { status: 504, code: 'judge_timeout' });
}
