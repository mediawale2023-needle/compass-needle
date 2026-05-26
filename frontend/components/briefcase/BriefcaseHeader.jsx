'use client';

import { Download, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function BriefcaseHeader({ downloading, onDownload }) {
    return (
        <div className="flex items-start justify-between gap-4">
            <div>
                <h1 className="text-2xl font-bold text-foreground">Briefcase</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Manage constituent grievances and cases
                </p>
            </div>
            <Button
                variant="outline"
                size="sm"
                onClick={onDownload}
                disabled={downloading}
                className="shrink-0 gap-2"
            >
                {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                {downloading ? 'Generating…' : 'Download Report'}
            </Button>
        </div>
    );
}
