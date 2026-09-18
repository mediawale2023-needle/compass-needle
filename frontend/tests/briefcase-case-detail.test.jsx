import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { useState } from 'react';
import { AccordionRow, ComplaintTabStrip } from '@/components/briefcase/BriefcaseCaseModal';
import CitizenReplyDialog from '@/components/briefcase/CitizenReplyDialog';

afterEach(cleanup);

describe('Case Detail interaction contracts', () => {
    it('connects disclosure state to its region', () => {
        render(<AccordionRow label="Internal notes">Private content</AccordionRow>);
        const trigger = screen.getByRole('button', { name: 'Internal notes' });
        expect(trigger).toHaveAttribute('aria-expanded', 'false');
        fireEvent.click(trigger);
        expect(trigger).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByRole('region', { name: 'Internal notes' })).toBeVisible();
    });
    it('supports keyboard complaint selection without invented context', () => {
        const select = vi.fn();
        render(<ComplaintTabStrip threadCases={[{ id: 2, status: 'new' }, { id: 1, status: 'in_progress' }]} activeCaseId={1} onSelectCase={select} />);
        expect(screen.queryByText(/same location|6 weeks/)).not.toBeInTheDocument();
        const tabs = screen.getAllByRole('tab');
        expect(tabs[0]).toHaveAttribute('aria-selected', 'true');
        fireEvent.keyDown(tabs[0], { key: 'ArrowRight' });
        expect(select).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }));
    });
    it('keeps preview in sync and does not send an empty message', () => {
        const send = vi.fn();
        function Composer() {
            const [response, setResponse] = useState('');
            return <CitizenReplyDialog open onOpenChange={() => {}} response={response} onChange={setResponse} onSend={send} phone="919876543210" caseRef="NDL-1" status="in_progress" />;
        }
        render(<Composer />);
        expect(screen.getByRole('button', { name: 'Send WhatsApp reply' })).toBeDisabled();
        fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'The department is reviewing your complaint.' } });
        expect(screen.getByText('The department is reviewing your complaint.', { selector: 'p' })).toBeVisible();
        fireEvent.click(screen.getByRole('button', { name: 'Send WhatsApp reply' }));
        expect(send).toHaveBeenCalledOnce();
        expect(screen.getByText(/Sending does not resolve/)).toBeVisible();
    });
    it('preserves the failed draft and exposes an accessible error', () => {
        render(<CitizenReplyDialog open onOpenChange={() => {}} response="Still reviewing" onChange={() => {}} onSend={() => {}} phone="919876543210" caseRef="NDL-1" status="new" error="Send failed. Draft kept." />);
        expect(screen.getByLabelText('Message')).toHaveValue('Still reviewing');
        expect(screen.getByRole('alert')).toHaveTextContent('Draft kept');
    });
});
