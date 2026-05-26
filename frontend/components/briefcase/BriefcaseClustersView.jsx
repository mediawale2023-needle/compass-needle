'use client';

import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { getStatusBadge } from '@/components/briefcase/briefcase-shared';

export default function BriefcaseClustersView({ clusters, loading, onSelectCase }) {
    if (loading) {
        return <div className="space-y-3 py-6">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 w-full rounded-lg" />)}</div>;
    }

    if (clusters.length === 0) {
        return <div className="text-center py-16 text-muted-foreground">No clusters found in the last 30 days.</div>;
    }

    return (
        <div className="divide-y">
            {clusters.map((cluster, index) => (
                <div key={index} className="py-4">
                    <div className="flex items-center justify-between mb-2">
                        <div>
                            <span className="font-semibold text-sm">{cluster.category}</span>
                            {cluster.location && cluster.location !== 'Unknown' && (
                                <span className="text-muted-foreground text-sm ml-2">· {cluster.location}</span>
                            )}
                        </div>
                        <Badge variant="secondary">{cluster.count} cases</Badge>
                    </div>
                    <div className="space-y-1">
                        {(cluster.cases || []).slice(0, 5).map((item) => (
                            <div
                                key={item.id}
                                className="text-xs text-muted-foreground flex items-center gap-2 cursor-pointer hover:text-foreground"
                                onClick={() => onSelectCase({ id: item.id, ...item })}
                            >
                                <span className="shrink-0">{getStatusBadge(item.status)}</span>
                                <span className="truncate">{item.message_preview}</span>
                            </div>
                        ))}
                        {cluster.count > 5 && (
                            <p className="text-xs text-muted-foreground">+{cluster.count - 5} more cases in this cluster</p>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}
