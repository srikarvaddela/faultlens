import { expect, test } from '@playwright/test'

test('capture-derived labels stay separate from recorded labels with inspectable evidence', async ({ page }) => {
  const base = { project: 'example', source: 'real', operator: '', single: true, chain: false, chain_step1: null, chain_step2: null, chain_step3: null }
  const rows = [
    { ...base, bug_id: '1', fn_leak: false, derived_leakage: { version: '1.1.0', fn_leak: true, reason: 'function_name_match', matches: [{ function: 'calculate', excerpt: 'in calculate' }], evidence_id: 'example_1.json', historical_input_verified: false } },
    { ...base, bug_id: '2', fn_leak: null, derived_leakage: { version: '1.1.0', fn_leak: null, reason: 'runner_unavailable', matches: [], evidence_id: 'example_2.json', historical_input_verified: false } },
  ]
  const capture = { filename: 'example_1.json', capture_sha256: 'synthetic-capture-hash', evidence_sha256: 'synthetic-evidence-hash', error_message: 'ValueError: bad input', stack_trace: 'File "app.py", line 20, in calculate', reproduced: true }
  await page.route('**/api/research', route => route.fulfill({ json: [{ id: 'leak-test', name: 'Synthetic capture study', run_count: 1, observation_count: 2 }] }))
  await page.route('**/api/research/leak-test', route => route.fulfill({ json: {
    id: 'leak-test', name: 'Synthetic capture study', run_count: 1, observation_count: 2, notes: ['Derived labels do not establish historical input identity.'], capture_evidence: { 'example_1.json': capture, 'example_2.json': { ...capture, filename: 'example_2.json', stack_trace: 'bash: tox: command not found' } },
    runs: [{ filename: 'results_test.csv', sha256: 'synthetic-csv-hash', model_label: 'Unspecified', duplicate_of: null, rows }],
  } }))
  await page.goto('/')
  await expect(page.getByText('API connected')).toBeVisible()
  await page.getByRole('button', { name: 'Research', exact: true }).click()
  await page.getByLabel('Function leakage').selectOption('clean')
  await expect(page.getByTestId('research-pairs')).toHaveText('1')
  await expect(page.getByRole('cell', { name: 'Recorded no leak', exact: true })).toBeVisible()
  await page.getByLabel('Label source').selectOption('derived')
  await expect(page.getByRole('status')).toContainText('do not reproduce the original leakage-controlled study')
  await page.getByLabel('Function leakage').selectOption('leak')
  await expect(page.getByTestId('research-pairs')).toHaveText('1')
  await page.getByRole('button', { name: 'Review capture example #1' }).click()
  await expect(page.getByRole('region', { name: 'Capture leakage review' })).toBeVisible()
  await expect(page.getByLabel('Archived stack trace')).toHaveText('File "app.py", line 20, in calculate')
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: '../docs/screenshots/capture-leakage.png', fullPage: true })
  await page.getByRole('button', { name: 'Close evidence' }).click()
  await page.getByLabel('Function leakage').selectOption('unknown')
  await page.getByRole('button', { name: 'Review capture example #2' }).click()
  await expect(page.getByText('Reason: runner unavailable')).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
