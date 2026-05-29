export function isPrimaryAccount(user) {
    return ['owner', 'mp', 'admin'].includes(user?.role);
}

export function getAccountStage(user) {
    if (user?.account_stage) return user.account_stage;
    if (user?.tenant_type === 'aspirant') return 'aspirant';
    return 'elected';
}

export function getSeatType(user) {
    if (user?.seat_type) return user.seat_type;
    if (user?.tenant_type === 'mla' || user?.house === 'Vidhan Sabha') return 'mla';
    return 'mp';
}

export function getSeatLabel(user) {
    return getSeatType(user) === 'mla' ? 'MLA' : 'MP';
}

export function getSeatBadge(user) {
    const seatType = getSeatType(user);
    const house = user?.house || '';
    if (seatType === 'mla') return 'VS';
    if (house === 'Rajya Sabha') return 'RS';
    return 'LS';
}

export function getAccountLabel(user) {
    if (user?.account_label) return user.account_label;
    if (user?.role === 'admin') return 'Admin';
    if (user?.role === 'owner') {
        if (getAccountStage(user) === 'aspirant') {
            return getSeatType(user) === 'mla' ? 'Aspirant MLA' : 'Aspirant MP';
        }
        return getSeatLabel(user);
    }
    if (user?.role === 'mp') return 'MP';
    return 'Staff';
}

export function isElectedAccount(user) {
    return isPrimaryAccount(user) && getAccountStage(user) === 'elected';
}

export function canAccessSansadAI(user) {
    return isElectedAccount(user);
}

export function canAccessConvergence(user) {
    return isElectedAccount(user);
}
