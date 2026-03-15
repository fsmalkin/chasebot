const stateEls = {
  apiMode: document.getElementById('api-mode'),
  environmentState: document.getElementById('environment-state'),
  activeScenario: document.getElementById('active-scenario'),
  proofState: document.getElementById('proof-state'),
  sessionId: document.getElementById('session-id'),
  environmentChip: document.getElementById('environment-chip'),
  environmentHeadline: document.getElementById('environment-headline'),
  environmentCopy: document.getElementById('environment-copy'),
  proofLiveChip: document.getElementById('proof-live-chip'),
  proofStageValue: document.getElementById('proof-stage-value'),
  proofStageCopy: document.getElementById('proof-stage-copy'),
  proofActionValue: document.getElementById('proof-action-value'),
  proofActionCopy: document.getElementById('proof-action-copy'),
  proofFeedbackValue: document.getElementById('proof-feedback-value'),
  proofFeedbackCopy: document.getElementById('proof-feedback-copy'),
  proofGuidance: document.getElementById('proof-guidance'),
  proofWarning: document.getElementById('proof-warning'),
  demoEmphasis: document.getElementById('demo-emphasis'),
  demoExpectation: document.getElementById('demo-expectation'),
  demoList: document.getElementById('demo-list'),
  operatorLog: document.getElementById('operator-log'),
  runLogChip: document.getElementById('run-log-chip'),
  runLogSummary: document.getElementById('run-log-summary'),
  runLogList: document.getElementById('run-log-list'),
  operatorFootnote: document.getElementById('operator-footnote'),
  debugVisualStatus: document.getElementById('debug-visual-status'),
  worldLink: document.getElementById('world-link'),
  worldImage: document.getElementById('world-image'),
  rawImage: document.getElementById('raw-image'),
  topdownImage: document.getElementById('topdown-image'),
  debugImage: document.getElementById('debug-image'),
  controlModeDetail: document.getElementById('control-mode-detail'),
  warmServices: document.getElementById('warm-services'),
  composeProject: document.getElementById('compose-project'),
  worldStreamReady: document.getElementById('world-stream-ready'),
  truthAlignment: document.getElementById('truth-alignment'),
  motionEvidence: document.getElementById('motion-evidence'),
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
  { id: 'llm_turn_then_go_proof', label: 'LLM Turn + Go', copy: 'Primary browser proof. The robot should turn until it sees the ball, then move toward it while the run log shows the same LLM-driven steps.' },
  { id: 'm3_single_target', label: 'M3 Single Target', copy: 'Single-target motion demo with a visible ball and a clear approach path.' },
  { id: 'm3_center', label: 'M3 Center', copy: 'Centered visible-ball demo for a straightforward approach.' },
  { id: 'm3_left', label: 'M3 Left', copy: 'Left-offset visible-ball demo with an obvious leftward response.' },
  { id: 'm3_right', label: 'M3 Right', copy: 'Right-offset visible-ball demo with an obvious rightward response.' }
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

let apiMode = true;
let cachedScenarios = [];
let localPreview = null;
let lastRenderedState = null;
let pendingScenarioId = '';

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
    return 'none yet';
  }
  return value.replaceAll('_', ' ');
}

function summarizeTime(value) {
  const text = selectText(value, '');
  if (!text) {
    return '';
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
  const scenarioJustFinished = lastRenderedState && lastRenderedState.session_id === sessionId && lastRenderedState.scenario_state === 'running' && scenarioState !== 'running';
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

function recommendedScenarioId(completed) {
  const next = demoFlow.find((item) => !completed.has(item.id));
  return next ? next.id : 'llm_turn_then_go_proof';
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
  controls.intentTemplate.innerHTML = Object.keys(intentTemplates).map((intentName) => `<option value="${intentName}">${intentName}</option>`).join('');
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
  stateEls.previewStatus.textContent = `${preview.intent || 'intent'} preview ${preview.ready_to_dispatch ? 'ready' : 'blocked'}`;
  stateEls.previewReadiness.textContent = missing.length ? `Missing: ${missing.join(', ')}` : 'Ready to dispatch from the current session.';
  stateEls.previewActivity.textContent = Array.isArray(preview.expected_boundary_activity) && preview.expected_boundary_activity.length ? preview.expected_boundary_activity.join(', ') : 'No specific activity listed.';
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
    { label: 'Target Visible Now', value: perception.target_visible_now ? 'yes' : 'no' },
    { label: 'Target Visible Ratio', value: `${Number(perception.target_visible_ratio || 0).toFixed(2)}` },
    { label: 'Latest Detection', value: formatPoint(perception.latest_detection_world) },
    { label: 'Truth Target', value: formatPoint(perception.latest_truth_target_world) },
    { label: 'Truth Status', value: selectText(perception.truth_status, 'truth unavailable') }
  ]);
  renderLane(stateEls.beliefLane, [
    { label: 'Robot Pose', value: formatPose(belief.latest_robot_pose) },
    { label: 'Goal Pose', value: formatPose(belief.latest_goal_pose) },
    { label: 'Distance', value: formatMeters(belief.latest_target_distance_m) },
    { label: 'Distance Trend', value: selectText(belief.distance_trend, 'unknown') },
    { label: 'Phase', value: selectText(belief.phase, 'n/a') },
    { label: 'Target / Transition', value: `${selectText(belief.target_id, 'n/a')} / ${belief.target_transition_active ? 'active' : 'steady'}` }
  ]);
  renderLane(stateEls.decisionLane, [
    { label: 'Last Intent', value: selectText(decision.last_intent, 'none') },
    { label: 'Last Intent At', value: selectText(decision.last_intent_timestamp_utc, 'n/a') },
    { label: 'Last Preview Valid', value: decision.last_preview_valid ? 'yes' : 'no' },
    { label: 'Preview Generated', value: selectText(decision.last_preview_timestamp_utc, 'n/a') },
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

function demoExpectationText(state, recommendedId) {
  const activeScenario = selectText(state.active_scenario, '');
  if (activeScenario === 'llm_turn_then_go_proof' && state.scenario_state === 'running') {
    return 'Watch the robot turn first, then watch the YOLO debug view lock the ball, then watch the robot move toward it.';
  }
  if (activeScenario && demoMetaById[activeScenario]) {
    return demoMetaById[activeScenario].copy;
  }
  const recommended = demoMetaById[recommendedId];
  if (recommended) {
    return `Run ${recommended.label} next. The default browser flow starts with the LLM Turn + Go proof and then uses the visible-ball M3 demos.`;
  }
  return 'Use the visible-ball demos here for browser UAT. Multi-target rehearsal stays available under Advanced Controls.';
}
function renderDemoCards(state, completed, recommendedId) {
  const controlsState = state.controls || {};
  const activeScenario = selectText(state.active_scenario, '');
  const canRunScenario = Boolean(controlsState.can_run_scenario);
  const featured = demoFlow[0];
  const featuredRunning = activeScenario === featured.id && state.scenario_state === 'running';
  const featuredComplete = completed.has(featured.id);
  const featuredClasses = ['demo-card', 'is-recommended'];
  if (featuredRunning) {
    featuredClasses.push('is-running');
  }
  if (featuredComplete) {
    featuredClasses.push('is-complete');
  }

  const supportButtons = demoFlow.slice(1).map((item) => {
    const running = activeScenario === item.id && state.scenario_state === 'running';
    const complete = completed.has(item.id);
    const label = running ? `${item.label} (Running)` : (complete ? `${item.label} (Done)` : item.label);
    return `<button class="secondary" type="button" data-demo-run="${item.id}" data-testid="btn-demo-${item.id}" ${canRunScenario ? '' : 'disabled'}>${label}</button>`;
  }).join('');

  stateEls.demoList.innerHTML = `\n    <div class="${featuredClasses.join(' ')}">\n      <div class="demo-card-head">\n        <div>\n          <p class="demo-meta">${featuredRunning ? 'running' : (featuredComplete ? 'done' : (recommendedId === featured.id ? 'next' : 'featured'))}</p>\n          <h3 class="demo-card-title">${featured.label}</h3>\n        </div>\n        <button class="primary" type="button" data-demo-run="${featured.id}" data-testid="btn-demo-${featured.id}" ${canRunScenario ? '' : 'disabled'}>${featuredRunning ? 'Running' : 'Run LLM Proof'}</button>\n      </div>\n      <p class="demo-card-copy">${featured.copy}</p>\n    </div>\n    <div class="demo-shortcuts">\n      ${supportButtons}\n    </div>\n  `;
}

function renderEnvironmentPanel(state) {
  const envState = selectText(state.environment_state, 'stopped');
  const controlsState = state.controls || {};
  const activeScenario = selectText(state.active_scenario, '');
  const latestEvent = selectText(state.latest_operator_event || state.scenario_message || state.environment_message || state.last_result, 'Waiting for dashboard state.');
  stateEls.environmentChip.textContent = envState;
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

  if (!state.control_plane_ready) {
    stateEls.environmentHeadline.textContent = 'Waiting for Control Plane';
    stateEls.environmentCopy.textContent = selectText(state.control_plane_error, 'Warm services are still coming up. The dashboard can render before the control plane is ready.');
  } else if (envState === 'starting') {
    stateEls.environmentHeadline.textContent = 'Environment Starting';
    stateEls.environmentCopy.textContent = 'Wait for the world and YOLO panes to come alive before launching a demo.';
  } else if (activeScenario && state.scenario_state === 'running') {
    stateEls.environmentHeadline.textContent = scenarioLabel(activeScenario);
    stateEls.environmentCopy.textContent = activeScenario === 'llm_turn_then_go_proof' ? 'Watch for a visible turn-first, then lock, then move sequence.' : 'This visible-ball demo should be easy to verify from the world and YOLO panes.';
  } else if (envState === 'environment_ready') {
    stateEls.environmentHeadline.textContent = 'LLM Turn + Go Demo';
    stateEls.environmentCopy.textContent = 'The environment is ready. Run LLM Turn + Go first, then use the visible-ball M3 demos if you want supporting motion proofs.';
  } else if (envState === 'error') {
    stateEls.environmentHeadline.textContent = 'Environment Error';
    stateEls.environmentCopy.textContent = selectText(state.last_error || state.environment_message, 'The environment hit an error. Stop and restart the environment.');
  } else {
    stateEls.environmentHeadline.textContent = 'LLM Turn + Go Demo';
    stateEls.environmentCopy.textContent = 'Start the environment, run the LLM proof, then watch the robot turn until it sees the ball and move to it.';
  }

  stateEls.operatorLog.textContent = latestEvent;
}

function renderProofStatus(state) {
  const proofState = selectText(state.proof_state, 'waiting');
  const proofVerdict = state.proof_verdict || {};
  const supervisor = state.llm_supervisor || {};
  const latestDecision = (state.latest_proof_decision && Object.keys(state.latest_proof_decision).length) ? state.latest_proof_decision : (supervisor.latest_decision || {});
  const latestFeedback = selectText(state.latest_proof_feedback || state.last_feedback, '');
  const activeScenario = selectText(state.active_scenario, '');
  const preview = supervisor.preview || {};

  stateEls.proofLiveChip.textContent = proofState;
  stateEls.proofStageValue.textContent = proofState;

  if (proofState === 'searching') {
    stateEls.proofStageCopy.textContent = 'The robot should be turning in place while YOLO looks for the ball.';
  } else if (proofState === 'target_locked') {
    stateEls.proofStageCopy.textContent = 'The ball is locked. The next visible step should be a move toward it.';
  } else if (proofState === 'moving') {
    stateEls.proofStageCopy.textContent = 'The robot should be moving toward the visible ball now.';
  } else if (proofState === 'completed') {
    stateEls.proofStageCopy.textContent = 'The turn-then-go proof completed successfully.';
  } else if (proofState === 'failed') {
    stateEls.proofStageCopy.textContent = 'The proof failed. Use the run log below to see where it stalled.';
  } else if (activeScenario === 'llm_turn_then_go_proof' && state.scenario_state === 'running') {
    stateEls.proofStageCopy.textContent = 'The proof is running, but it has not advanced into search, lock, or move yet.';
  } else {
    stateEls.proofStageCopy.textContent = 'The proof has not started yet.';
  }

  if (latestDecision.intent) {
    stateEls.proofActionValue.textContent = prettifyIntent(latestDecision.intent);
    const expected = Array.isArray(latestDecision.expected_observations) ? latestDecision.expected_observations.join(', ') : '';
    stateEls.proofActionCopy.textContent = expected || selectText(latestDecision.rationale_short, 'Latest LLM action observed.');
  } else if (supervisor.status === 'blocked') {
    stateEls.proofActionValue.textContent = 'blocked';
    stateEls.proofActionCopy.textContent = selectText(latestDecision.rationale_short, 'The LLM has not produced a dispatchable step yet.');
  } else {
    stateEls.proofActionValue.textContent = 'none yet';
    stateEls.proofActionCopy.textContent = 'No LLM action observed yet.';
  }

  if (latestFeedback) {
    stateEls.proofFeedbackValue.textContent = latestFeedback;
    stateEls.proofFeedbackCopy.textContent = 'Latest robot-side feedback from the proof path.';
  } else if (state.motion_evidence) {
    stateEls.proofFeedbackValue.textContent = 'motion observed';
    stateEls.proofFeedbackCopy.textContent = 'Motion evidence is present in the current session.';
  } else if (preview.ready_to_dispatch) {
    stateEls.proofFeedbackValue.textContent = 'ready';
    stateEls.proofFeedbackCopy.textContent = 'The current state passes preview gating for the latest allowed action.';
  } else {
    stateEls.proofFeedbackValue.textContent = 'waiting';
    stateEls.proofFeedbackCopy.textContent = 'Waiting for the next meaningful robot update.';
  }

  if (proofState === 'searching') {
    stateEls.proofGuidance.textContent = 'Watch for the robot to rotate in the world view while the YOLO debug pane stays alert for the ball entering frame.';
  } else if (proofState === 'target_locked') {
    stateEls.proofGuidance.textContent = 'You should see the ball clearly marked in YOLO now. The next expected physical change is forward motion toward it.';
  } else if (proofState === 'moving') {
    stateEls.proofGuidance.textContent = 'The robot should already be committed to the ball. Confirm motion in the world view and a stable detection in YOLO.';
  } else if (proofState === 'completed') {
    stateEls.proofGuidance.textContent = 'This run completed. If the visuals matched the log, the bounded LLM proof behaved as intended.';
  } else if (proofState === 'failed') {
    stateEls.proofGuidance.textContent = 'This run failed. The run log below should show the last high-level proof step before it stopped progressing.';
  } else {
    stateEls.proofGuidance.textContent = 'When this is working, you should see: turn first, then ball lock in YOLO, then move toward the ball.';
  }

  if (proofVerdict && Object.keys(proofVerdict).length) {
    stateEls.proofWarning.textContent = proofVerdict.pass ? 'Latest verdict: passed.' : `Latest verdict: failed. ${selectText(proofVerdict.reason || proofVerdict.failure_reason, 'Check the run log and Advanced Controls.')}`;
  } else if (activeScenario === 'llm_turn_then_go_proof' && state.scenario_state === 'running' && proofState === 'waiting') {
    if (supervisor.status === 'blocked') {
      stateEls.proofWarning.textContent = `LLM currently blocked: ${selectText(latestDecision.rationale_short, 'provider or state gating has not produced a valid next step yet.')}`;
    } else {
      stateEls.proofWarning.textContent = 'The proof is running, but no visible LLM search/lock/move step has been recorded yet.';
    }
  } else if (supervisor.status === 'blocked' && latestDecision.rationale_short) {
    stateEls.proofWarning.textContent = `Shadow supervisor note: ${latestDecision.rationale_short}`;
  } else {
    stateEls.proofWarning.textContent = 'No proof warnings right now.';
  }
}

function renderRunLog(state) {
  const proofState = selectText(state.proof_state, 'waiting');
  const proofVerdict = state.proof_verdict || {};
  const supervisor = state.llm_supervisor || {};
  const activeScenario = selectText(state.active_scenario, '');
  const latestDecision = (state.latest_proof_decision && Object.keys(state.latest_proof_decision).length) ? state.latest_proof_decision : (supervisor.latest_decision || {});
  const latestFeedback = selectText(state.latest_proof_feedback || state.last_feedback, '');
  const rawEvents = Array.isArray(state.recent_operator_events) ? state.recent_operator_events : [];
  const events = rawEvents.slice();
  if (latestDecision.intent) {
    const text = `LLM emitted ${latestDecision.intent}.`;
    if (!events.some((entry) => selectText(entry.message, '') === text)) {
      events.push({ timestamp_utc: latestDecision.generated_utc || latestDecision.timestamp_utc || '', message: text });
    }
  }
  if (latestFeedback && !events.some((entry) => selectText(entry.message, '').includes(latestFeedback))) {
    events.push({ timestamp_utc: selectText(state.last_feedback_timestamp_utc, ''), message: latestFeedback });
  }
  if (proofVerdict && Object.keys(proofVerdict).length) {
    const verdictMessage = proofVerdict.pass ? 'Proof completed.' : 'Proof failed.';
    if (!events.some((entry) => selectText(entry.message, '') === verdictMessage)) {
      events.push({ timestamp_utc: selectText(proofVerdict.generated_utc, ''), message: verdictMessage });
    }
  }
  stateEls.runLogChip.textContent = proofState;
  if (proofVerdict && Object.keys(proofVerdict).length) {
    stateEls.runLogSummary.textContent = proofVerdict.pass ? 'Proof completed. The turn-then-go sequence passed in this session.' : 'Proof failed. Use the log below and Advanced Controls for the exact failure boundary.';
  } else if (latestDecision.intent) {
    stateEls.runLogSummary.textContent = `Latest LLM step: ${latestDecision.intent}. ${latestFeedback || 'Waiting for the next proof event.'}`;
  } else if (supervisor.status === 'blocked' && activeScenario === 'llm_turn_then_go_proof' && state.scenario_state === 'running') {
    stateEls.runLogSummary.textContent = `The proof is running, but the LLM is currently blocked: ${selectText(latestDecision.rationale_short, 'no valid bounded step yet.')}`;
  } else if (activeScenario === 'llm_turn_then_go_proof' && state.scenario_state === 'running') {
    stateEls.runLogSummary.textContent = 'The LLM proof is running. Watch the log for search, lock, and move steps.';
  } else {
    stateEls.runLogSummary.textContent = 'The log will show the high-level LLM and robot steps here.';
  }
  stateEls.runLogList.innerHTML = events.length ? events.slice().reverse().map((entry) => {
    const when = summarizeTime(entry.timestamp_utc);
    return `\n      <li class="run-log-entry">\n        <strong>${selectText(entry.message, 'event')}</strong>\n        <span>${when || 'awaiting timestamp'}</span>\n      </li>\n    `;
  }).join('') : '<li class="run-log-entry"><strong>No run events yet.</strong><span>waiting</span></li>';
}

function renderControlDetail(state) {
  stateEls.controlModeDetail.textContent = selectText(state.control_mode, 'n/a');
  stateEls.warmServices.textContent = selectText(state.warm_services_status, 'unknown');
  stateEls.composeProject.textContent = selectText(state.compose_project, 'n/a');
  stateEls.worldStreamReady.textContent = state.world_stream_ready ? 'ready' : selectText(state.world_stream_failure_class, 'waiting');
  stateEls.truthAlignment.textContent = state.truth_alignment_ok ? 'aligned' : selectText(state.truth_failure_class, 'waiting');
  stateEls.motionEvidence.textContent = state.motion_evidence ? 'present' : 'waiting';
  stateEls.operatorFootnote.textContent = state.control_plane_ready ? 'Controls are live. Advanced tools here are the same truthful backend state, just with more detail.' : selectText(state.control_plane_error, 'Read-only fallback mode disables controls until the API-backed service is reachable.');
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
  stateEls.shadowDetailPreview.textContent = preview.ready_to_dispatch ? 'ready_to_dispatch' : (Array.isArray(preview.missing_keys) && preview.missing_keys.length ? `blocked: ${preview.missing_keys.join(', ')}` : status);
  stateEls.shadowDetailHistoryPath.textContent = selectText(supervisor.history_path, 'n/a');
  stateEls.shadowDetailSuppression.textContent = selectText(supervisor.suppression_reason, 'No suppression active.');
  const history = Array.isArray(supervisor.recent_history) ? supervisor.recent_history : [];
  stateEls.shadowHistoryList.innerHTML = history.length ? history.slice().reverse().map((entry) => {
    const when = selectText(entry.generated_utc, 'unknown time');
    const label = selectText(entry.event_type, 'event');
    const detail = selectText(entry.intent || entry.status, '');
    return `<li class="watch-item">${when} - ${label}${detail ? ` - ${detail}` : ''}</li>`;
  }).join('') : `<li class="watch-item">${selectText(latest.rationale_short, 'No LLM runtime history yet.')}</li>`;
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
  if (state.world_stream_url) {
    stateEls.worldLink.style.display = 'inline';
    stateEls.worldLink.href = state.world_stream_url;
  } else {
    stateEls.worldLink.style.display = 'none';
    stateEls.worldLink.removeAttribute('href');
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
  }
  const envState = selectText(state.environment_state, 'stopped');
  const completed = envState === 'stopped' ? new Set() : trackScenarioProgress(state);
  const recommendedId = recommendedScenarioId(completed);
  const activeScenarioId = selectText(state.active_scenario, '');
  stateEls.apiMode.textContent = apiMode ? `${selectText(state.control_mode, 'control')} | ${state.warm_services_ready ? 'warm ready' : selectText(state.warm_services_status, 'warm pending')}` : 'Read-Only Fallback';
  stateEls.environmentState.textContent = envState;
  stateEls.activeScenario.textContent = activeScenarioId ? scenarioLabel(activeScenarioId) : 'idle';
  stateEls.proofState.textContent = selectText(state.proof_state, 'waiting');
  stateEls.sessionId.textContent = envState === 'stopped' ? 'n/a' : selectText(state.session_id, 'n/a');
  stateEls.demoEmphasis.textContent = activeScenarioId === 'llm_turn_then_go_proof' ? 'llm proof live' : (envState === 'environment_ready' ? 'featured demo' : 'featured');
  stateEls.demoExpectation.textContent = demoExpectationText(state, recommendedId);
  renderDemoCards(state, completed, recommendedId);
  renderEnvironmentPanel(state);
  renderProofStatus(state);
  renderRunLog(state);
  renderControlDetail(state);
  renderShadowBrain(state);
  renderCameraState(state);
  renderAdvancedLanes(state);
  renderPreview(state);
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
  stateEls.operatorLog.textContent = `Queueing ${scenarioLabel(scenarioId)}.`;
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

controls.startEnv.addEventListener('click', async () => {
  stateEls.operatorLog.textContent = 'Starting environment.';
  await postJson('/api/env/start', {});
  await refreshState();
});

controls.refresh.addEventListener('click', async () => {
  stateEls.operatorLog.textContent = 'Refreshing environment.';
  await postJson('/api/env/refresh', {});
  await refreshState();
});

controls.resetSim.addEventListener('click', async () => {
  stateEls.operatorLog.textContent = 'Resetting sim.';
  await postJson('/api/sim/reset', {});
  await refreshState();
});

controls.stopScenario.addEventListener('click', async () => {
  stateEls.operatorLog.textContent = 'Stopping scenario.';
  await postJson('/api/scenario/stop', {});
  await refreshState();
});

controls.stop.addEventListener('click', async () => {
  stateEls.operatorLog.textContent = 'Stopping environment.';
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
refreshState();
window.setInterval(refreshState, 1000);
