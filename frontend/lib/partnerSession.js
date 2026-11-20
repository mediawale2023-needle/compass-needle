'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
    clearPartnerSession,
    getMustChangePassword,
    getPartnerToken,
    getStoredPartnerBrand,
    partnerChangePassword,
    partnerLogin,
    partnerMe,
    storePartnerSession,
} from './partnerApi';

const PartnerSessionContext = createContext(null);

export function PartnerSessionProvider({ children }) {
    const [state, setState] = useState({ ready: false, token: null, partner: null, mustChangePassword: false });

    useEffect(() => {
        let cancelled = false;
        const token = getPartnerToken();
        const partner = getStoredPartnerBrand();
        const mustChangePassword = getMustChangePassword();
        setState({ ready: true, token, partner, mustChangePassword });

        // Refresh branding and confirm the token is still valid (a 401 clears storage in the client).
        if (token && !mustChangePassword) {
            partnerMe()
                .then((me) => {
                    if (cancelled) return;
                    storePartnerSession({ partner: me.partner });
                    setState((s) => ({ ...s, partner: me.partner }));
                })
                .catch(() => {
                    if (cancelled) return;
                    if (!getPartnerToken()) setState({ ready: true, token: null, partner: null, mustChangePassword: false });
                });
        }
        return () => {
            cancelled = true;
        };
    }, []);

    const signIn = useCallback(async (email, password) => {
        const res = await partnerLogin(email.trim(), password);
        storePartnerSession({ token: res.token, partner: res.partner, mustChangePassword: !!res.must_change_password });
        setState({ ready: true, token: res.token, partner: res.partner, mustChangePassword: !!res.must_change_password });
        return res;
    }, []);

    const changePassword = useCallback(async (currentPassword, newPassword) => {
        const res = await partnerChangePassword(currentPassword, newPassword);
        storePartnerSession({ token: res.token, mustChangePassword: false });
        setState((s) => ({ ...s, token: res.token, mustChangePassword: false }));
        return res;
    }, []);

    const signOut = useCallback(() => {
        clearPartnerSession();
        setState({ ready: true, token: null, partner: null, mustChangePassword: false });
    }, []);

    const value = useMemo(
        () => ({ ...state, signIn, changePassword, signOut }),
        [state, signIn, changePassword, signOut],
    );
    return <PartnerSessionContext.Provider value={value}>{children}</PartnerSessionContext.Provider>;
}

export function usePartnerSession() {
    const ctx = useContext(PartnerSessionContext);
    if (!ctx) throw new Error('usePartnerSession must be used inside PartnerSessionProvider');
    return ctx;
}
