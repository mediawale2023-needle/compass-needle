'use client';

import { useEffect, useState } from 'react';
import { Loader2, Paperclip, FileText } from 'lucide-react';
import { apiBlob } from '@/lib/api';
import { Button } from '@/components/ui/button';

export default function BriefcaseSourceMediaViewer({ caseId, media = [] }) {
    const [activeId, setActiveId] = useState(media[0]?.id || null);
    const [objectUrl, setObjectUrl] = useState('');
    const [loading, setLoading] = useState(false);
    const active = media.find((item) => item.id === activeId) || media[0];

    useEffect(() => {
        setActiveId(media[0]?.id || null);
    }, [caseId, media?.length]);

    useEffect(() => {
        if (!caseId || !active?.id) {
            setObjectUrl('');
            return;
        }
        let cancelled = false;
        let url = '';
        setLoading(true);
        apiBlob(`/api/cases/${caseId}/media/${active.id}`)
            .then((blob) => {
                if (cancelled) {
                    return;
                }
                url = URL.createObjectURL(blob);
                setObjectUrl(url);
            })
            .catch(() => setObjectUrl(''))
            .finally(() => {
                if (!cancelled) {
                    setLoading(false);
                }
            });
        return () => {
            cancelled = true;
            if (url) {
                URL.revokeObjectURL(url);
            }
        };
    }, [caseId, active?.id]);

    if (!media || media.length === 0) {
        return null;
    }

    const isImage = (active?.mime_type || '').startsWith('image/');
    const isPdf = active?.mime_type === 'application/pdf';
    const isAudio = (active?.mime_type || '').startsWith('audio/') || active?.media_type === 'audio';

    return (
        <div>
            <div className="flex items-center justify-between gap-2 mb-2">
                <div className="text-xs text-muted-foreground uppercase font-medium flex items-center gap-1.5">
                    <Paperclip className="h-3.5 w-3.5" />
                    Source Attachment
                </div>
                {media.length > 1 && (
                    <div className="flex gap-1">
                        {media.map((item, index) => (
                            <Button
                                key={item.id}
                                variant={item.id === active?.id ? 'default' : 'outline'}
                                size="sm"
                                className="h-7 px-2 text-xs"
                                onClick={() => setActiveId(item.id)}
                            >
                                {index + 1}
                            </Button>
                        ))}
                    </div>
                )}
            </div>
            <div className="border rounded-lg bg-muted/30 overflow-hidden">
                {loading ? (
                    <div className="h-64 flex items-center justify-center text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin mr-2" />
                        Loading source
                    </div>
                ) : !objectUrl ? (
                    <div className="h-40 flex items-center justify-center text-sm text-muted-foreground">
                        Source file could not be loaded
                    </div>
                ) : isImage ? (
                    <img
                        src={objectUrl}
                        alt="Original complaint source"
                        className="max-h-[520px] w-full object-contain bg-background"
                    />
                ) : isPdf ? (
                    <iframe
                        src={objectUrl}
                        title="Original complaint PDF"
                        className="h-[520px] w-full bg-background"
                    />
                ) : isAudio ? (
                    <div className="p-4 space-y-3">
                        <div className="flex items-center gap-2 text-sm">
                            <Paperclip className="h-4 w-4 text-muted-foreground" />
                            Voice note
                        </div>
                        <audio controls className="w-full" src={objectUrl}>
                            Your browser does not support audio playback.
                        </audio>
                        <div className="text-xs text-muted-foreground">
                            {active?.file_name || active?.mime_type || 'Audio attachment'}
                        </div>
                    </div>
                ) : (
                    <div className="p-4 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 text-sm">
                            <FileText className="h-4 w-4 text-muted-foreground" />
                            {active?.mime_type || 'Attachment'}
                        </div>
                        <Button variant="outline" size="sm" asChild>
                            <a href={objectUrl} target="_blank" rel="noopener noreferrer">Open</a>
                        </Button>
                    </div>
                )}
            </div>
            {active?.caption && (
                <p className="text-xs text-muted-foreground mt-2">
                    Caption: {active.caption}
                </p>
            )}
        </div>
    );
}
