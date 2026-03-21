const { test, expect } = require('@playwright/test');

const DASHBOARD_URL = process.env.DASHBOARD_URL || 'http://127.0.0.1:8860';

async function getState(page) {
  const response = await page.request.get(`${DASHBOARD_URL}/api/state`);
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
  await page.request.post(`${DASHBOARD_URL}/api/env/stop`).catch(() => null);
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
  await expect.poll(async () => (
    await page.getByTestId(testId).evaluate((img) => img.complete && img.naturalWidth > 0)
  ), { timeout: 30_000 }).toBeTruthy();
}

async function openControlsDrawer(page) {
  const drawer = page.getByTestId('controls-drawer');
  if ((await drawer.getAttribute('data-open')) !== 'true') {
    await page.getByTestId('btn-toggle-controls').click();
    await expect(drawer).toHaveAttribute('data-open', 'true');
  }
}

async function closeControlsDrawer(page) {
  const drawer = page.getByTestId('controls-drawer');
  if ((await drawer.getAttribute('data-open')) === 'true') {
    await page.getByRole('button', { name: 'Close' }).first().click();
    await expect(drawer).toHaveAttribute('data-open', 'false');
  }
}

test.describe.serial('dashboard operator flow', () => {
  test.setTimeout(15 * 60 * 1000);

  test('default page centers on llm turn-and-go demo', async ({ page }) => {
    await page.goto(`${DASHBOARD_URL}/`);
    await ensureStopped(page);

    await expect(page.getByTestId('environment-state')).toBeVisible();
    await expect(page.getByTestId('active-scenario')).toBeVisible();
    await expect(page.getByTestId('proof-state')).toBeVisible();
    await expect(page.getByTestId('session-id')).toBeVisible();
    await expect(page.getByTestId('world-image')).toBeVisible();
    await expect(page.getByTestId('debug-image')).toBeVisible();
    await expect(page.getByTestId('btn-toggle-controls')).toBeVisible();
    await expect(page.getByTestId('btn-toggle-log')).toBeVisible();
    await expect(page.getByTestId('controls-drawer')).toHaveAttribute('data-open', 'false');
    await expect(page.getByTestId('log-drawer')).toHaveAttribute('data-open', 'false');
    await expect(page.getByTestId('btn-start-env')).not.toBeVisible();
  });

  test('environment start-stop-start cycle', async ({ page }) => {
    await page.goto(`${DASHBOARD_URL}/`);
    await ensureStopped(page);
    await openControlsDrawer(page);

    await page.getByTestId('btn-start-env').click();
    await observeStateTransition(page, 'environment_state', 'starting', 'environment_ready', 5 * 60 * 1000);
    await expect(page.getByTestId('environment-state')).toHaveText('environment_ready');

    await page.getByTestId('btn-stop').click();
    await observeStateTransition(page, 'environment_state', 'stopping', 'stopped', 3 * 60 * 1000);
    await expect(page.getByTestId('environment-state')).toHaveText('stopped');

    await page.getByTestId('btn-start-env').click();
    await observeStateTransition(page, 'environment_state', 'starting', 'environment_ready', 5 * 60 * 1000);
    await expect(page.getByTestId('environment-state')).toHaveText('environment_ready');
  });

  test('reset sim and run single-target visible-ball demo', async ({ page }) => {
    await page.goto(`${DASHBOARD_URL}/`);
    await openControlsDrawer(page);
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
    await expect(page.getByTestId('controls-drawer')).toHaveAttribute('data-open', 'false');
    await waitForCondition(page, (state) => state.scenario_state === 'running', 30_000, 'Scenario did not enter running state.');
    await expect(page.getByTestId('active-scenario')).toHaveText(/M3 Single Target/);

    await waitForImageLoaded(page, 'world-image');
    await waitForImageLoaded(page, 'debug-image');

    const finalState = await waitForCondition(
      page,
      (state) => state.scenario_state === 'ready' && state.motion_evidence === true,
      8 * 60 * 1000,
      'Single-target scenario did not complete with motion evidence.'
    );
    expect(finalState.latest_artifacts.nav2 || '').not.toBe('');
  });

  test('advanced drawer keeps manual tools and quick intents', async ({ page }) => {
    await page.goto(`${DASHBOARD_URL}/`);
    await openControlsDrawer(page);
    await page.getByTestId('advanced-toggle').click();

    await expect(page.getByTestId('scenario-select')).toBeVisible();
    await expect(page.getByTestId('raw-image')).toBeVisible();
    await expect(page.getByTestId('topdown-image')).toBeVisible();
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
    await page.goto(`${DASHBOARD_URL}/`);
    await openControlsDrawer(page);
    await page.getByTestId('btn-stop').click();
    await observeStateTransition(page, 'environment_state', 'stopping', 'stopped', 3 * 60 * 1000);
    await expect(page.getByTestId('environment-state')).toHaveText('stopped');
    await closeControlsDrawer(page);
  });
});
