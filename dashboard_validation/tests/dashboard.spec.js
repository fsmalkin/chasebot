const { test, expect } = require('@playwright/test');

async function getState(page) {
  const response = await page.request.get('/api/state');
  expect(response.ok()).toBeTruthy();
  return await response.json();
}

async function waitForCondition(page, predicate, timeoutMs, message) {
  const deadline = Date.now() + timeoutMs;
  let lastState = {};
  while (Date.now() < deadline) {
    lastState = await getState(page);
    if (predicate(lastState)) {
      return lastState;
    }
    await page.waitForTimeout(1000);
  }
  throw new Error(`${message}\nLast state: ${JSON.stringify(lastState, null, 2)}`);
}

async function ensureStopped(page) {
  await page.request.post('/api/env/stop').catch(() => null);
  await waitForCondition(page, (state) => state.environment_state === 'stopped', 90_000, 'Environment did not stop.');
}

async function observeStateTransition(page, field, middleValue, finalValue, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let sawMiddle = false;
  let lastState = {};
  while (Date.now() < deadline) {
    lastState = await getState(page);
    const value = lastState[field];
    if (value === middleValue) {
      sawMiddle = true;
    }
    if (value === finalValue && sawMiddle) {
      return lastState;
    }
    await page.waitForTimeout(1000);
  }
  throw new Error(`Did not observe ${field} transition ${middleValue} -> ${finalValue}.\nLast state: ${JSON.stringify(lastState, null, 2)}`);
}

async function waitForImageLoaded(page, testId) {
  await expect.poll(async () => {
    return await page.getByTestId(testId).evaluate((img) => img.complete && img.naturalWidth > 0);
  }, { timeout: 30_000 }).toBeTruthy();
}

test.describe.serial('dashboard operator flow', () => {
  test.setTimeout(15 * 60 * 1000);

  test('environment start-stop-start cycle', async ({ page }) => {
    await page.goto('/');
    await ensureStopped(page);

    await page.getByTestId('btn-next-step').click();
    await observeStateTransition(page, 'environment_state', 'starting', 'environment_ready', 5 * 60 * 1000);
    await expect(page.getByTestId('environment-state')).toHaveText('environment_ready');

    await page.getByTestId('btn-stop').click();
    await observeStateTransition(page, 'environment_state', 'stopping', 'stopped', 3 * 60 * 1000);
    await expect(page.getByTestId('environment-state')).toHaveText('stopped');

    await page.getByTestId('btn-next-step').click();
    await observeStateTransition(page, 'environment_state', 'starting', 'environment_ready', 5 * 60 * 1000);
    await expect(page.getByTestId('environment-state')).toHaveText('environment_ready');
  });

  test('reset sim and run single-target proof', async ({ page }) => {
    await page.goto('/');
    const before = await getState(page);
    const oldSession = before.session_id;

    await page.getByTestId('btn-reset-sim').click();
    const resetState = await waitForCondition(
      page,
      (state) => state.environment_state === 'environment_ready' && state.session_id && state.session_id !== oldSession,
      6 * 60 * 1000,
      'Reset sim did not yield a new ready session.'
    );
    expect(resetState.session_id).not.toBe(oldSession);

    await page.getByTestId('btn-demo-m3_single_target').click();
    await waitForCondition(page, (state) => state.scenario_state === 'running', 30_000, 'Scenario did not enter running state.');
    await expect(page.getByTestId('phase')).toHaveText(/M3/);
    await expect(page.getByTestId('target-id')).toHaveText(/single_target/);

    await waitForImageLoaded(page, 'world-image');
    await page.getByTestId('camera-tab-raw').click();
    await waitForImageLoaded(page, 'raw-image');
    await page.getByTestId('camera-tab-debug').click();
    await waitForImageLoaded(page, 'debug-image');

    const finalState = await waitForCondition(
      page,
      (state) => state.scenario_state === 'ready' && state.motion_evidence === true,
      8 * 60 * 1000,
      'Single-target scenario did not complete with motion evidence.'
    );
    expect(finalState.latest_artifacts.nav2 || '').not.toBe('');
  });

  test('multi-target rehearsal surfaces transition state', async ({ page }) => {
    await page.goto('/');

    await page.getByTestId('btn-demo-multi_target_rehearsal').click();
    await waitForCondition(page, (state) => state.scenario_state === 'running', 30_000, 'Multi-target scenario did not start.');

    await waitForCondition(
      page,
      (state) => state.target_transition_active === true,
      8 * 60 * 1000,
      'Dashboard never surfaced target_transition_active during multi-target rehearsal.'
    );

    const finalState = await waitForCondition(
      page,
      (state) => state.scenario_state === 'ready',
      10 * 60 * 1000,
      'Multi-target rehearsal did not return to ready state.'
    );
    expect(finalState.latest_artifacts.multi_target || '').not.toBe('');
  });

  test('intent controls update status strip', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('advanced-toggle').click();
    await expect(page.getByTestId('btn-acquire-target')).toBeEnabled();

    await page.getByTestId('btn-acquire-target').click();
    await waitForCondition(page, (state) => state.last_intent === 'acquire_target', 60_000, 'acquire_target did not register.');

    await page.getByTestId('btn-plan-to-target').click();
    await waitForCondition(page, (state) => state.last_intent === 'plan_to_target', 60_000, 'plan_to_target did not register.');

    await page.getByTestId('btn-track-target').click();
    await waitForCondition(page, (state) => state.last_intent === 'track_target', 60_000, 'track_target did not register.');

    await page.getByTestId('btn-abort').click();
    await waitForCondition(page, (state) => state.last_intent === 'abort', 60_000, 'abort did not register.');

    await page.getByTestId('btn-safe-stop').click();
    const finalState = await waitForCondition(page, (state) => state.last_intent === 'safe_stop', 60_000, 'safe_stop did not register.');
    expect(finalState.last_result).toContain('safe_stop');
  });

  test('final stop returns dashboard to stopped state', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('btn-stop').click();
    await observeStateTransition(page, 'environment_state', 'stopping', 'stopped', 3 * 60 * 1000);
    await expect(page.getByTestId('environment-state')).toHaveText('stopped');
  });
});
