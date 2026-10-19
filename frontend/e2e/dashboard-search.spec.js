// Dashboard header search hands the query to Briefcase's existing case search (?q=).
const { test, expect } = require('@playwright/test');
test('header search opens Briefcase with the query', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(() => { sessionStorage.setItem('needle_token', 't'); sessionStorage.setItem('needle_user', JSON.stringify({ username: 's', display_name: 'S J', role: 'mp', constituency: 'Belgaum Dakshin' })); });
  const seen = [];
  await page.route('http://127.0.0.1:4010/**', (r) => { const u = new URL(r.request().url()); if (u.pathname === '/api/cases') seen.push(u.searchParams.get('search')); return r.fulfill({ json: u.pathname === '/api/cases' ? { cases: [], total: 0, page: 1, pages: 1 } : u.pathname === '/api/dashboard/overview' ? { attention_counts: [{ key: 'needs_review', value: 1 }], attention_queue: [] } : {} }); });
  await page.goto('/dashboard');
  await page.getByText('Attention Queue').first().waitFor();
  await page.keyboard.press('Control+k');
  await expect(page.getByLabel('Search cases in Briefcase')).toBeFocused();
  await page.getByLabel('Search cases in Briefcase').fill('Tilakwadi');
  await page.keyboard.press('Enter');
  await page.waitForURL(/sansadx\?q=Tilakwadi/);
  await expect(page.getByPlaceholder(/Search citizen, ref/)).toHaveValue('Tilakwadi');
  await expect.poll(() => seen.includes('Tilakwadi')).toBeTruthy();
});
