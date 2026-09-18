'use client';

import { useRef } from 'react';
import { Loader2, Send } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

export default function CitizenReplyDialog({ open, onOpenChange, response, onChange, onSend, sending, error, phone, caseRef, status, triggerRef }) {
    const inputRef = useRef(null);
    const maskedPhone = phone ? `••••••${String(phone).slice(-4)}` : 'No phone on file';
    return (
        <Dialog open={open} onOpenChange={(next) => { if (!sending) onOpenChange(next); }}>
            <DialogContent className="case-detail-dialog max-w-lg"
                onOpenAutoFocus={(event) => { event.preventDefault(); inputRef.current?.focus(); }}
                onCloseAutoFocus={(event) => { event.preventDefault(); triggerRef?.current?.focus(); }}
                onInteractOutside={(event) => event.preventDefault()}>
                <DialogHeader>
                    <DialogTitle>Reply to citizen</DialogTitle>
                    <DialogDescription className="case-reply-meta">WhatsApp · {maskedPhone} · Complaint {caseRef}</DialogDescription>
                </DialogHeader>
                <label htmlFor="case-citizen-reply">Message</label>
                <textarea id="case-citizen-reply" ref={inputRef} value={response} disabled={sending}
                    onChange={(event) => onChange(event.target.value)} placeholder="Write a meaningful update for the citizen…" />
                <div className="case-reply-preview"><strong>Exact WhatsApp preview</strong><p>{response.trim() || 'Enter a message to preview it here.'}</p></div>
                <p className="case-reply-meta">Sending does not resolve this complaint. Needle status remains {status.replaceAll('_', ' ')}.</p>
                {error && <p role="alert" className="case-reply-error">{error}</p>}
                <DialogFooter>
                    <Button variant="outline" disabled={sending} onClick={() => onOpenChange(false)}>Keep draft &amp; close</Button>
                    <Button disabled={sending || !response.trim() || !phone} onClick={onSend} style={{ background: '#234f3a', color: '#fffdf8' }}>
                        {sending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
                        {sending ? 'Sending…' : 'Send WhatsApp reply'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
