const fs = require('fs');
const path = require('path');
const { chromium } = require('@playwright/test');

const BASE_URL = process.env.DASHBOARD_URL || 'http://127.0.0.1:8860';
const OUTPUT_ROOT = process.env.CORRAL_DASHBOARD_UAT_ROOT
  || 'D:/dev/chasecar/artifacts/session/20260412T_CORRAL_DASHBOARD_UAT';
const VISUAL_ROOT = path.join(OUTPUT_ROOT, 'dashboard_visual_clean');
const REQUIRED_GREEN_RUNS = Math.max(Number.parseInt(process.env.CORRAL_DASHBOARD_UAT_RUNS || '3', 10) || 3, 1);
const CAPTURE_STAGE_SCREENSHOTS = process.env.CORRAL_DASHBOARD_UAT_CAPTURE_STAGES === '1';

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
  const summaryPath = path.join(OUTPUT_ROOT, 'dashboard_uat_summary.json');
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } });

  try {
    let readyState = await ensureEnvironmentReady(page);
    const results = [];
    let previousSessionId = readyState.session_id || '';
    const writeSummary = (extra = {}) => {
      const passCount = results.filter((item) => item.passed === true).length;
      const summary = {
        generated_utc: new Date().toISOString(),
        type: 'corral_single_ball_dashboard_uat',
        dashboard_url: BASE_URL,
        pass_count: passCount,
        required_green_runs: REQUIRED_GREEN_RUNS,
        promotion_gate_pass: passCount === REQUIRED_GREEN_RUNS && results.length === REQUIRED_GREEN_RUNS,
        runs: results,
        ...extra,
      };
      fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2));
      return summary;
    };

    for (let runIndex = 1; runIndex <= REQUIRED_GREEN_RUNS; runIndex += 1) {
      const runDir = path.join(VISUAL_ROOT, `run_${String(runIndex).padStart(2, '0')}`);
      fs.mkdirSync(runDir, { recursive: true });
      const seenProofStates = [];
      const seenSet = new Set();
      let sawRunning = false;
      let sawNewSession = false;
      let sawActiveScenario = false;
      let activeScenarioLabel = '';
      let sawWorldStreamRestart = false;
      let sawWorldStreamDegraded = false;
      let degradedPollStreak = 0;
      let maxDegradedPollStreak = 0;

      await page.goto(`${BASE_URL}/`);
      const preRunState = await getState(page);
      const restartAttemptsBeforeRun = Number.parseInt(String(preRunState.world_stream_restart_attempts || '0'), 10) || 0;
      const latestEventBeforeRun = Array.isArray(preRunState.recent_operator_events) && preRunState.recent_operator_events.length
        ? String(preRunState.recent_operator_events[preRunState.recent_operator_events.length - 1].timestamp_utc || '')
        : '';
      await page.screenshot({ path: path.join(runDir, 'before.png') });
      await page.evaluate(() => window.pickScenario('corral_single_ball_place'));

      try {
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
            const missionVerdict = state.mission_verdict && typeof state.mission_verdict === 'object'
              ? state.mission_verdict
              : null;
            if (
              state.scenario_state === 'error'
              && missionVerdict
              && missionVerdict.scenario_id === 'corral_single_ball_place'
            ) {
              const missionError = missionVerdict.mission_error || state.last_result || state.scenario_message || 'unknown_error';
              throw new Error(`Run ${runIndex} mission failed: ${missionError}`);
            }
            if (
              state.scenario_state === 'ready'
              && missionVerdict
              && missionVerdict.scenario_id === 'corral_single_ball_place'
              && missionVerdict.pass === false
            ) {
              const missionError = missionVerdict.mission_error || state.last_result || state.scenario_message || 'unknown_error';
              throw new Error(`Run ${runIndex} mission finished failed: ${missionError}`);
            }
            const restartAttemptsNow = Number.parseInt(String(state.world_stream_restart_attempts || '0'), 10) || 0;
            if (restartAttemptsNow > restartAttemptsBeforeRun) {
              sawWorldStreamRestart = true;
            }
            const runSurfaceActive = state.scenario_state === 'running' || sawRunning;
            if (runSurfaceActive && (state.world_stream_degraded === true || state.world_stream_ready === false)) {
              degradedPollStreak += 1;
              maxDegradedPollStreak = Math.max(maxDegradedPollStreak, degradedPollStreak);
              if (degradedPollStreak >= 2) {
                sawWorldStreamDegraded = true;
              }
            } else {
              degradedPollStreak = 0;
            }
            const recentEvents = Array.isArray(state.recent_operator_events) ? state.recent_operator_events : [];
            if (recentEvents.some((item) => {
              const eventTimestamp = String((item && item.timestamp_utc) || '');
              if (latestEventBeforeRun && eventTimestamp && eventTimestamp <= latestEventBeforeRun) {
                return false;
              }
              const message = String((item && item.message) || '');
              return message.includes('World surface stale; restarting world stream controller.')
                || message.includes('World surface recovered after stale stream.');
            })) {
              sawWorldStreamRestart = true;
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
              if (CAPTURE_STAGE_SCREENSHOTS) {
                await page.screenshot({ path: path.join(runDir, `${proofState}.png`) });
              }
            }
          },
        );

        await page.screenshot({ path: path.join(runDir, 'final.png') });

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
        const missionVerdict = finalState.mission_verdict || {};
        const zonePose = missionVerdict.zone_pose && typeof missionVerdict.zone_pose === 'object'
          ? missionVerdict.zone_pose
          : {};
        const zoneRadius = Number.parseFloat(String(zonePose.radius_m || '0.2')) || 0.2;
        const finalSettleDistance = Number.parseFloat(String(missionVerdict.final_settle_distance_m || '0'));
        const maxOvershootDistance = Number.parseFloat(String(missionVerdict.max_overshoot_distance_m || '0'));
        const settleTime = Number.parseFloat(String(missionVerdict.settle_time_s || '0'));
        const releaseRecontactCount = Number.parseInt(String(missionVerdict.release_recontact_count || '0'), 10) || 0;
        const surfaceProfile = String(missionVerdict.surface_profile || finalState.surface_profile || '');
        const worldStreamRestartCountDelta = Math.max(
          (Number.parseInt(String(finalState.world_stream_restart_attempts || '0'), 10) || 0) - restartAttemptsBeforeRun,
          0,
        );
        const worldStreamClean = (
          worldStreamRestartCountDelta === 0
          && !sawWorldStreamRestart
          && !sawWorldStreamDegraded
          && finalState.world_stream_ready === true
          && finalState.world_stream_degraded !== true
        );

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
        if (!surfaceProfile) {
          throw new Error(`Run ${runIndex} did not report a surface_profile.`);
        }
        if (!(finalSettleDistance <= zoneRadius)) {
          throw new Error(`Run ${runIndex} settled outside the zone. final_settle_distance_m=${finalSettleDistance} zone_radius=${zoneRadius}`);
        }
        if (!(maxOvershootDistance <= 0.05)) {
          throw new Error(`Run ${runIndex} exceeded overshoot allowance. max_overshoot_distance_m=${maxOvershootDistance}`);
        }
        if (!(settleTime <= 2.0)) {
          throw new Error(`Run ${runIndex} settled too slowly. settle_time_s=${settleTime}`);
        }
        if (releaseRecontactCount > 1) {
          throw new Error(`Run ${runIndex} exceeded release recontact budget. release_recontact_count=${releaseRecontactCount}`);
        }
        if (!worldStreamClean) {
          throw new Error(
            `Run ${runIndex} was not operator-clean. restart_delta=${worldStreamRestartCountDelta} degraded_seen=${sawWorldStreamDegraded} restart_seen=${sawWorldStreamRestart}`,
          );
        }

        results.push({
          run_index: runIndex,
          session_id_before: previousSessionId,
          session_id_after: finalState.session_id,
          active_scenario_label_seen: activeScenarioLabel,
          proof_states_seen: seenProofStates,
          mission_verdict: finalState.mission_verdict,
          placed_targets: finalState.placed_targets,
          surface_profile: surfaceProfile,
          final_settle_distance_m: finalSettleDistance,
          max_overshoot_distance_m: maxOvershootDistance,
          settle_time_s: settleTime,
          release_recontact_count: releaseRecontactCount,
          latest_artifacts: artifacts,
          artifact_checks: artifactChecks,
          world_stream_restart_count_delta: worldStreamRestartCountDelta,
          world_stream_clean: worldStreamClean,
          world_stream_degraded_poll_streak_max: maxDegradedPollStreak,
          screenshots: fs.readdirSync(runDir).sort().map((name) => path.join(runDir, name)),
          passed: true,
        });
        previousSessionId = finalState.session_id || previousSessionId;
      } catch (error) {
        results.push({
          run_index: runIndex,
          session_id_before: previousSessionId,
          active_scenario_label_seen: activeScenarioLabel,
          proof_states_seen: seenProofStates,
          world_stream_restart_count_delta: sawWorldStreamRestart ? 1 : 0,
          world_stream_clean: false,
          world_stream_degraded_poll_streak_max: maxDegradedPollStreak,
          failure_reason: error && error.message ? error.message : String(error),
          screenshots: fs.readdirSync(runDir).sort().map((name) => path.join(runDir, name)),
          passed: false,
        });
        const failedSummary = writeSummary({
          failure_reason: error && error.message ? error.message : String(error),
        });
        console.log(`DASHBOARD_UAT_SUMMARY=${summaryPath}`);
        console.log(JSON.stringify(failedSummary, null, 2));
        throw error;
      }
    }

    const summary = writeSummary();
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
