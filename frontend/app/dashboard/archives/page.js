'use client';

import { useState, useEffect } from 'react';
import { apiGet } from '@/lib/api';
import { FileText, Search, Download, Eye, X, Archive } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const TYPE_CONFIG = {
    draft_letter: { label: 'Letter', icon: FileText, className: 'bg-blue-100 text-blue-700' },
    draft_question: { label: 'Draft', icon: FileText, className: 'bg-amber-100 text-amber-700' },
    analysis: { label: 'Research', icon: Search, className: 'bg-green-100 text-green-700' },
    copilot_chat: { label: 'Research', icon: Search, className: 'bg-green-100 text-green-700' },
};

const TABS = [
    { key: 'all', label: 'All' },
    { key: 'draft_letter', label: 'Letters' },
    { key: 'analysis', label: 'Research' },
];

export default function ArchivesPage() {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all');
    const [selected, setSelected] = useState(null);

    const fetchItems = async () => {
        setLoading(true);
        try {
            const params = filter !== 'all' ? `?activity_type=${filter}` : '';
            const data = await apiGet(`/api/history${params}`);
            setItems(data.items || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    useEffect(() => { fetchItems(); }, [filter]);

    const downloadItem = (item, e) => {
        e?.stopPropagation();
        const blob = new Blob([item.content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${item.title?.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 40) || 'document'}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const getTypeConfig = (type) => {
        return TYPE_CONFIG[type] || TYPE_CONFIG.analysis;
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-foreground">Archives</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Access your saved drafts, letters, and research documents
                </p>
            </div>

            <Card>
                <CardHeader className="pb-0">
                    <Tabs value={filter} onValueChange={setFilter}>
                        <TabsList>
                            {TABS.map(t => (
                                <TabsTrigger key={t.key} value={t.key}>
                                    {t.label}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                    </Tabs>
                </CardHeader>

                <CardContent className="pt-6">
                    {loading ? (
                        <div className="space-y-3">
                            {[1, 2, 3, 4, 5].map(i => (
                                <div key={i} className="flex items-center gap-4">
                                    <Skeleton className="h-4 w-8" />
                                    <Skeleton className="h-4 flex-1" />
                                    <Skeleton className="h-6 w-20" />
                                    <Skeleton className="h-4 w-24" />
                                    <Skeleton className="h-8 w-16" />
                                </div>
                            ))}
                        </div>
                    ) : items.length === 0 ? (
                        <div className="text-center py-16">
                            <Archive className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
                            <p className="text-muted-foreground">No saved items yet.</p>
                            <p className="text-sm text-muted-foreground mt-1">
                                Use the Drafter or Research Desk to save documents.
                            </p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto -mx-6">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-12">#</TableHead>
                                        <TableHead>Title</TableHead>
                                        <TableHead className="w-28">Type</TableHead>
                                        <TableHead className="w-28">Date</TableHead>
                                        <TableHead className="w-20">Action</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {items.map((item, idx) => {
                                        const config = getTypeConfig(item.activity_type);
                                        const Icon = config.icon;
                                        
                                        return (
                                            <TableRow 
                                                key={item.id} 
                                                onClick={() => setSelected(item)} 
                                                className="cursor-pointer"
                                            >
                                                <TableCell className="text-muted-foreground">
                                                    {idx + 1}
                                                </TableCell>
                                                <TableCell className="font-medium">
                                                    {item.title || '-'}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="secondary" className={cn("gap-1", config.className)}>
                                                        <Icon className="h-3 w-3" />
                                                        {config.label}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-muted-foreground text-xs">
                                                    {item.created_at 
                                                        ? new Date(item.created_at).toLocaleDateString('en-CA') 
                                                        : '-'}
                                                </TableCell>
                                                <TableCell>
                                                    <Button 
                                                        variant="ghost" 
                                                        size="sm"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            setSelected(item);
                                                        }}
                                                        style={{ color }}
                                                    >
                                                        <Eye className="h-4 w-4" />
                                                        View
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Detail Modal */}
            <Dialog open={!!selected} onOpenChange={() => setSelected(null)}>
                {selected && (
                    <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                        <DialogHeader className="p-0 -m-6 mb-0">
                            <div className="p-6 text-white rounded-t-xl" style={{ background: color }}>
                                <DialogDescription className="text-white/80 text-xs uppercase tracking-widest font-semibold mb-1">
                                    {getTypeConfig(selected.activity_type).label}
                                </DialogDescription>
                                <DialogTitle className="text-lg font-bold text-white">
                                    {selected.title}
                                </DialogTitle>
                            </div>
                        </DialogHeader>
                        
                        <div className="space-y-4 pt-6">
                            <div className="text-xs text-muted-foreground">
                                {selected.created_at 
                                    ? new Date(selected.created_at).toLocaleString('en-IN', { 
                                        dateStyle: 'full', 
                                        timeStyle: 'short' 
                                    }) 
                                    : '-'}
                            </div>
                            <div className="bg-muted/50 border rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto">
                                {selected.content || 'No content.'}
                            </div>
                        </div>
                        
                        <DialogFooter className="gap-2 sm:gap-0">
                            <Button variant="outline" onClick={() => setSelected(null)}>
                                Close
                            </Button>
                            <Button onClick={() => downloadItem(selected)} style={{ background: color }}>
                                <Download className="h-4 w-4" />
                                Download
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                )}
            </Dialog>
        </div>
    );
}
