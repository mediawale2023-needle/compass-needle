import { describe, it, expect, vi } from 'vitest';

import { confirmSuggestedCategory } from '@/components/briefcase/BriefcaseCaseModal';

// Case lifecycle: accepting the AI's suggested category is triage, not
// progress. It must confirm the taxonomy only and never write the case
// status — progress starts on verified external evidence (government filing
// or portal confirmation) or an explicit staff status change.

describe('confirmSuggestedCategory', () => {
    it('confirms the category and never calls the status endpoint', async () => {
        const patch = vi.fn().mockResolvedValue({ success: true });

        await confirmSuggestedCategory(patch, 42, {
            ai_category: 'Infrastructure & Utilities',
            ai_subcategory: 'Water Supply',
        });

        expect(patch).toHaveBeenCalledTimes(1);
        expect(patch).toHaveBeenCalledWith('/api/cases/42', {
            problem_domain: 'Infrastructure & Utilities',
            problem_subdomain: 'Water Supply',
        });
        for (const [url, body] of patch.mock.calls) {
            expect(url).not.toMatch(/\/status$/);
            expect(body).not.toHaveProperty('status');
        }
    });

    it('falls back to the domain alone without ever touching status', async () => {
        const patch = vi.fn()
            .mockRejectedValueOnce(new Error('Invalid subdomain'))
            .mockResolvedValueOnce({ success: true });

        await confirmSuggestedCategory(patch, 7, {
            ai_category: 'Health',
            ai_subcategory: 'Legacy subdomain',
        });

        expect(patch).toHaveBeenCalledTimes(2);
        expect(patch).toHaveBeenLastCalledWith('/api/cases/7', { problem_domain: 'Health' });
        expect(patch.mock.calls.every(([url]) => !url.endsWith('/status'))).toBe(true);
    });

    it('surfaces a failure when there is no subdomain to drop', async () => {
        const patch = vi.fn().mockRejectedValue(new Error('Server error'));

        await expect(
            confirmSuggestedCategory(patch, 9, { ai_category: 'Health', ai_subcategory: null })
        ).rejects.toThrow('Server error');
        expect(patch).toHaveBeenCalledTimes(1);
    });
});
