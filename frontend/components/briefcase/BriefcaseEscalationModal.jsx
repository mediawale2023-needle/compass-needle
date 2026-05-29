'use client';

import { useEffect, useState } from 'react';
import { Loader2, Shield } from 'lucide-react';
import { apiGet, apiPost } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';

export default function BriefcaseEscalationModal({ caseItem, color, open, onClose, toast }) {
    const [officers, setOfficers] = useState([]);
    const [selectedOfficer, setSelectedOfficer] = useState('');
    const [letterContent, setLetterContent] = useState('');
    const [escalations, setEscalations] = useState([]);
    const [submitting, setSubmitting] = useState(false);
    const [loadingOfficers, setLoadingOfficers] = useState(false);

    useEffect(() => {
        if (!open) {
            return;
        }
        setLoadingOfficers(true);
        Promise.all([
            apiGet('/api/officers').catch(() => ({ officers: [] })),
            apiGet(`/api/escalations?case_id=${caseItem.id}`).catch(() => ({ escalations: [] })),
        ])
            .then(([officerData, escalationData]) => {
                setOfficers(officerData.officers || []);
                setEscalations(escalationData.escalations || []);
            })
            .finally(() => setLoadingOfficers(false));
    }, [open, caseItem?.id]);

    useEffect(() => {
        if (!open) {
            return;
        }
        const category = caseItem?.category || 'this matter';
        const reference = caseItem?.case_ref || `#${caseItem?.id}`;
        const location = caseItem?.location || '';
        const message = caseItem?.raw_message || '';
        setLetterContent(
`Subject: Escalation of Citizen Grievance ${reference}

Respected Sir/Madam,

I am writing to bring to your urgent attention a citizen grievance (Ref: ${reference}) related to ${category}${location ? ` in ${location}` : ''}.

Citizen's complaint:
"${message.slice(0, 300)}${message.length > 300 ? '...' : ''}"

This issue requires immediate attention and resolution. Kindly look into this matter and take necessary action at the earliest.

Thank you for your cooperation.

Regards,
Constituency Workspace`
        );
    }, [open, caseItem]);

    const handleEscalate = async () => {
        if (!selectedOfficer) {
            toast.error('Please select an officer');
            return;
        }
        setSubmitting(true);
        try {
            await apiPost('/api/escalations', {
                case_id: caseItem.id,
                officer_id: parseInt(selectedOfficer, 10),
                letter_content: letterContent,
                deadline: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
            });
            toast.success('Case escalated to officer');
            const escalationData = await apiGet(`/api/escalations?case_id=${caseItem.id}`).catch(() => ({ escalations: [] }));
            setEscalations(escalationData.escalations || []);
            setSelectedOfficer('');
        } catch (error) {
            toast.error(`Failed to escalate: ${error.message || 'Unknown error'}`);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onClose}>
            <DialogContent className="max-w-xl max-h-[80vh] overflow-y-auto">
                <DialogHeader className="p-0 -m-6 mb-0">
                    <div className="p-5 text-white rounded-t-xl" style={{ background: color || '#b45309' }}>
                        <DialogDescription className="text-white/80 text-xs uppercase tracking-widest font-semibold mb-1">
                            Escalation · Case #{caseItem?.id}
                        </DialogDescription>
                        <DialogTitle className="text-lg font-bold text-white">Escalate to Officer</DialogTitle>
                    </div>
                </DialogHeader>

                <div className="space-y-5 pt-6">
                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Select Officer</div>
                        {loadingOfficers ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" /> Loading officers...
                            </div>
                        ) : officers.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No officers configured. Add officers in Settings first.</p>
                        ) : (
                            <select
                                value={selectedOfficer}
                                onChange={(event) => setSelectedOfficer(event.target.value)}
                                className="w-full border rounded-lg p-2 text-sm"
                            >
                                <option value="">— Select Officer —</option>
                                {officers.map((officer) => (
                                    <option key={officer.id} value={officer.id}>
                                        {officer.name} — {officer.designation}{officer.department ? `, ${officer.department}` : ''}
                                    </option>
                                ))}
                            </select>
                        )}
                    </div>

                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Escalation Letter</div>
                        <Textarea
                            value={letterContent}
                            onChange={(event) => setLetterContent(event.target.value)}
                            className="min-h-[180px] text-sm font-mono"
                        />
                    </div>

                    <Button
                        onClick={handleEscalate}
                        disabled={submitting || !selectedOfficer}
                        className="w-full bg-amber-600 hover:bg-amber-700 text-white"
                    >
                        {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Shield className="h-4 w-4 mr-2" />}
                        Escalate Case
                    </Button>

                    {escalations.length > 0 && (
                        <>
                            <Separator />
                            <div>
                                <div className="text-xs text-muted-foreground uppercase font-medium mb-3">Escalation History</div>
                                <div className="space-y-3">
                                    {escalations.map((escalation) => (
                                        <div key={escalation.id} className="border rounded-lg p-3 space-y-2">
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <span className="text-sm font-medium">{escalation.officer_name || 'Officer'}</span>
                                                    {escalation.designation && (
                                                        <span className="text-xs text-muted-foreground ml-2">{escalation.designation}</span>
                                                    )}
                                                </div>
                                                <Badge variant="outline" className="text-[10px]">
                                                    Escalated
                                                </Badge>
                                            </div>
                                            {escalation.deadline && (
                                                <p className="text-xs text-muted-foreground">
                                                    Deadline: {new Date(escalation.deadline).toLocaleDateString('en-IN')}
                                                </p>
                                            )}
                                            {escalation.created_at && (
                                                <p className="text-xs text-muted-foreground">
                                                    Recorded on {new Date(escalation.created_at).toLocaleString('en-IN')}
                                                </p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>Close</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
