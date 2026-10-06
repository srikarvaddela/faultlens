import { expect, test } from '@playwright/test'

test('fresh validation keeps failed controls separate from ready cases', async ({ page }) => {
  const base = { project: 'example', sources: [{ path: 'module.py', sha256: 'synthetic-source', patch_verified: true, targets: [{ line: 8, kind: 'insertion_anchor', function: 'calculate' }] }], fresh_runs: { buggy: { exit_code: 1, timeout: false, output: 'FAILED synthetic regression', output_sha256: 'synthetic-output', latency_ms: 10 } }, buggy_commit: 'synthetic-buggy', fixed_commit: 'synthetic-fixed', capture_commit_matches: true, deviations: [] }
  await page.route('**/api/research', route => route.fulfill({ json: [{ id: 'validation-test', name: 'Synthetic validation', run_count: 1, observation_count: 1 }] }))
  await page.route('**/api/research/validation-test', route => route.fulfill({ json: {
    id: 'validation-test', name: 'Synthetic validation', run_count: 1, observation_count: 1, notes: [],
    runs: [{ filename: 'results_test.csv', sha256: 'synthetic', model_label: 'Unspecified', duplicate_of: null, rows: [] }],
    real_validation: { version: '1.0.0', benchmark_revision: 'synthetic-benchmark', selection: 'Synthetic controls', notes: ['Historical inputs are unverified.'], cases: [{ ...base, bug_id: '1', status: 'buggy_fails_fixed_passes', ready_for_prompt_review: true }, { ...base, bug_id: '2', status: 'both_revisions_fail', ready_for_prompt_review: false }] }
  } }))
  await page.goto('/')
  await page.getByRole('button', { name: 'Research', exact: true }).click()
  const panel = page.getByRole('region', { name: 'Real-case validation' })
  await expect(panel).toContainText('1/2 ready for prompt review')
  await expect(panel).toContainText('Both revisions fail')
  await panel.locator('summary').first().click()
  await expect(page.getByLabel('example 1 buggy reproduction output')).toHaveText('FAILED synthetic regression')
  await expect(panel).toContainText('insertion anchor')
  await expect(panel).toContainText('Historical prompt identity remains unverified')
})
