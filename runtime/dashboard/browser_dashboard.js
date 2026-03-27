const stateEls = {
  environmentState: document.getElementById('environment-state'),
  activeScenario: document.getElementById('active-scenario'),
  proofState: document.getElementById('proof-state'),
  sessionId: document.getElementById('session-id'),
  operatorViewLink: document.getElementById('operator-view-link'),
  worldLink: document.getElementById('world-link'),
  worldImage: document.getElementById('world-image'),
  debugImage: document.getElementById('debug-image'),
  rawImage: document.getElementById('raw-image'),
  topdownImage: document.getElementById('topdown-image'),
  debugVisualStatus: document.getElementById('debug-visual-status'),
  controlsDrawer: document.getElementById('controls-drawer'),
  logDrawer: document.getElementById('log-drawer'),
  toggleControls: document.getElementById('btn-toggle-controls'),
  toggleControlsState: document.getElementById('controls-toggle-state'),
  toggleLog: document.getElementById('btn-toggle-log'),
  toggleLogState: document.getElementById('log-toggle-state'),
  toggleLogCount: document.getElementById('log-unread-count'),
  toggleLogDot: document.getElementById('log-unread-dot'),
  closeControls: document.getElementById('btn-close-controls'),
  closeLog: document.getElementById('btn-close-log'),
  demoList: document.getElementById('demo-list'),
  runLogChip: document.getElementById('run-log-chip'),
  runLogList: document.getElementById('run-log-list'),
  controlModeDetail: document.getElementById('control-mode-detail'),
  warmServices: document.getElementById('warm-services'),
  composeProject: document.getElementById('compose-project'),
  operatorViewReady: document.getElementById('operator-view-ready'),
  operatorViewBackend: document.getElementById('operator-view-backend'),
  worldStreamReady: document.getElementById('world-stream-ready'),
  truthAlignment: document.getElementById('truth-alignment'),
  motionEvidence: document.getElementById('motion-evidence'),
  operatorFootnote: document.getElementById('operator-footnote'),
  perceptionLane: document.getElementById('perception-lane'),
  beliefLane: document.getElementById('belief-lane'),
  decisionLane: document.getElementById('decision-lane'),
  outcomeLane: document.getElementById('outcome-lane'),
  previewStatus: document.getElementById('preview-status'),
  previewReadiness: document.getElementById('preview-readiness'),
  previewActivity: document.getElementById('preview-activity'),
  previewPayload: document.getElementById('preview-payload'),
  shadowDetailStatus: document.getElementById('shadow-detail-status'),
  shadowDetailProvider: document.getElementById('shadow-detail-provider'),
  shadowDetailModel: document.getElementById('shadow-detail-model'),
  shadowDetailStateHash: document.getElementById('shadow-detail-state-hash'),
  shadowDetailPreview: document.getElementById('shadow-detail-preview'),
  shadowDetailHistoryPath: document.getElementById('shadow-detail-history-path'),
  shadowDetailSuppression: document.getElementById('shadow-detail-suppression'),
  shadowHistoryList: document.getElementById('shadow-history-list')
};

const controls = {
  startEnv: document.getElementById('btn-start-env'),
  stop: document.getElementById('btn-stop'),
  refresh: document.getElementById('btn-refresh'),
  resetSim: document.getElementById('btn-reset-sim'),
  stopScenario: document.getElementById('btn-stop-scenario'),
  runScenario: document.getElementById('btn-run-scenario'),
  scenarioSelect: document.getElementById('scenario-select'),
  targetClass: document.getElementById('target-class'),
  approachDistance: document.getElementById('approach-distance'),
  acquireTarget: document.getElementById('btn-acquire-target'),
  planToTarget: document.getElementById('btn-plan-to-target'),
  trackTarget: document.getElementById('btn-track-target'),
  abort: document.getElementById('btn-abort'),
  safeStop: document.getElementById('btn-safe-stop'),
  intentTemplate: document.getElementById('intent-template'),
  intentJson: document.getElementById('intent-json'),
  previewIntent: document.getElementById('btn-preview-intent'),
  dispatchIntent: document.getElementById('btn-dispatch-intent')
};

const demoFlow = [
  { id: 'llm_turn_then_go_proof', label: 'LLM Turn + Go' },
  { id: 'visit_single_ball_proof', label: 'Visit Single Ball' },
  { id: 'visit_three_ball_sequence', label: 'Visit 3 Ball Sequence' },
  { id: 'm3_single_target', label: 'M3 Single Target' },
  { id: 'm3_center', label: 'M3 Center' },
  { id: 'm3_left', label: 'M3 Left' },
  { id: 'm3_right', label: 'M3 Right' }
];

const demoMetaById = Object.fromEntries(demoFlow.map((item) => [item.id, item]));
const manualScenarioFallback = ['m2_single_target', ...demoFlow.map((item) => item.id), 'multi_target_rehearsal'];
const intentTemplates = {
  acquire_target: { intent: 'acquire_target', args: { target_class: 'ball' } },
  plan_to_target: { intent: 'plan_to_target', args: { approach_distance_m: 0.25 } },
  track_target: { intent: 'track_target', args: {} },
  abort: { intent: 'abort', args: {} },
  safe_stop: { intent: 'safe_stop', args: {} }
};

const storageKeys = {
  controlsDrawerOpen: 'chasecar.browser.controlsDrawerOpen',
  logDrawerOpen: 'chasecar.browser.logDrawerOpen'
};

let apiMode = true;
let cachedScenarios = [];
let localPreview = null;
let lastRenderedState = null;
let pendingScenarioId = '';

const uiState = {
  controlsDrawerOpen: readBoolStorage(storageKeys.controlsDrawerOpen, false),
  logDrawerOpen: readBoolStorage(storageKeys.logDrawerOpen, false),
  logUnreadCount: 0,
  lastSeenLogKey: '',
  logPrimed: false,
  lastFailureAutoOpenKey: ''
};

function readBoolStorage(key, fallback = false) {
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) {
      return fallback;
    }
    return raw === 'true';
  } catch (_err) {
    return fallback;
  }
}

function writeBoolStorage(key, value) {
  try {
    window.localStorage.setItem(key, value ? 'true' : 'false');
  } catch (_err) {
    // ignore storage errors
  }
}

function placeholderImage() {
  return 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';
}

function stampImage(el, path) {
  el.src = `${path}?t=${Date.now()}`;
}

function selectText(value, fallback = 'n/a') {
  return value === undefined || value === null || value === '' ? fallback : String(value);
}

function formatMeters(value) {
  if (value === undefined || value === null || value === '') {
    return 'n/a';
  }
  const num = Number(value);
  return Number.isFinite(num) ? `${num.toFixed(2)} m` : String(value);
}

function formatPose(value) {
  if (!value || typeof value !== 'object') {
    return 'n/a';
  }
  const x = Number(value.x);
  const y = Number(value.y);
  const yaw = value.yaw === undefined ? null : Number(value.yaw);
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return 'n/a';
  }
  if (yaw === null || !Number.isFinite(yaw)) {
    return `x=${x.toFixed(2)}, y=${y.toFixed(2)}`;
  }
  return `x=${x.toFixed(2)}, y=${y.toFixed(2)}, yaw=${yaw.toFixed(2)}`;
}

function formatPoint(value) {
  if (!value || typeof value !== 'object') {
    return 'n/a';
  }
  const x = Number(value.x);
  const y = Number(value.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return 'n/a';
  }
  return `x=${x.toFixed(2)}, y=${y.toFixed(2)}`;
}

function prettifyIntent(intentName) {
  const value = selectText(intentName, '');
  if (!value) {
    return '';
  }
  return value.replaceAll('_', ' ');
}

function shortIntent(intentName) {
  const value = selectText(intentName, '');
  const mapping = {
    search_for_target: 'search',
    acquire_target: 'acquire',
    plan_to_target: 'plan',
    track_target: 'track',
    abort: 'abort',
    safe_stop: 'safe stop'
  };
  return mapping[value] || prettifyIntent(value);
}

function summarizeTime(value) {
  const text = selectText(value, '');
  if (!text) {
    return '';
  }
  const parsed = new Date(text);
  if (!Number.isNaN(parsed.getTime())) {
    return parsed.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  }
  return text.replace('T', ' ').replace('Z', ' UTC');
}

function laneRow(label, value) {
  return `\n    <div class="lane-row">\n      <div class="lane-label">${label}</div>\n      <div class="lane-value">${value}</div>\n    </div>\n  `;
}

function renderLane(element, rows) {
  element.innerHTML = rows.map((row) => laneRow(row.label, row.value)).join('');
}

function completedStorageKey(sessionId) {
  return `chasecar.dashboard.completed.${sessionId}`;
}

function loadCompletedScenarios(sessionId) {
  if (!sessionId) {
    return new Set();
  }
  try {
    const raw = window.sessionStorage.getItem(completedStorageKey(sessionId));
    const parsed = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch (_err) {
    return new Set();
  }
}

function saveCompletedScenarios(sessionId, completedSet) {
  if (!sessionId) {
    return;
  }
  window.sessionStorage.setItem(completedStorageKey(sessionId), JSON.stringify(Array.from(completedSet)));
}

function trackScenarioProgress(state) {
  const sessionId = selectText(state.session_id, '');
  const completed = loadCompletedScenarios(sessionId);
  const scenarioState = selectText(state.scenario_state, 'idle');
  const activeScenario = selectText(state.active_scenario, '');
  const sessionChanged = lastRenderedState && lastRenderedState.session_id !== sessionId;
  if (sessionChanged) {
    pendingScenarioId = '';
  }
  if (scenarioState === 'running' && demoMetaById[activeScenario]) {
    pendingScenarioId = activeScenario;
  }
  const scenarioJustFinished = lastRenderedState
    && lastRenderedState.session_id === sessionId
    && lastRenderedState.scenario_state === 'running'
    && scenarioState !== 'running';
  if (scenarioJustFinished && pendingScenarioId) {
    const cancelled = String(state.last_result || '').toLowerCase().includes('cancel');
    if (!cancelled && scenarioState === 'ready') {
      completed.add(pendingScenarioId);
      saveCompletedScenarios(sessionId, completed);
    }
    pendingScenarioId = '';
  }
  return completed;
}

function scenarioLabel(id) {
  const normalized = selectText(id, '');
  if (!normalized) {
    return 'idle';
  }
  const cached = cachedScenarios.find((item) => item && item.id === normalized);
  if (cached && cached.label) {
    return String(cached.label);
  }
  return demoMetaById[normalized] ? demoMetaById[normalized].label : normalized;
}

function populateScenarioOptions() {
  const previous = controls.scenarioSelect.value;
  const source = cachedScenarios.length ? cachedScenarios : manualScenarioFallback.map((id) => ({ id, label: scenarioLabel(id) }));
  const seen = new Set();
  const options = [];
  source.forEach((item) => {
    const id = selectText(item.id, '');
    if (!id || seen.has(id)) {
      return;
    }
    seen.add(id);
    options.push({ id, label: selectText(item.label, id) });
  });
  controls.scenarioSelect.innerHTML = options.map((item) => `<option value="${item.id}">${item.label}</option>`).join('');
  if (previous && seen.has(previous)) {
    controls.scenarioSelect.value = previous;
  } else if (options.length > 0) {
    controls.scenarioSelect.value = options[0].id;
  }
}

function populateIntentTemplates() {
  controls.intentTemplate.innerHTML = Object.keys(intentTemplates)
    .map((intentName) => `<option value="${intentName}">${intentName}</option>`)
    .join('');
  setIntentEditor(controls.intentTemplate.value || 'acquire_target', true);
}

function setIntentEditor(intentName, preservePreview) {
  const template = intentTemplates[intentName] || intentTemplates.acquire_target;
  controls.intentJson.value = JSON.stringify(template, null, 2);
  if (!preservePreview) {
    clearPreview();
  }
}

function clearPreview(message = 'Preview required.') {
  localPreview = null;
  stateEls.previewStatus.textContent = message;
  stateEls.previewReadiness.textContent = 'No preview yet.';
  stateEls.previewActivity.textContent = 'No preview yet.';
  stateEls.previewPayload.textContent = '{}';
  controls.dispatchIntent.disabled = true;
}

function readIntentBodyFromEditor() {
  const parsed = JSON.parse(controls.intentJson.value || '{}');
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Intent body must be a JSON object.');
  }
  const intentName = selectText(parsed.intent, '');
  if (!intentName) {
    throw new Error('Intent body must include an intent field.');
  }
  const args = parsed.args && typeof parsed.args === 'object' && !Array.isArray(parsed.args) ? parsed.args : {};
  return { intent: intentName, args };
}

function previewFromState(state) {
  const decision = state.decision || {};
  if (decision.last_preview_valid) {
    return {
      generated_utc: decision.last_preview_timestamp_utc || '',
      intent: selectText(decision.last_preview_payload && decision.last_preview_payload.intent, ''),
      payload: decision.last_preview_payload || {},
      readiness: decision.last_preview_readiness || {},
      expected_boundary_activity: Array.isArray(decision.last_preview_expected_activity) ? decision.last_preview_expected_activity : [],
      ready_to_dispatch: Boolean(decision.last_preview_readiness && decision.last_preview_readiness.ready_to_dispatch),
      contract_valid: true
    };
  }
  if (decision.last_preview_error) {
    return {
      intent: '',
      payload: {},
      readiness: {},
      expected_boundary_activity: [],
      ready_to_dispatch: false,
      contract_valid: false,
      error: decision.last_preview_error
    };
  }
  return null;
}

function renderPreview(state) {
  const preview = localPreview || previewFromState(state);
  const controlsState = state.controls || {};
  if (!preview) {
    clearPreview('Preview required.');
    return;
  }
  if (preview.error) {
    stateEls.previewStatus.textContent = `Preview failed: ${preview.error}`;
    stateEls.previewReadiness.textContent = 'Preview is invalid.';
    stateEls.previewActivity.textContent = 'No boundary activity because validation failed.';
    stateEls.previewPayload.textContent = '{}';
    controls.dispatchIntent.disabled = true;
    return;
  }
  const readiness = preview.readiness || {};
  const missing = Array.isArray(readiness.missing_keys) ? readiness.missing_keys : [];
  stateEls.previewStatus.textContent = `${preview.intent || 'intent'} ${preview.ready_to_dispatch ? 'ready' : 'blocked'}`;
  stateEls.previewReadiness.textContent = missing.length ? `Missing: ${missing.join(', ')}` : 'Ready to dispatch.';
  stateEls.previewActivity.textContent = Array.isArray(preview.expected_boundary_activity) && preview.expected_boundary_activity.length
    ? preview.expected_boundary_activity.join(', ')
    : 'No specific activity listed.';
  stateEls.previewPayload.textContent = JSON.stringify(preview.payload || {}, null, 2);
  controls.dispatchIntent.disabled = !(controlsState.can_dispatch_intent && preview.contract_valid && preview.ready_to_dispatch);
}

function renderAdvancedLanes(state) {
  const perception = state.perception || {};
  const belief = state.belief || {};
  const decision = state.decision || {};
  const outcome = state.outcome || {};
  renderLane(stateEls.perceptionLane, [
    { label: 'Detection Topic', value: perception.detection_topic_seen ? 'live' : 'waiting' },
    { label: 'Target Visible', value: perception.target_visible_now ? 'yes' : 'no' },
    { label: 'Visible Ratio', value: `${Number(perception.target_visible_ratio || 0).toFixed(2)}` },
    { label: 'Detection', value: formatPoint(perception.latest_detection_world) },
    { label: 'Truth Target', value: formatPoint(perception.latest_truth_target_world) },
    { label: 'Truth Status', value: selectText(perception.truth_status, 'truth unavailable') }
  ]);
  renderLane(stateEls.beliefLane, [
    { label: 'Robot Pose', value: formatPose(belief.latest_robot_pose) },
    { label: 'Goal Pose', value: formatPose(belief.latest_goal_pose) },
    { label: 'Distance', value: formatMeters(belief.latest_target_distance_m) },
    { label: 'Trend', value: selectText(belief.distance_trend, 'unknown') },
    { label: 'Phase', value: selectText(belief.phase, 'n/a') },
    { label: 'Target / Transition', value: `${selectText(belief.target_id, 'n/a')} / ${belief.target_transition_active ? 'active' : 'steady'}` }
  ]);
  renderLane(stateEls.decisionLane, [
    { label: 'Last Intent', value: selectText(decision.last_intent, 'none') },
    { label: 'Intent Time', value: selectText(decision.last_intent_timestamp_utc, 'n/a') },
    { label: 'Preview Valid', value: decision.last_preview_valid ? 'yes' : 'no' },
    { label: 'Preview Time', value: selectText(decision.last_preview_timestamp_utc, 'n/a') },
    { label: 'Preview Error', value: selectText(decision.last_preview_error, 'none') },
    { label: 'Available Intents', value: Array.isArray(decision.available_intents) ? decision.available_intents.join(', ') : 'n/a' }
  ]);
  renderLane(stateEls.outcomeLane, [
    { label: 'Last Feedback', value: selectText(outcome.last_feedback, 'none') },
    { label: 'Last Result', value: selectText(outcome.last_result, 'none') },
    { label: 'Feedback Recent', value: outcome.feedback_recent ? 'yes' : 'no' },
    { label: 'Nav Goal Recent', value: outcome.nav_goal_recent ? 'yes' : 'no' },
    { label: 'cmd_vel Recent', value: outcome.cmd_vel_recent ? 'yes' : 'no' },
    { label: 'Motion Evidence', value: outcome.motion_evidence ? 'yes' : 'no' }
  ]);
}

function renderControlDetail(state) {
  stateEls.controlModeDetail.textContent = selectText(state.control_mode, 'n/a');
  stateEls.warmServices.textContent = selectText(state.warm_services_status, 'unknown');
  stateEls.composeProject.textContent = selectText(state.compose_project, 'n/a');
  stateEls.operatorViewBackend.textContent = selectText(state.operator_view_backend, 'n/a');
  stateEls.operatorViewReady.textContent = state.operator_view_ready
    ? selectText(state.operator_view_status, 'ready')
    : selectText(state.operator_view_failure_class || state.operator_view_status, 'waiting');
  stateEls.worldStreamReady.textContent = state.world_stream_ready ? 'ready' : selectText(state.world_stream_failure_class, 'waiting');
  stateEls.truthAlignment.textContent = state.truth_alignment_ok ? 'aligned' : selectText(state.truth_failure_class, 'waiting');
  stateEls.motionEvidence.textContent = state.motion_evidence ? 'present' : 'waiting';
  stateEls.operatorFootnote.textContent = state.control_plane_ready
    ? (state.operator_view_ready
      ? 'Controls are live. Open Xpra for the recommended live view.'
      : 'Controls are live. Xpra is starting or unavailable; check Live View status.')
    : selectText(state.control_plane_error, 'Read-only fallback mode.');
}

function renderShadowBrain(state) {
  const supervisor = state.llm_supervisor || {};
  const latest = supervisor.latest_decision || {};
  const preview = supervisor.preview || {};
  const status = selectText(supervisor.status, 'disabled');
  stateEls.shadowDetailStatus.textContent = status;
  stateEls.shadowDetailProvider.textContent = selectText(supervisor.provider, 'n/a');
  stateEls.shadowDetailModel.textContent = selectText(supervisor.model, 'n/a');
  stateEls.shadowDetailStateHash.textContent = selectText(supervisor.state_hash, 'n/a');
  stateEls.shadowDetailPreview.textContent = preview.ready_to_dispatch
    ? 'ready_to_dispatch'
    : (Array.isArray(preview.missing_keys) && preview.missing_keys.length ? `blocked: ${preview.missing_keys.join(', ')}` : status);
  stateEls.shadowDetailHistoryPath.textContent = selectText(supervisor.history_path, 'n/a');
  stateEls.shadowDetailSuppression.textContent = selectText(supervisor.suppression_reason, 'No suppression active.');
  const history = Array.isArray(supervisor.recent_history) ? supervisor.recent_history : [];
  stateEls.shadowHistoryList.innerHTML = history.length
    ? history.slice().reverse().map((entry) => {
      const when = selectText(entry.generated_utc, 'unknown time');
      const label = selectText(entry.event_type, 'event');
      const detail = selectText(entry.intent || entry.status, '');
      return `<li class="watch-item">${when} - ${label}${detail ? ` - ${detail}` : ''}</li>`;
    }).join('')
    : `<li class="watch-item">${selectText(latest.rationale_short, 'No LLM runtime history yet.')}</li>`;
}

function normalizeLogMessage(message) {
  const text = selectText(message, '').trim();
  if (!text) {
    return '';
  }
  const replacements = [
    [/^LLM emitted search_for_target.*$/i, 'LLM: search'],
    [/^LLM emitted acquire_target.*$/i, 'LLM: acquire'],
    [/^LLM emitted plan_to_target.*$/i, 'LLM: plan'],
    [/^LLM emitted track_target.*$/i, 'LLM: track'],
    [/^LLM emitted abort.*$/i, 'LLM: abort'],
    [/^LLM emitted safe_stop.*$/i, 'LLM: safe stop'],
    [/^Proof target spawned.*$/i, 'Target spawned'],
    [/^.*scenario started\.$/i, 'Scenario started'],
    [/^Robot began search turn\.$/i, 'Robot: search turn'],
    [/^Target visible and locked\.$/i, 'Target locked'],
    [/^Robot began move-to-target\.$/i, 'Robot: moving'],
    [/^Motion progress observed\.$/i, 'Progress observed'],
    [/^Proof completed successfully\.$/i, 'Proof completed'],
    [/^Proof failed\.$/i, 'Proof failed'],
    [/^nav goal accepted by nav2$/i, 'Nav active'],
    [/^navigation goal accepted$/i, 'Nav active'],
    [/^move-to-target active$/i, 'Robot: moving'],
    [/^Starting environment\.$/i, 'Starting environment'],
    [/^Stopping environment\.$/i, 'Stopping environment'],
    [/^Stopping scenario\.$/i, 'Stopping scenario'],
    [/^Resetting sim\.$/i, 'Resetting sim'],
    [/^Refreshing environment\.$/i, 'Refreshing environment']
  ];
  for (const [pattern, replacement] of replacements) {
    if (pattern.test(text)) {
      return replacement;
    }
  }
  return text;
}

function eventKey(entry) {
  return `${selectText(entry.timestamp_utc, '')}|${selectText(entry.message, '')}`;
}

function buildLogEvents(state) {
  const proofVerdict = state.proof_verdict || {};
  const supervisor = state.llm_supervisor || {};
  const latestDecision = (state.latest_proof_decision && Object.keys(state.latest_proof_decision).length)
    ? state.latest_proof_decision
    : (supervisor.latest_decision || {});
  const latestFeedback = selectText(state.latest_proof_feedback || state.last_feedback, '');
  const rawEvents = Array.isArray(state.recent_operator_events) ? state.recent_operator_events : [];
  const events = [];

  rawEvents.forEach((entry) => {
    const message = normalizeLogMessage(entry && entry.message);
    if (!message) {
      return;
    }
    events.push({
      timestamp_utc: selectText(entry.timestamp_utc, ''),
      message
    });
  });

  if (latestDecision && latestDecision.intent) {
    events.push({
      timestamp_utc: selectText(latestDecision.generated_utc || latestDecision.timestamp_utc, ''),
      message: `LLM: ${shortIntent(latestDecision.intent)}`
    });
  }

  if (latestFeedback) {
    events.push({
      timestamp_utc: selectText(state.last_feedback_timestamp_utc, ''),
      message: normalizeLogMessage(latestFeedback)
    });
  }

  if (proofVerdict && Object.keys(proofVerdict).length) {
    events.push({
      timestamp_utc: selectText(proofVerdict.generated_utc, ''),
      message: proofVerdict.pass ? 'Proof completed' : 'Proof failed'
    });
  }

  const deduped = [];
  const seen = new Set();
  events
    .filter((entry) => entry.message)
    .sort((a, b) => String(a.timestamp_utc).localeCompare(String(b.timestamp_utc)))
    .forEach((entry) => {
      const key = eventKey(entry);
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      deduped.push({ ...entry, key });
    });
  return deduped.slice(-40);
}

function markLogSeen(events) {
  uiState.logUnreadCount = 0;
  uiState.lastSeenLogKey = events.length ? events[events.length - 1].key : '';
}

function setControlsDrawerOpen(isOpen, persist = true) {
  uiState.controlsDrawerOpen = Boolean(isOpen);
  if (persist) {
    writeBoolStorage(storageKeys.controlsDrawerOpen, uiState.controlsDrawerOpen);
  }
  syncDrawerState();
}

function setLogDrawerOpen(isOpen, persist = true, events = []) {
  uiState.logDrawerOpen = Boolean(isOpen);
  if (persist) {
    writeBoolStorage(storageKeys.logDrawerOpen, uiState.logDrawerOpen);
  }
  if (uiState.logDrawerOpen) {
    markLogSeen(events);
  }
  syncDrawerState();
}

function syncDrawerState() {
  stateEls.controlsDrawer.dataset.open = uiState.controlsDrawerOpen ? 'true' : 'false';
  stateEls.controlsDrawer.setAttribute('aria-hidden', uiState.controlsDrawerOpen ? 'false' : 'true');
  stateEls.toggleControls.setAttribute('aria-expanded', uiState.controlsDrawerOpen ? 'true' : 'false');
  stateEls.toggleControls.classList.toggle('is-active', uiState.controlsDrawerOpen);
  stateEls.toggleControlsState.textContent = uiState.controlsDrawerOpen ? 'hide' : 'show';

  stateEls.logDrawer.dataset.open = uiState.logDrawerOpen ? 'true' : 'false';
  stateEls.logDrawer.setAttribute('aria-hidden', uiState.logDrawerOpen ? 'false' : 'true');
  stateEls.toggleLog.setAttribute('aria-expanded', uiState.logDrawerOpen ? 'true' : 'false');
  stateEls.toggleLog.classList.toggle('is-active', uiState.logDrawerOpen);

  document.body.classList.toggle('drawer-open', uiState.controlsDrawerOpen || uiState.logDrawerOpen);
}

function updateLogState(state, events) {
  const latestKey = events.length ? events[events.length - 1].key : '';
  if (!uiState.logPrimed) {
    uiState.logPrimed = true;
    if (uiState.logDrawerOpen) {
      markLogSeen(events);
    } else {
      uiState.lastSeenLogKey = latestKey;
      uiState.logUnreadCount = 0;
    }
  } else if (uiState.logDrawerOpen) {
    markLogSeen(events);
  } else if (latestKey) {
    const lastSeenIndex = uiState.lastSeenLogKey ? events.findIndex((entry) => entry.key === uiState.lastSeenLogKey) : -1;
    if (lastSeenIndex >= 0) {
      uiState.logUnreadCount = Math.max(events.length - lastSeenIndex - 1, 0);
    } else if (uiState.lastSeenLogKey) {
      uiState.logUnreadCount = 1;
    } else {
      uiState.logUnreadCount = 0;
      uiState.lastSeenLogKey = latestKey;
    }
  } else {
    uiState.logUnreadCount = 0;
  }

  const proofState = selectText(state.proof_state, 'waiting');
  stateEls.toggleLogState.textContent = proofState;
  stateEls.runLogChip.textContent = proofState;

  const hasUnread = uiState.logUnreadCount > 0;
  stateEls.toggleLogCount.textContent = String(uiState.logUnreadCount);
  stateEls.toggleLogCount.classList.toggle('hidden', !hasUnread);
  stateEls.toggleLogDot.classList.toggle('hidden', !hasUnread);
}

function maybeAutoOpenDrawers(state, events) {
  const scenarioStarted = lastRenderedState
    && lastRenderedState.scenario_state !== 'running'
    && state.scenario_state === 'running'
    && selectText(state.active_scenario, '');
  if (scenarioStarted && uiState.controlsDrawerOpen) {
    setControlsDrawerOpen(false, true);
  }

  const hasFailure = state.environment_state === 'error' || state.scenario_state === 'error' || state.proof_state === 'failed';
  if (!hasFailure) {
    return;
  }
  const failureKey = [
    selectText(state.session_id, ''),
    selectText(state.environment_state, ''),
    selectText(state.scenario_state, ''),
    selectText(state.proof_state, ''),
    events.length ? events[events.length - 1].key : selectText(state.last_result || state.latest_operator_event, '')
  ].join('|');
  if (failureKey && failureKey !== uiState.lastFailureAutoOpenKey) {
    uiState.lastFailureAutoOpenKey = failureKey;
    setLogDrawerOpen(true, true, events);
  }
}

function renderTopRail(state) {
  const envState = selectText(state.environment_state, 'stopped');
  const activeScenarioId = selectText(state.active_scenario, '');
  stateEls.environmentState.textContent = envState;
  stateEls.activeScenario.textContent = activeScenarioId ? scenarioLabel(activeScenarioId) : 'idle';
  stateEls.proofState.textContent = selectText(state.proof_state, 'waiting');
  stateEls.sessionId.textContent = envState === 'stopped' ? 'n/a' : selectText(state.session_id, 'n/a');
}

function renderDemoButtons(state, completed) {
  const controlsState = state.controls || {};
  const activeScenario = selectText(state.active_scenario, '');
  const canRunScenario = Boolean(controlsState.can_run_scenario);

  const featured = demoFlow[0];
  const featuredRunning = activeScenario === featured.id && state.scenario_state === 'running';
  const featuredComplete = completed.has(featured.id);

  const supportButtons = demoFlow.slice(1).map((item) => {
    const running = activeScenario === item.id && state.scenario_state === 'running';
    const complete = completed.has(item.id);
    return `
      <button
        class="demo-button secondary ${running ? 'is-running' : ''} ${complete ? 'is-complete' : ''}"
        type="button"
        data-demo-run="${item.id}"
        data-testid="btn-demo-${item.id}"
        ${canRunScenario ? '' : 'disabled'}>
        <span class="demo-name">${item.label}</span>
        <span class="demo-state">${running ? 'running' : (complete ? 'done' : 'ready')}</span>
      </button>
    `;
  }).join('');

  stateEls.demoList.innerHTML = `
    <button
      class="demo-button primary ${featuredRunning ? 'is-running' : ''} ${featuredComplete ? 'is-complete' : ''}"
      type="button"
      data-demo-run="${featured.id}"
      data-testid="btn-demo-${featured.id}"
      ${canRunScenario ? '' : 'disabled'}>
      <span class="demo-name">${featured.label}</span>
      <span class="demo-state">${featuredRunning ? 'running' : (featuredComplete ? 'done' : 'featured')}</span>
    </button>
    <div class="demo-grid">
      ${supportButtons}
    </div>
  `;
}

function renderControls(state, completed) {
  const controlsState = state.controls || {};
  controls.startEnv.disabled = !controlsState.can_start;
  controls.stop.disabled = !controlsState.can_stop;
  controls.refresh.disabled = !controlsState.can_refresh;
  controls.resetSim.disabled = !controlsState.can_reset_sim;
  controls.stopScenario.disabled = !controlsState.can_stop_scenario;
  controls.stopScenario.hidden = !controlsState.can_stop_scenario;
  controls.runScenario.disabled = !controlsState.can_run_scenario;
  controls.scenarioSelect.disabled = !controlsState.can_run_scenario;
  controls.acquireTarget.disabled = !controlsState.can_issue_intent;
  controls.planToTarget.disabled = !controlsState.can_issue_intent;
  controls.trackTarget.disabled = !controlsState.can_issue_intent;
  controls.abort.disabled = !controlsState.can_issue_intent;
  controls.safeStop.disabled = !controlsState.can_issue_intent;
  controls.previewIntent.disabled = !controlsState.can_preview_intent;

  renderDemoButtons(state, completed);
}

function renderRunLog(events) {
  stateEls.runLogList.innerHTML = events.length
    ? events.slice().reverse().map((entry) => {
      const when = summarizeTime(entry.timestamp_utc);
      return `
        <li class="run-log-entry">
          <strong>${selectText(entry.message, 'event')}</strong>
          <span>${when || 'awaiting timestamp'}</span>
        </li>
      `;
    }).join('')
    : '<li class="run-log-entry"><strong>No run events yet.</strong><span>waiting</span></li>';
}

function renderCameraState(state) {
  const sessionActive = Boolean(state.session_id) && state.environment_state !== 'stopped';
  const livePaths = state.live_paths || {};
  if (sessionActive) {
    stampImage(stateEls.worldImage, livePaths.world_stream || 'live/world_stream.jpg');
    stampImage(stateEls.debugImage, livePaths.yolo_debug || 'live/yolo_debug.jpg');
    stampImage(stateEls.rawImage, livePaths.raw_camera || 'live/raw_camera.jpg');
    stampImage(stateEls.topdownImage, livePaths.topdown_telemetry || 'live/topdown_telemetry.jpg');
  } else {
    stateEls.worldImage.src = placeholderImage();
    stateEls.debugImage.src = placeholderImage();
    stateEls.rawImage.src = placeholderImage();
    stateEls.topdownImage.src = placeholderImage();
  }

  if (state.operator_view_url) {
    stateEls.operatorViewLink.classList.remove('hidden');
    stateEls.operatorViewLink.href = state.operator_view_url;
    stateEls.operatorViewLink.textContent = 'Open Xpra';
  } else {
    stateEls.operatorViewLink.classList.add('hidden');
    stateEls.operatorViewLink.removeAttribute('href');
  }

  if (state.world_stream_url) {
    stateEls.worldLink.classList.remove('hidden');
    stateEls.worldLink.href = state.world_stream_url;
    stateEls.worldLink.textContent = state.operator_view_url ? 'Open Legacy Stream' : 'Open Stream';
  } else {
    stateEls.worldLink.classList.add('hidden');
    stateEls.worldLink.removeAttribute('href');
  }

  if (!sessionActive) {
    stateEls.debugVisualStatus.textContent = 'terminator view';
    return;
  }

  const proofState = selectText(state.proof_state, 'waiting');
  const perception = state.perception || {};
  if (proofState === 'searching') {
    stateEls.debugVisualStatus.textContent = 'searching';
  } else if (proofState === 'target_locked') {
    stateEls.debugVisualStatus.textContent = 'target locked';
  } else if (proofState === 'moving') {
    stateEls.debugVisualStatus.textContent = 'moving';
  } else if (proofState === 'completed') {
    stateEls.debugVisualStatus.textContent = 'completed';
  } else if (proofState === 'failed') {
    stateEls.debugVisualStatus.textContent = 'failed';
  } else {
    stateEls.debugVisualStatus.textContent = perception.target_visible_now ? 'target visible' : 'terminator view';
  }
}

function renderState(state) {
  const sessionChanged = lastRenderedState && lastRenderedState.session_id !== state.session_id;
  if (sessionChanged) {
    clearPreview('Preview cleared because the session changed.');
    uiState.lastSeenLogKey = '';
    uiState.logUnreadCount = 0;
    uiState.logPrimed = false;
  }

  const envState = selectText(state.environment_state, 'stopped');
  const completed = envState === 'stopped' ? new Set() : trackScenarioProgress(state);
  const events = buildLogEvents(state);

  renderTopRail(state);
  renderControls(state, completed);
  renderRunLog(events);
  renderControlDetail(state);
  renderShadowBrain(state);
  renderCameraState(state);
  renderAdvancedLanes(state);
  renderPreview(state);

  maybeAutoOpenDrawers(state, events);
  updateLogState(state, events);
  syncDrawerState();
  lastRenderedState = JSON.parse(JSON.stringify(state));
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: 'no-store' });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || payload.message || `Request failed: ${response.status}`);
  }
  return payload;
}

async function postJson(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error || payload.message || `Request failed: ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

async function runScenarioById(scenarioId) {
  if (!scenarioId) {
    throw new Error('Missing scenario id.');
  }
  await postJson('/api/scenario/run', { scenario_id: scenarioId });
  await refreshState();
}

async function refreshApiState() {
  const [state, scenarioCatalog] = await Promise.all([
    fetchJson('/api/state'),
    fetchJson('/api/scenarios').catch(() => ({ scenarios: [] }))
  ]);
  apiMode = true;
  if (Array.isArray(scenarioCatalog.scenarios) && scenarioCatalog.scenarios.length) {
    cachedScenarios = scenarioCatalog.scenarios;
    populateScenarioOptions();
  }
  return state;
}

function refreshLegacyState(error) {
  apiMode = false;
  const base = lastRenderedState ? JSON.parse(JSON.stringify(lastRenderedState)) : {
    control_mode: 'read_only',
    control_plane_ready: false,
    control_plane_error: 'Dashboard API unavailable.',
    warm_services_ready: false,
    warm_services_status: 'unknown',
    environment_state: 'stopped',
    environment_message: 'Dashboard API unavailable.',
    scenario_state: 'idle',
    scenario_message: '',
    session_id: '',
    compose_project: '',
    phase: 'stopped',
    target_id: '',
    target_transition_active: false,
    active_scenario: '',
    last_feedback: '',
    last_result: '',
    motion_evidence: false,
    operator_view_backend: 'xpra',
    operator_view_url: '',
    operator_view_ready: false,
    operator_view_status: 'disabled',
    operator_view_failure_class: '',
    world_stream_ready: false,
    truth_alignment_ok: false,
    live_paths: {},
    perception: {},
    belief: {},
    decision: {},
    outcome: {},
    llm_supervisor: {},
    proof_state: 'waiting',
    latest_operator_event: '',
    recent_operator_events: [],
    proof_verdict: {},
    latest_proof_decision: {},
    latest_proof_feedback: '',
    controls: {
      can_start: false,
      can_stop: false,
      can_refresh: true,
      can_reset_sim: false,
      can_run_scenario: false,
      can_stop_scenario: false,
      can_issue_intent: false,
      can_preview_intent: false,
      can_dispatch_intent: false
    }
  };
  base.control_plane_ready = false;
  base.control_mode = 'read_only';
  base.control_plane_error = String(error && error.message ? error.message : error || 'Dashboard API unavailable.');
  base.controls = {
    can_start: false,
    can_stop: false,
    can_refresh: true,
    can_reset_sim: false,
    can_run_scenario: false,
    can_stop_scenario: false,
    can_issue_intent: false,
    can_preview_intent: false,
    can_dispatch_intent: false
  };
  return base;
}

async function refreshState() {
  try {
    const state = await refreshApiState();
    renderState(state);
  } catch (error) {
    renderState(refreshLegacyState(error));
  }
}

stateEls.toggleControls.addEventListener('click', () => {
  setControlsDrawerOpen(!uiState.controlsDrawerOpen, true);
});

stateEls.toggleLog.addEventListener('click', () => {
  const events = buildLogEvents(lastRenderedState || {});
  setLogDrawerOpen(!uiState.logDrawerOpen, true, events);
});

stateEls.closeControls.addEventListener('click', () => {
  setControlsDrawerOpen(false, true);
});

stateEls.closeLog.addEventListener('click', () => {
  const events = buildLogEvents(lastRenderedState || {});
  setLogDrawerOpen(false, true, events);
});

window.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') {
    return;
  }
  if (uiState.logDrawerOpen) {
    setLogDrawerOpen(false, true, buildLogEvents(lastRenderedState || {}));
  }
  if (uiState.controlsDrawerOpen) {
    setControlsDrawerOpen(false, true);
  }
});

controls.startEnv.addEventListener('click', async () => {
  await postJson('/api/env/start', {});
  await refreshState();
});

controls.refresh.addEventListener('click', async () => {
  await postJson('/api/env/refresh', {});
  await refreshState();
});

controls.resetSim.addEventListener('click', async () => {
  await postJson('/api/sim/reset', {});
  await refreshState();
});

controls.stopScenario.addEventListener('click', async () => {
  await postJson('/api/scenario/stop', {});
  await refreshState();
});

controls.stop.addEventListener('click', async () => {
  await postJson('/api/env/stop', {});
  await refreshState();
});

controls.runScenario.addEventListener('click', async () => {
  await runScenarioById(controls.scenarioSelect.value);
});

stateEls.demoList.addEventListener('click', async (event) => {
  const target = event.target instanceof HTMLElement ? event.target.closest('[data-demo-run]') : null;
  if (!target) {
    return;
  }
  const scenarioId = target.getAttribute('data-demo-run') || '';
  if (scenarioId) {
    await runScenarioById(scenarioId);
  }
});

controls.intentTemplate.addEventListener('change', () => {
  setIntentEditor(controls.intentTemplate.value, false);
});

controls.intentJson.addEventListener('input', () => {
  clearPreview('Preview required after edits.');
});

controls.previewIntent.addEventListener('click', async () => {
  try {
    const body = readIntentBodyFromEditor();
    const payload = await postJson('/api/intents/preview', body);
    localPreview = payload.preview || null;
    renderPreview(lastRenderedState || refreshLegacyState('Dashboard API unavailable.'));
  } catch (error) {
    localPreview = { error: String(error.message || error) };
    renderPreview(lastRenderedState || refreshLegacyState('Dashboard API unavailable.'));
  }
});

controls.dispatchIntent.addEventListener('click', async () => {
  const body = readIntentBodyFromEditor();
  await postJson('/api/intents/dispatch', body);
  await refreshState();
});

async function fireQuickIntent(intentName, args) {
  await postJson(`/api/intents/${intentName}`, args);
  await refreshState();
}

controls.acquireTarget.addEventListener('click', async () => {
  await fireQuickIntent('acquire_target', { target_class: controls.targetClass.value || 'ball' });
});

controls.planToTarget.addEventListener('click', async () => {
  await fireQuickIntent('plan_to_target', { approach_distance_m: Number(controls.approachDistance.value || 0.25) });
});

controls.trackTarget.addEventListener('click', async () => {
  await fireQuickIntent('track_target', {});
});

controls.abort.addEventListener('click', async () => {
  await fireQuickIntent('abort', {});
});

controls.safeStop.addEventListener('click', async () => {
  await fireQuickIntent('safe_stop', {});
});

populateScenarioOptions();
populateIntentTemplates();
clearPreview();
syncDrawerState();
refreshState();
window.setInterval(refreshState, 1000);
