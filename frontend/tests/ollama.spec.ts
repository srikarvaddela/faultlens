import { expect, test } from '@playwright/test'

test('local inference UI shows saved results, transcript metadata, and parse failures', async ({ page }) => {
  await page.route('**/api/ollama/status', route => route.fulfill({ json: { connected: true, server_version: 'test-version', models: [{ name: 'test-local:1b', digest: 'synthetic-model-digest' }] } }))
  await page.route('**/api/ollama/runs', route => route.request().method() === 'POST' ? route.fulfill({ status: 202, json: { id: 'test-run' } }) : route.fulfill({ json: [] }))
  const result = {
    id: 'test-run', status: 'completed', cancel_requested: false, error: null,
    model_identity: { name: 'test-local:1b', digest: 'synthetic-model-digest' }, options: { temperature: 0, seed: 42, num_predict: 256 },
    results: [
      { strategy: 'single', fault_rank: 1, top1: true, top3: true, parse: { valid: true, error: null, candidates: [{ line: 3, reason: 'Synthetic test reason' }] } },
      { strategy: 'chain_evidence', fault_rank: null, top1: false, top3: false, parse: { valid: false, error: 'invalid_json', candidates: [] } },
    ],
    calls: [{ strategy: 'single', step: 1, status: 'completed', messages: [{ role: 'user', content: 'Synthetic saved input' }], latency_ms: 1000, response: { message: { content: 'Synthetic saved output' }, prompt_eval_count: 25, eval_count: 10, done_reason: 'stop' } }],
  }
  await page.route('**/api/ollama/runs/test-run', route => route.fulfill({ json: result }))
  await page.goto('/')
  await expect(page.getByText('API connected')).toBeVisible()
  await page.getByRole('button', { name: 'Prompt lab', exact: true }).click()
  await page.getByRole('button', { name: 'Prepare prompt plan', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Prepared prompt plan' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Run with Ollama', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Run with Ollama', exact: true }).click()
  await expect(page.getByText('Run completed', { exact: true })).toBeVisible()
  await expect(page.getByText('Parse failure: invalid_json')).toBeVisible()
  await page.getByText('Single prompt · step 1 · completed · 1.00s').click()
  await expect(page.getByText('Synthetic saved output', { exact: true })).toBeVisible()
  await expect(page.getByText('Input tokens: 25 · Output tokens: 10 · Stop: stop')).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
