'use client';

import { Button } from '@/components/ui/button';

export default function BriefcasePagination({ page, totalPages, totalCases, search, onPrevious, onNext }) {
    return (
        <div className="px-4 md:px-6 py-3 border-t flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs md:text-sm text-muted-foreground">
                Page {page} of {totalPages} · <strong>{totalCases}</strong> total cases
                {search && <span> · filtered by "{search}"</span>}
            </span>
            <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={onPrevious}>
                    Previous
                </Button>
                {totalPages > 2 && (
                    <span className="flex items-center px-2 text-sm text-muted-foreground">
                        {page} / {totalPages}
                    </span>
                )}
                <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={onNext}>
                    Next
                </Button>
            </div>
        </div>
    );
}
