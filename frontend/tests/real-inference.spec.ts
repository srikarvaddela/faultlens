import { expect, test } from '@playwright/test'

test('real plans expose context exclusions and render file-aware results', async ({ page }) => {
  const plan = { id: 'synthetic-real-plan', bug_id: 'example#1', kind: 'real', strategy: 'single', evidence_mode: 'fresh_regression_output', prompt_version: 'real-test', status: 'prepared_no_inference', steps: ['Localize fault'], carry_evidence: true, first_messages: [{ role: 'user', content: 'File: module.py\n1: value = 1' }], notes: ['File-conditioned localization with oracle-assisted file selection.'], first_messages_sha256: 'synthetic', evidence_sha256: 'synthetic', source_sha256: 'synthetic', plan_sha256: 'synthetic' }
  await page.route('**/api/real-cases', route => route.fulfill({ json: [{ id: 'ready', case_label: 'example#1', status: 'ready', reason: null }, { id: 'large', case_label: 'large#2', status: 'excluded', reason: 'Full-file input exceeds context budget' }] }))
  await page.route('**/api/prompt-plans', route => route.fulfill({ json: [] }))
  await page.route('**/api/real-prompt-plans', async route => {
    expect(route.request().postDataJSON()).toEqual({ case_id: 'ready', strategy: 'single' })
    await route.fulfill({ json: plan })
  })
  await page.route('**/api/ollama/status', route => route.fulfill({ json: { connected: true, models: [{ name: 'synthetic-local', digest: 'synthetic' }], server_version: 'test' } }))
  await page.route('**/api/ollama/runs', route => route.fulfill({ json: route.request().method() === 'POST' ? { id: 'real-run' } : [] }))
  await page.route('**/api/ollama/runs/real-run', route => route.fulfill({ json: { id: 'real-run', kind: 'real', status: 'completed', cancel_requested: false, error: null, model_identity: { name: 'synthetic-local', digest: 'synthetic' }, options: { num_ctx: 32768, num_predict: 256 }, calls: [], results: [{ strategy: 'single', metric: 'file_conditioned_patch_location_hit', fault_rank: 1, top1: true, top3: true, parse: { valid: true, error: null, candidates: [{ file: 'module.py', line: 1, reason: 'Synthetic result' }] } }] } }))
  await page.goto('/')
  await page.getByRole('button', { name: 'Prompt lab', exact: true }).click()
  await page.getByLabel('Prompt input source').selectOption('real')
  await expect(page.getByText('large#2 · Excluded: Full-file input exceeds context budget')).toBeVisible()
  await page.getByRole('button', { name: 'Prepare prompt plan', exact: true }).click()
  await expect(page.getByLabel('user prompt')).toContainText('File: module.py')
  await expect(page.getByText('LOCAL INFERENCE · REAL CASE · FILE CONDITIONED')).toBeVisible()
  await page.getByRole('button', { name: 'Run with Ollama', exact: true }).click()
  await expect(page.getByText('Patch-location rank: 1 · Top-1: hit')).toBeVisible()
  await expect(page.getByText('module.py:Line 1: Synthetic result')).toBeVisible()
})
