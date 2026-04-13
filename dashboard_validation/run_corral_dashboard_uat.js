const fs = require('fs');
const path = require('path');
const { chromium } = require('@playwright/test');

const BASE_URL = process.env.DASHBOARD_URL || 'http://127.0.0.1:8860';
const OUTPUT_ROOT = process.env.CORRAL_DASHBOARD_UAT_ROOT
  || 'D:/dev/chasecar/artifacts/session/20260412T_CORRAL_DASHBOARD_UAT';
const VISUAL_ROOT = path.join(OUTPUT_ROOT, 'dashboard_visual_clean');
const REQUIRED_GREEN_RUNS = Math.max(Number.parseInt(process.env.CORRAL_DASHBOARD_UAT_RUNS || '3', 10) || 3, 1);

async function getState(page) {
  const response = await page.request.get(`${BASE_URL}/api/state`);
  if (!response.ok()) {
    throw new Error(`GET /api/state failed with ${response.status()}`);
  }
  return await response.json();
}

async function waitFor(page, predicate, timeoutMs, label, onTick) {
  const deadline = Date.now() + timeoutMs;
  let lastState = null;
  while (Date.now() < deadline) {
    lastState = await getState(page);
    if (onTick) {
      await onTick(lastState);
    }
    if (predicate(lastState)) {
      return lastState;
    }
    await page.waitForTimeout(1000);
  }
  throw new Error(`${label}\nLast state: ${JSON.stringify(lastState, null, 2)}`);
}

async function postJson(page, pathname, payload = {}) {
  const response = await page.request.post(`${BASE_URL}${pathname}`, { data: payload });
  if (!response.ok()) {
    throw new Error(`POST ${pathname} failed with ${response.status()}`);
  }
  return await response.json();
}

async function ensureEnvironmentReady(page) {
  await page.goto(`${BASE_URL}/`);
  let state = await getState(page);
  if (state.environment_state !== 'environment_ready') {
    const startButton = page.locator('button', { hasText: 'Start env' });
    if (await startButton.isVisible()) {
      await startButton.click();
    }
    state = await waitFor(
      page,
      (candidate) => (
        candidate.environment_state === 'environment_ready'
        && candidate.world_stream_ready === true
        && candidate.operator_view_ready === true
      ),
      6 * 60 * 1000,
      'Environment did not become ready.',
    );
  }
  if (state.scenario_state !== 'ready') {
    await postJson(page, '/api/scenario/stop');
    state = await waitFor(
      page,
      (candidate) => (
        candidate.environment_state === 'environment_ready'
        && candidate.scenario_state === 'ready'
      ),
      2 * 60 * 1000,
      'Dashboard did not return to ready state.',
    );
  }
  return state;
}

async function run() {
  fs.mkdirSync(VISUAL_ROOT, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } });

  try {
    let readyState = await ensureEnvironmentReady(page);
    const results = [];
    let previousSessionId = readyState.session_id || '';

    for (let runIndex = 1; runIndex <= REQUIRED_GREEN_RUNS; runIndex += 1) {
      const runDir = path.join(VISUAL_ROOT, `run_${String(runIndex).padStart(2, '0')}`);
      fs.mkdirSync(runDir, { recursive: true });
      const seenProofStates = [];
      const seenSet = new Set();
      let sawRunning = false;
      let sawNewSession = false;
      let sawActiveScenario = false;
      let activeScenarioLabel = '';

      await page.goto(`${BASE_URL}/`);
      await page.screenshot({ path: path.join(runDir, 'before.png'), fullPage: true });
      await page.evaluate(() => window.pickScenario('corral_single_ball_place'));

      const finalState = await waitFor(
        page,
        (state) => (
          state.scenario_state === 'ready'
          && state.proof_state === 'completed'
          && state.mission_verdict
          && state.mission_verdict.pass === true
          && state.mission_verdict.scenario_id === 'corral_single_ball_place'
          && state.session_id
          && state.session_id !== previousSessionId
          && Array.isArray(state.placed_targets)
          && state.placed_targets.length === 1
        ),
        12 * 60 * 1000,
        `Corral run ${runIndex} did not complete successfully.`,
        async (state) => {
          if (state.scenario_state === 'running') {
            sawRunning = true;
          }
          if (state.session_id && state.session_id !== previousSessionId) {
            sawNewSession = true;
          }
          if (state.active_scenario === 'corral_single_ball_place') {
            sawActiveScenario = true;
            activeScenarioLabel = state.active_scenario_label || activeScenarioLabel;
          }
          const proofState = String(state.proof_state || '');
          if (['visiting', 'capturing', 'placing', 'completed'].includes(proofState) && !seenSet.has(proofState)) {
            seenSet.add(proofState);
            seenProofStates.push({
              proof_state: proofState,
              mission_phase: state.mission_phase,
              gather_phase: state.gather_phase,
              session_id: state.session_id,
            });
            await page.screenshot({ path: path.join(runDir, `${proofState}.png`), fullPage: true });
          }
        },
      );

      await page.screenshot({ path: path.join(runDir, 'final.png'), fullPage: true });

      const artifacts = finalState.latest_artifacts || {};
      const requiredArtifactKeys = ['gather_mission', 'mission_verdict', 'target_results', 'scorecard', 'log'];
      const artifactChecks = Object.fromEntries(
        requiredArtifactKeys.map((key) => [
          key,
          typeof artifacts[key] === 'string' && artifacts[key] && fs.existsSync(artifacts[key]),
        ]),
      );
      const missingArtifacts = Object.entries(artifactChecks)
        .filter(([, ok]) => !ok)
        .map(([key]) => key);

      if (!sawRunning) {
        throw new Error(`Run ${runIndex} never entered running state.`);
      }
      if (!sawNewSession) {
        throw new Error(`Run ${runIndex} did not get a fresh self-contained session.`);
      }
      if (!sawActiveScenario) {
        throw new Error(`Run ${runIndex} never surfaced corral_single_ball_place as the active scenario.`);
      }
      for (const requiredProof of ['visiting', 'capturing', 'placing', 'completed']) {
        if (!seenSet.has(requiredProof)) {
          throw new Error(
            `Run ${runIndex} did not expose proof state ${requiredProof}. Seen: ${Array.from(seenSet).join(', ')}`,
          );
        }
      }
      if (missingArtifacts.length) {
        throw new Error(`Run ${runIndex} missing required artifacts: ${missingArtifacts.join(', ')}`);
      }

      results.push({
        run_index: runIndex,
        session_id_before: previousSessionId,
        session_id_after: finalState.session_id,
        active_scenario_label_seen: activeScenarioLabel,
        proof_states_seen: seenProofStates,
        mission_verdict: finalState.mission_verdict,
        placed_targets: finalState.placed_targets,
        latest_artifacts: artifacts,
        artifact_checks: artifactChecks,
        screenshots: fs.readdirSync(runDir).sort().map((name) => path.join(runDir, name)),
      });
      previousSessionId = finalState.session_id || previousSessionId;
    }

    const summary = {
      generated_utc: new Date().toISOString(),
      type: 'corral_single_ball_dashboard_uat',
      dashboard_url: BASE_URL,
      pass_count: results.length,
      required_green_runs: REQUIRED_GREEN_RUNS,
      promotion_gate_pass: results.length === REQUIRED_GREEN_RUNS,
      runs: results,
    };
    const summaryPath = path.join(OUTPUT_ROOT, 'dashboard_uat_summary.json');
    fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2));
    console.log(`DASHBOARD_UAT_SUMMARY=${summaryPath}`);
    console.log(JSON.stringify(summary, null, 2));
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});
