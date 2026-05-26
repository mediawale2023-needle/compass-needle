'use client';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

export default function BriefcaseDeletedCasesView({ deletedCases, loading, onRestore }) {
    if (loading) {
        return <div className="space-y-3 py-6">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full rounded-lg" />)}</div>;
    }

    if (deletedCases.length === 0) {
        return <div className="text-center py-16 text-muted-foreground">No deleted cases in the last 7 days.</div>;
    }

    return (
        <div className="overflow-x-auto -mx-6">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead className="pl-6">#</TableHead>
                        <TableHead>Contact</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead>Deleted At</TableHead>
                        <TableHead>Deleted By</TableHead>
                        <TableHead className="text-right pr-6">Action</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {deletedCases.map((item) => (
                        <TableRow key={item.id} className="opacity-60">
                            <TableCell className="pl-6 font-mono text-xs text-muted-foreground">{item.id}</TableCell>
                            <TableCell className="font-mono text-xs">{item.user_phone || '-'}</TableCell>
                            <TableCell>{item.category || 'General'}</TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                                {item.deleted_at ? new Date(item.deleted_at).toLocaleString('en-IN') : '-'}
                            </TableCell>
                            <TableCell className="text-xs">{item.deleted_by || '-'}</TableCell>
                            <TableCell className="text-right pr-6">
                                <Button size="sm" variant="outline" onClick={() => onRestore(item.id)}>
                                    Restore
                                </Button>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </div>
    );
}
