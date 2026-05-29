'use client';

import { useEffect, useState } from 'react';
import { Loader2, Send } from 'lucide-react';
import { apiDelete, apiGet, apiPatch, apiPost } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import BriefcaseEscalationModal from '@/components/briefcase/BriefcaseEscalationModal';
import BriefcaseSourceMediaViewer from '@/components/briefcase/BriefcaseSourceMediaViewer';
import { STATUS_OPTIONS, getStatusBadge } from '@/components/briefcase/briefcase-shared';
import { isPrimaryAccount } from '@/lib/account';
import { cn } from '@/lib/utils';

export default function BriefcaseCaseModal({ caseItem, color, onClose, onStatusChange, staff, user }) {
    const toast = useToast();
    const [updating, setUpdating] = useState(null);
    const [notes, setNotes] = useState('');
    const [response, setResponse] = useState('');
    const [savingNotes, setSavingNotes] = useState(false);
    const [assignee, setAssignee] = useState('');
    const [activities, setActivities] = useState([]);
    const [loadingActivity, setLoadingActivity] = useState(false);
    const [showEscalation, setShowEscalation] = useState(false);
    const [draftSaved, setDraftSaved] = useState(false);
    const [similarCases, setSimilarCases] = useState([]);
    const [notifyOpen, setNotifyOpen] = useState(false);
    const [notifyInput, setNotifyInput] = useState('');
    const [notifySending, setNotifySending] = useState(false);
    const [fullCase, setFullCase] = useState(null);
    const [geoLocation, setGeoLocation] = useState('');
    const [geoAssembly, setGeoAssembly] = useState('');
    const [savingGeo, setSavingGeo] = useState(false);

    useEffect(() => {
        if (!caseItem) {
            return;
        }
        setFullCase(caseItem);
        apiGet(`/api/cases/${caseItem.id}`)
            .then((result) => {
                setFullCase({ ...caseItem, ...result });
                setGeoLocation(result.case_metadata?.matched_value || result.location || '');
                setGeoAssembly(result.case_metadata?.assembly_constituency || result.assembly || '');
            })
            .catch(() => setFullCase(caseItem));

        const savedNotes = localStorage.getItem(`draft_notes_${caseItem.id}`);
        const savedResponse = localStorage.getItem(`draft_response_${caseItem.id}`);
        setNotes(savedNotes !== null ? savedNotes : (caseItem.notes_for_staff || ''));
        setResponse(savedResponse !== null ? savedResponse : (caseItem.response_to_citizen || ''));
        setAssignee(caseItem.assigned_to || '');
        setDraftSaved(savedNotes !== null || savedResponse !== null);
        setGeoLocation(caseItem.case_metadata?.matched_value || caseItem.location || '');
        setGeoAssembly(caseItem.case_metadata?.assembly_constituency || caseItem.assembly || '');

        setLoadingActivity(true);
        apiGet(`/api/cases/${caseItem.id}/activity`)
            .then((result) => setActivities(result.activities || []))
            .catch(() => setActivities([]))
            .finally(() => setLoadingActivity(false));

        apiGet(`/api/cases/${caseItem.id}/similar`)
            .then((result) => setSimilarCases(result.cases || []))
            .catch(() => setSimilarCases([]));
    }, [caseItem?.id]);

    useEffect(() => {
        if (!caseItem) {
            return;
        }
        localStorage.setItem(`draft_notes_${caseItem.id}`, notes);
        localStorage.setItem(`draft_response_${caseItem.id}`, response);
    }, [notes, response, caseItem?.id]);

    if (!caseItem) {
        return null;
    }

    const current = fullCase || caseItem;
    const meta = current.case_metadata || {};
    const createdAt = current.created_at ? new Date(current.created_at) : null;
    const updatedAt = current.updated_at ? new Date(current.updated_at) : null;
    const currentStatus = (current.status || 'new').toLowerCase();
    const isMp = isPrimaryAccount(user);
    const caseRef = current.case_ref || `#${current.id}`;

    const handleStatusChange = async (newStatus) => {
        setUpdating(newStatus);
        try {
            await apiPatch(`/api/cases/${current.id}/status`, { status: newStatus });
            onStatusChange(current.id, newStatus);
            toast.success(`Case marked as ${newStatus}`);
        } catch (error) {
            console.error('Status update failed:', error);
            toast.error('Failed to update status');
        } finally {
            setUpdating(null);
        }
    };

    const saveNotes = async () => {
        setSavingNotes(true);
        try {
            await apiPatch(`/api/cases/${current.id}`, {
                notes_for_staff: notes || null,
                response_to_citizen: response || null,
            });
            localStorage.removeItem(`draft_notes_${current.id}`);
            localStorage.removeItem(`draft_response_${current.id}`);
            setDraftSaved(false);
            toast.success('Notes saved successfully');
        } catch (error) {
            console.error('Failed to save notes:', error);
            toast.error('Failed to save notes');
        } finally {
            setSavingNotes(false);
        }
    };

    const saveGeography = async () => {
        setSavingGeo(true);
        try {
            await apiPatch(`/api/cases/${current.id}`, {
                location: geoLocation || null,
                assembly: geoAssembly || null,
            });
            const refreshed = await apiGet(`/api/cases/${current.id}`);
            setFullCase({ ...current, ...refreshed });
            setGeoLocation(refreshed.case_metadata?.matched_value || refreshed.location || '');
            setGeoAssembly(refreshed.case_metadata?.assembly_constituency || refreshed.assembly || '');
            onStatusChange(current.id, refreshed.status || currentStatus);
            toast.success('Geography updated and locked');
        } catch (error) {
            console.error('Failed to save geography:', error);
            toast.error('Failed to save geography');
        } finally {
            setSavingGeo(false);
        }
    };

    const sendNotification = async () => {
        setNotifySending(true);
        try {
            const customMessage = response && response.trim() ? response.trim() : null;
            await apiPost(`/api/cases/${current.id}/notify/send`, {
                message: customMessage,
                response_to_citizen: customMessage,
            });
            setNotifyOpen(false);
            setNotifyInput('');
            toast.success('WhatsApp update sent — case moved to Resolved');
            onStatusChange(current.id, 'resolved');
            onClose();
        } catch (error) {
            toast.error(error.message || 'Failed to send notification');
        } finally {
            setNotifySending(false);
        }
    };

    const handleAssign = async (username) => {
        try {
            await apiPatch(`/api/cases/${current.id}`, { assigned_to: username || null });
            setAssignee(username);
            onStatusChange(current.id, currentStatus);
            toast.success(`Case assigned to ${username || 'unassigned'}`);
        } catch (error) {
            console.error('Failed to assign:', error);
            toast.error('Failed to assign case');
        }
    };

    const handleDelete = async () => {
        if (!window.confirm('Are you sure you want to delete this case? This cannot be undone.')) {
            return;
        }
        try {
            await apiDelete(`/api/cases/${current.id}`);
            onClose();
            toast.success('Case deleted successfully');
        } catch (error) {
            console.error('Failed to delete case:', error);
            toast.error('Failed to delete case');
        }
    };

    if (currentStatus === 'resolved') {
        const notifyActivity = [...activities].reverse().find((activity) => activity.action === 'citizen_notified');
        const notifiedAt = notifyActivity ? new Date(notifyActivity.created_at) : null;
        return (
            <Dialog open={!!caseItem} onOpenChange={onClose}>
                <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                    <DialogHeader className="p-0 -m-6 mb-0">
                        <div className="p-6 text-white rounded-t-xl" style={{ background: color }}>
                            <DialogDescription className="text-white/80 text-xs uppercase tracking-widest font-semibold mb-1">
                                Resolved · {caseRef}
                            </DialogDescription>
                            <DialogTitle className="text-lg font-bold text-white">{current.category || 'General'}</DialogTitle>
                        </div>
                    </DialogHeader>
                    <div className="space-y-4 pt-6">
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                            {[
                                ['Case Number', caseRef],
                                ['Contact', current.user_phone || '-'],
                                ['Category', current.category || 'General'],
                                ['Location', meta.matched_value || current.location || '-'],
                                ['Assembly', meta.assembly_constituency || current.assembly || '-'],
                                ['Geo Confidence', meta.geography_confidence || '-'],
                                ['Date Filed', createdAt ? createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'],
                                ['Time Filed', createdAt ? createdAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '-'],
                                ['Date Resolved', notifiedAt ? notifiedAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'],
                                ['Time Resolved', notifiedAt ? notifiedAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '-'],
                            ].map(([label, value]) => (
                                <div key={label} className="border rounded-lg p-3">
                                    <div className="text-xs text-muted-foreground uppercase font-medium">{label}</div>
                                    <div className="text-sm font-medium text-foreground mt-0.5">{value}</div>
                                </div>
                            ))}
                        </div>
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Complaint Message</div>
                            <div className="bg-muted/50 border rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed min-h-[60px]">
                                {current.raw_message || 'No content available.'}
                            </div>
                        </div>
                        <BriefcaseSourceMediaViewer caseId={current.id} media={current.media || []} />
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Resolution Message Sent to Citizen</div>
                            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed min-h-[60px]">
                                {current.response_to_citizen || <span className="text-muted-foreground italic">Standard status message was sent</span>}
                            </div>
                        </div>
                        <Separator />
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Activity Log</div>
                            {loadingActivity ? (
                                <div className="flex items-center justify-center py-4">
                                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                </div>
                            ) : (
                                <div className="space-y-2 max-h-48 overflow-y-auto">
                                    {activities.length === 0 ? (
                                        <p className="text-xs text-muted-foreground">No activity yet</p>
                                    ) : (
                                        activities.map((activity) => (
                                            <div key={activity.id} className="flex items-start gap-2 text-xs">
                                                <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                                                <div>
                                                    <span className="font-medium">{activity.username}</span> {activity.action.replace(/_/g, ' ')}
                                                    {activity.new_value && <span className="text-muted-foreground"> → {activity.new_value}</span>}
                                                    <div className="text-muted-foreground">
                                                        {activity.created_at ? new Date(activity.created_at).toLocaleString('en-IN') : ''}
                                                    </div>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={onClose}>Close</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        );
    }

    return (
        <Dialog open={!!caseItem} onOpenChange={onClose}>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader className="p-0 -m-6 mb-0">
                    <div className="p-6 text-white rounded-t-xl" style={{ background: color }}>
                        <DialogDescription className="text-white/80 text-xs uppercase tracking-widest font-semibold mb-1">
                            Grievance · #{current.id}
                        </DialogDescription>
                        <DialogTitle className="text-lg font-bold text-white">
                            {current.category || 'General'}
                        </DialogTitle>
                    </div>
                </DialogHeader>

                <div className="space-y-4 pt-6">
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        {[
                            ['Contact', current.user_phone || '-'],
                            ['Category', current.category || 'General'],
                            ['Status', currentStatus],
                            ['Location', meta.matched_value || current.location || '-'],
                            ['Assembly', meta.assembly_constituency || current.assembly || '-'],
                            ['Geo Confidence', meta.geography_confidence || '-'],
                            ['Date', createdAt ? createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'],
                            ['Time', createdAt ? createdAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '-'],
                            ['Critical', current.is_critical ? 'Yes' : 'No'],
                            ['Last Updated', updatedAt ? updatedAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'],
                        ].map(([label, value]) => (
                            <div key={label} className="border rounded-lg p-3">
                                <div className="text-xs text-muted-foreground uppercase font-medium">{label}</div>
                                <div className="text-sm font-medium text-foreground mt-0.5">{value}</div>
                            </div>
                        ))}
                    </div>

                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Full Message</div>
                        <div className="bg-muted/50 border rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed min-h-[80px]">
                            {current.raw_message || 'No content available.'}
                        </div>
                    </div>

                    <BriefcaseSourceMediaViewer caseId={current.id} media={current.media || []} />

                    {meta.summary && (
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">AI Summary</div>
                            <div className="bg-muted/50 border rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                                {meta.summary}
                            </div>
                        </div>
                    )}

                    {meta.needs_geography_review && (
                        <div className="rounded-lg border border-purple-200 bg-purple-50 px-4 py-3 text-sm text-purple-800">
                            Geography match needs staff review before routing decisions rely on it.
                        </div>
                    )}

                    <Separator />

                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div className="text-xs text-muted-foreground uppercase font-medium">Geography</div>
                            {meta.geography_locked && (
                                <Badge variant="secondary" className="bg-emerald-100 text-emerald-700">
                                    Manual Lock
                                </Badge>
                            )}
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div>
                                <Label htmlFor={`geo-location-${current.id}`} className="text-xs text-muted-foreground uppercase font-medium mb-2 block">
                                    Location
                                </Label>
                                <Input
                                    id={`geo-location-${current.id}`}
                                    value={geoLocation}
                                    onChange={(event) => setGeoLocation(event.target.value)}
                                    placeholder="Village / area / ward"
                                />
                            </div>
                            <div>
                                <Label htmlFor={`geo-assembly-${current.id}`} className="text-xs text-muted-foreground uppercase font-medium mb-2 block">
                                    Assembly
                                </Label>
                                <Input
                                    id={`geo-assembly-${current.id}`}
                                    value={geoAssembly}
                                    onChange={(event) => setGeoAssembly(event.target.value)}
                                    placeholder="Assembly constituency"
                                />
                            </div>
                        </div>
                        <div className="flex items-center gap-3 flex-wrap">
                            <Button onClick={saveGeography} disabled={savingGeo}>
                                {savingGeo ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
                                Save Geography
                            </Button>
                            <span className="text-xs text-muted-foreground">
                                Saving here marks this case as a manual geography correction.
                            </span>
                        </div>
                    </div>

                    <Separator />

                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-3">Update Status</div>
                        <div className="flex flex-wrap gap-2">
                            {STATUS_OPTIONS.filter((option) => option.value !== currentStatus).map((option) => (
                                <Button
                                    key={option.value}
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleStatusChange(option.value)}
                                    disabled={updating === option.value}
                                    className={cn('border', option.className)}
                                >
                                    {updating === option.value && <Loader2 className="h-3 w-3 animate-spin" />}
                                    Mark {option.label}
                                </Button>
                            ))}
                        </div>
                    </div>

                    <Separator />

                    <div className="space-y-4">
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <div className="text-xs text-muted-foreground uppercase font-medium">Notes for Staff</div>
                                {draftSaved && <span className="text-xs text-amber-600 font-medium">● Draft saved locally</span>}
                            </div>
                            <Textarea
                                value={notes}
                                onChange={(event) => setNotes(event.target.value)}
                                placeholder="Internal notes..."
                                className="min-h-[60px]"
                            />
                        </div>
                        <div>
                            <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Response to Citizen</div>
                            <Textarea
                                value={response}
                                onChange={(event) => setResponse(event.target.value)}
                                placeholder="Response message..."
                                className="min-h-[60px]"
                            />
                        </div>
                        <div className="flex items-center gap-2 flex-wrap">
                            <Button onClick={saveNotes} disabled={savingNotes}>
                                {savingNotes ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
                                Save Notes
                            </Button>
                            <Button
                                variant="outline"
                                className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                                disabled={!current.user_phone || !isMp}
                                title={!isMp ? 'Only the primary account can send citizen notifications' : !current.user_phone ? 'No phone number on file' : ''}
                                onClick={() => {
                                    setNotifyInput('');
                                    setNotifyOpen(true);
                                }}
                            >
                                <Send className="h-4 w-4 mr-1" />
                                Send Update via WhatsApp
                                {!isMp && <span className="ml-1 text-xs opacity-60">(Primary only)</span>}
                            </Button>
                        </div>
                    </div>

                    {similarCases.length > 0 && (
                        <>
                            <Separator />
                            <div>
                                <div className="text-xs text-muted-foreground uppercase font-medium mb-2">
                                    Related Cases ({similarCases.length})
                                </div>
                                <div className="space-y-1 max-h-36 overflow-y-auto">
                                    {similarCases.map((similarCase) => (
                                        <div key={similarCase.id} className="flex items-center gap-2 text-xs py-1 border-b last:border-0">
                                            <span className="font-mono text-muted-foreground shrink-0">#{similarCase.id}</span>
                                            {getStatusBadge(similarCase.status)}
                                            <span className="truncate text-muted-foreground">{similarCase.message_preview}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}

                    <Separator />

                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Assign To</div>
                        <select
                            value={assignee}
                            onChange={(event) => handleAssign(event.target.value)}
                            className="w-full border rounded-lg p-2 text-sm"
                        >
                            <option value="">Unassigned</option>
                            {staff.map((staffMember) => (
                                <option key={staffMember.username} value={staffMember.username}>
                                    {staffMember.display_name || staffMember.username}
                                </option>
                            ))}
                        </select>
                    </div>

                    <Separator />

                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Activity Log</div>
                        {loadingActivity ? (
                            <div className="flex items-center justify-center py-4">
                                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                            </div>
                        ) : (
                            <div className="space-y-2 max-h-48 overflow-y-auto">
                                {activities.length === 0 ? (
                                    <p className="text-xs text-muted-foreground">No activity yet</p>
                                ) : (
                                    activities.map((activity) => (
                                        <div key={activity.id} className="flex items-start gap-2 text-xs">
                                            <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                                            <div>
                                                <span className="font-medium">{activity.username}</span> {activity.action.replace('_', ' ')}
                                                {activity.new_value && <span className="text-muted-foreground"> → {activity.new_value}</span>}
                                                <div className="text-muted-foreground">
                                                    {activity.created_at ? new Date(activity.created_at).toLocaleString('en-IN') : ''}
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        )}
                    </div>

                    <Separator />

                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowEscalation(true)}
                            className="border-amber-300 text-amber-700 hover:bg-amber-50"
                        >
                            Escalate to Officer
                        </Button>
                        {(user?.role === 'mp' || user?.role === 'owner' || user?.role === 'pr') && (
                            <Button variant="destructive" size="sm" onClick={handleDelete}>
                                Delete Case
                            </Button>
                        )}
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>Close</Button>
                </DialogFooter>
            </DialogContent>

            {showEscalation && (
                <BriefcaseEscalationModal
                    caseItem={current}
                    color="#b45309"
                    open={showEscalation}
                    onClose={() => setShowEscalation(false)}
                    toast={toast}
                />
            )}

            <Dialog
                open={notifyOpen}
                onOpenChange={(open) => {
                    setNotifyOpen(open);
                    if (!open) {
                        setNotifyInput('');
                    }
                }}
            >
                <DialogContent className="max-w-sm">
                    <DialogHeader>
                        <DialogTitle>Send WhatsApp Update</DialogTitle>
                        <DialogDescription>
                            This will message the citizen about the current status of their case. Type the case reference <strong>{caseRef}</strong> to confirm.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-2 space-y-3">
                        <div className="rounded-lg bg-muted/50 border p-3 text-sm text-muted-foreground">
                            {(() => {
                                if (response && response.trim()) {
                                    return response.trim();
                                }
                                const statusMessages = {
                                    new: `Your grievance (${caseRef}) has been received and is being reviewed.`,
                                    in_progress: `Update on your grievance (${caseRef}): We are actively working on this.`,
                                    escalated: `Update on your grievance (${caseRef}): This has been escalated to the relevant authority.`,
                                    resolved: `Good news! Your grievance (${caseRef}) has been resolved. If unsatisfied, reply 'NO' to reopen.`,
                                    completed: `Good news! Your grievance (${caseRef}) has been resolved. If unsatisfied, reply 'NO' to reopen.`,
                                    closed: `Your grievance (${caseRef}) has been closed. Thank you for reaching out.`,
                                };
                                return statusMessages[current.status] || `Update on your grievance (${caseRef}): Status is now '${current.status}'.`;
                            })()}
                        </div>
                        {response && response.trim() && (
                            <p className="text-xs text-emerald-600 font-medium">✓ Using your custom response message</p>
                        )}
                        <Input
                            placeholder={`Type ${caseRef} to confirm`}
                            value={notifyInput}
                            onChange={(event) => setNotifyInput(event.target.value)}
                            onKeyDown={(event) => event.key === 'Enter' && notifyInput === caseRef && sendNotification()}
                            autoFocus
                        />
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => { setNotifyOpen(false); setNotifyInput(''); }}>Cancel</Button>
                        <Button
                            onClick={sendNotification}
                            disabled={notifyInput !== caseRef || notifySending}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white"
                        >
                            {notifySending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Send className="h-4 w-4 mr-1" />}
                            Confirm & Send
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Dialog>
    );
}
