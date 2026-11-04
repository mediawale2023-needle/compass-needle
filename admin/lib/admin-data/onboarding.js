/**
 * Account onboarding — the single definition of the create-account form
 * rules, its POST payload, client-side readiness, and the post-creation
 * launch checklist. Behaviour is carried over unchanged from PR #146:
 *   - step 1 requires name and state; step 2 requires username and password;
 *   - the payload sent to POST /api/admin/mps is identical;
 *   - the launch checklist reads the same profile/staff/geography/onboarding
 *     fields and uses the same required keys.
 * Nothing here is persisted before creation (there are no server drafts).
 */

export const ONBOARDING_STEPS = [
    { key: 'identity', label: 'Identity', detail: 'Who it represents' },
    { key: 'access', label: 'Seat & Access', detail: 'Seat and primary login' },
    { key: 'configure', label: 'Configure', detail: 'Messaging and context' },
    { key: 'review', label: 'Review & Create', detail: 'Check, then create' },
];

export const INITIAL_ACCOUNT_FORM = {
    account_stage: 'elected',
    seat_type: 'mp',
    name: '', display_name: '', house: 'Lok Sabha',
    username: '', password: '', constituency: '',
    state: '', party: '', whatsapp_number: '',
    languages: 'English, Hindi', key_facts: '', alt_names: '',
};

/** Role choices map onto the existing seat_type + house fields. */
export const ROLE_OPTIONS = [
    { value: 'mp-ls', label: 'MP', detail: 'Lok Sabha', seat_type: 'mp', house: 'Lok Sabha' },
    { value: 'mp-rs', label: 'MP', detail: 'Rajya Sabha', seat_type: 'mp', house: 'Rajya Sabha' },
    { value: 'mla', label: 'MLA', detail: 'Vidhan Sabha', seat_type: 'mla', house: 'Vidhan Sabha' },
];

export function roleValue(form) {
    if (form.seat_type === 'mla') return 'mla';
    return form.house === 'Rajya Sabha' ? 'mp-rs' : 'mp-ls';
}

export function applyRole(form, value) {
    const role = ROLE_OPTIONS.find((option) => option.value === value);
    return role ? { ...form, seat_type: role.seat_type, house: role.house } : form;
}

/** Lok Sabha MPs pick from the constituency list; others type the seat. */
export function constituencyMode(form) {
    if (form.seat_type === 'mp' && form.house === 'Lok Sabha') return { kind: 'select', label: 'Parliamentary constituency' };
    if (form.seat_type === 'mla') return { kind: 'text', label: 'Assembly seat name' };
    return { kind: 'text', label: 'State / Nominated' };
}

/** Returns an error message for the step, or '' when it may continue. */
export function validateStep(form, step) {
    if (step === 1 && !(form.name && form.state)) return 'Name and State are required before continuing';
    if (step === 2 && !(form.username && form.password)) return 'Username and Password are required before continuing';
    return '';
}

export function validateForCreate(form) {
    if (!form.name || !form.username || !form.password || !form.state) return 'Name, Username, Password and State are required';
    return '';
}

function splitList(value, separator) {
    return value ? value.split(separator).map((item) => item.trim()).filter(Boolean) : [];
}

export function buildCreatePayload(form) {
    return {
        name: form.name,
        username: form.username,
        password: form.password,
        tenant_type: form.account_stage === 'aspirant' ? 'aspirant' : form.seat_type,
        account_stage: form.account_stage,
        seat_type: form.seat_type,
        constituency: form.constituency || 'India',
        whatsapp_number: form.whatsapp_number,
        house: form.house,
        display_name: form.display_name || form.name,
        state: form.state,
        party: form.party || 'Independent',
        languages: form.languages ? splitList(form.languages, ',') : ['English', 'Hindi'],
        key_facts: splitList(form.key_facts, '\n'),
        alt_names: splitList(form.alt_names, ','),
    };
}

/**
 * Client-side readiness while creating. Only reflects what is in the form;
 * post-creation checks are listed as "after creation", never as done.
 * states: complete | progress | todo | optional
 */
export function formReadiness(form) {
    const identityFilled = [form.name, form.state].filter(Boolean).length;
    const accessFilled = [form.username, form.password].filter(Boolean).length;
    return [
        {
            key: 'identity', label: 'Identity', step: 1,
            state: identityFilled === 2 ? 'complete' : identityFilled ? 'progress' : 'todo',
            detail: identityFilled === 2 ? 'Name and state set' : 'Name and state required',
        },
        {
            key: 'seat', label: 'Seat', step: 2,
            state: form.constituency ? 'complete' : 'todo',
            detail: form.constituency ? form.constituency : 'Not set · defaults to India',
        },
        {
            key: 'access', label: 'Admin access', step: 2,
            state: accessFilled === 2 ? 'complete' : accessFilled ? 'progress' : 'todo',
            detail: accessFilled === 2 ? 'Primary login ready' : 'Username and temporary password required',
        },
        {
            key: 'whatsapp', label: 'WhatsApp number', step: 3,
            state: form.whatsapp_number ? 'complete' : 'optional',
            detail: form.whatsapp_number ? 'Number entered · Meta phone ID set after creation' : 'Can be added after creation',
        },
        {
            key: 'context', label: 'AI context', step: 3,
            state: form.key_facts.trim() ? 'complete' : 'optional',
            detail: form.key_facts.trim() ? `${splitList(form.key_facts, '\n').length} key facts` : 'Key facts improve drafting and intelligence',
        },
        { key: 'geography', label: 'Geography', state: 'optional', detail: 'Set up after creation' },
        { key: 'staff', label: 'Staff', state: 'optional', detail: 'Set up after creation' },
    ];
}

// ─── Post-creation launch checklist (moved from the setup page) ───────────

export const LAUNCH_REQUIRED_KEYS = ['profile', 'key_facts', 'geography', 'staff', 'whatsapp', 'test_sent'];

export function buildLaunchChecklist(tenantId, detail, onboarding = {}, geography = { assemblies: {} }) {
    const p = detail?.profile || {};
    const assemblies = Object.keys(geography?.assemblies || {});
    const localityCount = assemblies.reduce((sum, assembly) => sum + (geography.assemblies[assembly]?.length || 0), 0);
    const hasWhatsAppNumber = !!p.whatsapp_number;
    const hasPhoneId = !!p.phone_number_id;

    return [
        {
            key: 'profile', label: 'Profile Data',
            desc: 'Name, constituency, state, house, and party are present.',
            action: 'Edit profile', link: `/dashboard/mps/${tenantId}#profile`,
            done: !!(p.mp_name && p.constituency && p.state && p.house),
            source: 'Verified from profile',
        },
        {
            key: 'key_facts', label: 'AI Context Added',
            desc: 'Key facts help Copilot, Drafter, and constituency intelligence avoid generic output.',
            action: 'Add key facts', link: `/dashboard/mps/${tenantId}#profile`,
            done: !!(p.key_facts && p.key_facts.length > 0),
            source: 'Verified from profile',
        },
        {
            key: 'geography', label: 'Geography Uploaded',
            desc: assemblies.length
                ? `${assemblies.length} assemblies and ${localityCount} localities available for routing.`
                : 'Upload or add assembly-locality data before live grievance routing.',
            action: 'Configure geography', link: `/dashboard/shared-geography/workspace?tenant_id=${tenantId}`,
            done: assemblies.length > 0 && localityCount > 0,
            source: 'Verified from saved geography',
            meta: { assemblies: assemblies.length, localities: localityCount },
        },
        {
            key: 'rules', label: 'Geography Rules Reviewed',
            desc: 'Optional override rules are not required, but should be reviewed for ambiguous locality names.',
            action: 'Review rules', link: '/dashboard/shared-geography/rules',
            done: true, optional: true,
            source: 'Optional review step',
        },
        {
            key: 'staff', label: 'Staff Assigned',
            desc: 'At least one active non-admin staff account is assigned to this tenant.',
            action: 'Add staff', link: `/dashboard/mps/${tenantId}#staff`,
            done: (detail?.staff || []).some((s) => s.is_active),
            source: 'Verified from staff roster',
        },
        {
            key: 'whatsapp', label: 'WhatsApp Routing Ready',
            desc: hasWhatsAppNumber && hasPhoneId
                ? 'WhatsApp number and Meta phone number ID are mapped.'
                : 'Both WhatsApp number and Meta phone number ID are required for reliable routing.',
            action: 'Configure WhatsApp', link: `/dashboard/mps/${tenantId}#whatsapp`,
            done: hasWhatsAppNumber && hasPhoneId,
            source: hasWhatsAppNumber && !hasPhoneId ? 'Missing Meta phone number ID' : 'Verified from tenant config',
        },
        {
            key: 'test_sent', label: 'Live Smoke Test Completed',
            desc: 'Manually verify MP login, webhook intake, and one citizen reply before enabling production traffic.',
            action: null, link: null,
            done: !!onboarding.test_sent, manual: true,
            source: 'Manual operator verification',
        },
    ];
}

export function launchSummary(checklist, onboarding = {}) {
    const required = checklist.filter((item) => LAUNCH_REQUIRED_KEYS.includes(item.key));
    const completed = required.filter((item) => item.done).length;
    const blockers = required.filter((item) => !item.done);
    return {
        required: required.length,
        completed,
        pct: required.length ? Math.round((completed / required.length) * 100) : 0,
        blockers,
        canGoLive: blockers.length === 0,
        isLive: !!onboarding?.live,
    };
}
