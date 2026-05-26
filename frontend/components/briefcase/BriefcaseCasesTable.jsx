'use client';

import { CheckCircle, Image as ImageIcon } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { getStatusBadge } from '@/components/briefcase/briefcase-shared';
import { getBriefcaseRowHighlight } from '@/hooks/useBriefcaseCases';
import { cn } from '@/lib/utils';

export default function BriefcaseCasesTable({
    cases,
    loading,
    search,
    statusFilter,
    categoryFilter,
    selectedIds,
    setSelectedIds,
    onSelectCase,
    onOpenContact,
}) {
    if (loading) {
        return (
            <div className="space-y-3 py-6">
                {[1, 2, 3, 4, 5].map((i) => (
                    <div key={i} className="flex items-center gap-4">
                        <Skeleton className="h-4 w-4" />
                        <Skeleton className="h-4 w-12" />
                        <Skeleton className="h-4 w-24" />
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-4 w-24" />
                        <Skeleton className="h-4 w-20" />
                        <Skeleton className="h-6 w-20" />
                        <Skeleton className="h-4 flex-1" />
                    </div>
                ))}
            </div>
        );
    }

    if (cases.length === 0) {
        return (
            <div className="text-center py-16">
                <CheckCircle className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
                <p className="text-muted-foreground">
                    No cases found{categoryFilter ? ` in "${categoryFilter}"` : ''}
                    {statusFilter !== 'All' ? ` with status "${statusFilter}"` : ''}
                    {search ? ` matching "${search}"` : ''}.
                </p>
            </div>
        );
    }

    return (
        <div className="overflow-x-auto -mx-6">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead className="w-10 pl-6">
                            <input
                                type="checkbox"
                                checked={selectedIds.size === cases.length && cases.length > 0}
                                onChange={(event) => {
                                    if (event.target.checked) {
                                        setSelectedIds(new Set(cases.map((item) => item.id)));
                                    } else {
                                        setSelectedIds(new Set());
                                    }
                                }}
                                className="rounded border-border"
                            />
                        </TableHead>
                        <TableHead className="w-16">#</TableHead>
                        <TableHead>Contact</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead>Location</TableHead>
                        <TableHead>Assembly</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="max-w-[200px]">Message</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {cases.map((item) => (
                        <TableRow key={item.id} className={cn('cursor-pointer', getBriefcaseRowHighlight(item.status, item.category))} onClick={() => onSelectCase(item)}>
                            <TableCell className="pl-6">
                                <input
                                    type="checkbox"
                                    checked={selectedIds.has(item.id)}
                                    onChange={(event) => {
                                        event.stopPropagation();
                                        setSelectedIds((current) => {
                                            const next = new Set(current);
                                            if (event.target.checked) {
                                                next.add(item.id);
                                            } else {
                                                next.delete(item.id);
                                            }
                                            return next;
                                        });
                                    }}
                                    onClick={(event) => event.stopPropagation()}
                                    className="rounded border-border"
                                />
                            </TableCell>
                            <TableCell className="font-mono text-xs text-muted-foreground">{item.id}</TableCell>
                            <TableCell className="font-mono text-xs">
                                {item.user_phone ? (
                                    <button
                                        className="hover:underline text-primary font-mono text-xs"
                                        onClick={(event) => {
                                            event.stopPropagation();
                                            onOpenContact(item.user_phone);
                                        }}
                                    >
                                        {item.user_phone}
                                    </button>
                                ) : '-'}
                            </TableCell>
                            <TableCell className="font-medium">{item.category || 'General'}</TableCell>
                            <TableCell className="text-muted-foreground">{item.location || '-'}</TableCell>
                            <TableCell className="text-muted-foreground">{item.assembly || '-'}</TableCell>
                            <TableCell>{getStatusBadge(item.status)}</TableCell>
                            <TableCell className="max-w-[200px]">
                                <span className="flex items-center gap-1.5 text-muted-foreground">
                                    {(item.media_count || item.case_metadata?.source_media) ? (
                                        <ImageIcon className="h-3.5 w-3.5 shrink-0 text-primary" />
                                    ) : null}
                                    <span className="truncate block" title={item.raw_message}>
                                        {item.raw_message || '-'}
                                    </span>
                                </span>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </div>
    );
}
