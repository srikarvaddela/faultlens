import { expect, test } from '@playwright/test'

test('saved-answer audit preserves scores and exposes review evidence on desktop and mobile', async ({ page }) => {
  const truth = { functions: ['handle_request'], line: 400 }
  const answer = { answer: 'The server returns HTTP 400.', answer_sha256: 'synthetic-answer-hash', recorded: true, legacy_replay: true, matched_functions: [], line_token_hit: true, explicit_line_hit: false, explicit_lines: [], flags: ['unanchored_line_number'] }
  const rows = [
    { project: 'example', bug_id: '1', source: 'real', operator: '', single: true, chain: false, fn_leak: null, chain_step1: null, chain_step2: null, chain_step3: null, audit: {
      version: '1.0.0', raw_filename: 'raw_answers_test.jsonl', raw_sha256: 'synthetic-raw-hash', needs_review: true, flags: [], ground_truth: truth, csv_ground_truth: truth,
      answers: { single: answer, chain: { ...answer, answer: 'Another function is faulty.', recorded: false, legacy_replay: false, line_token_hit: false, flags: [] } },
    } },
    { project: 'example', bug_id: '2', source: 'real', operator: '', single: false, chain: true, fn_leak: null, chain_step1: null, chain_step2: null, chain_step3: null, audit: null },
  ]
  await page.route('**/api/research', route => route.fulfill({ json: [{ id: 'audit-test', name: 'Synthetic audit study', run_count: 1, observation_count: 2 }] }))
  await page.route('**/api/research/audit-test', route => route.fulfill({ json: {
    id: 'audit-test', name: 'Synthetic audit study', run_count: 1, observation_count: 2, notes: ['Review flags do not change recorded scores.'],
    runs: [{ filename: 'results_test.csv', sha256: 'synthetic-csv-hash', model_label: 'Unspecified', duplicate_of: null, rows }],
  } }))
  await page.goto('/')
  await expect(page.getByText('API connected')).toBeVisible()
  await page.getByRole('button', { name: 'Research', exact: true }).click()
  await page.getByLabel('Saved answer audit').selectOption('flagged')
  await expect(page.getByTestId('research-pairs')).toHaveText('1')
  await expect(page.getByTestId('research-single')).toHaveText('100.0%')
  await page.getByRole('button', { name: 'Audit example #1' }).click()
  const panel = page.getByRole('region', { name: 'Answer audit' })
  await expect(panel).toBeVisible()
  await expect(page.getByLabel('Single-prompt saved answer')).toHaveText('The server returns HTTP 400.')
  await expect(panel.getByText('Ground-truth number appears without an explicit line reference or matching function')).toBeVisible()
  await expect(panel.getByText('Line: 400', { exact: true })).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: '../docs/screenshots/answer-audit.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByLabel('Chain-of-prompt saved answer')).toHaveText('Another function is faulty.')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Close answer audit' }).click()
  await expect(panel).not.toBeVisible()
  await page.getByLabel('Saved answer audit').selectOption('missing')
  await expect(page.getByRole('button', { name: /Audit example/ })).toHaveCount(0)
  await expect(page.getByText('Unavailable', { exact: true })).toBeVisible()
})
