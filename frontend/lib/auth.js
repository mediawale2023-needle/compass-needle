'use client';

import { createContext, useContext, useState, useEffect } from 'react';
import { API_BASE, apiGet, apiPost, setAuthNotice } from './api';

const AuthContext = createContext(null);

function getStoredValue(key) {
    if (typeof window === 'undefined') return null;
    return sessionStorage.getItem(key) || localStorage.getItem(key);
}

function setStoredValue(key, value) {
    if (typeof window === 'undefined') return;
    sessionStorage.setItem(key, value);
    localStorage.removeItem(key);
}

function setStoredValuePersistent(key, value, persist = false) {
    if (typeof window === 'undefined') return;
    if (persist) {
        localStorage.setItem(key, value);
        sessionStorage.removeItem(key);
        return;
    }
    sessionStorage.setItem(key, value);
    localStorage.removeItem(key);
}

function clearStoredValue(key) {
    if (typeof window === 'undefined') return;
    sessionStorage.removeItem(key);
    localStorage.removeItem(key);
}

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;

        const token = getStoredValue('needle_token');
        const userStr = getStoredValue('needle_user');
        let cachedUser = null;

        if (userStr) {
            try {
                cachedUser = JSON.parse(userStr);
                if (!cancelled) {
                    setUser(cachedUser);
                }
                setStoredValue('needle_user', userStr);
            } catch {
                clearStoredValue('needle_user');
            }
        }

        if (token) {
            setStoredValue('needle_token', token);
            apiGet('/api/auth/me', { noRetry: true })
                .then((freshUser) => {
                    if (cancelled) return;
                    setStoredValue('needle_user', JSON.stringify(freshUser));
                    setUser(freshUser);
                })
                .catch(() => {
                    if (cancelled) return;
                    if (!cachedUser) {
                        setUser(null);
                    }
                })
                .finally(() => {
                    if (!cancelled) {
                        setLoading(false);
                    }
                });
        } else {
            setLoading(false);
        }

        return () => {
            cancelled = true;
        };
    }, []);

    const establishSession = (nextUser, token, rememberMe = false) => {
        setStoredValuePersistent('needle_token', token, rememberMe);
        setStoredValuePersistent('needle_user', JSON.stringify(nextUser), rememberMe);
        if (nextUser?.must_change_password) {
            sessionStorage.setItem('needle_force_reset_required', '1');
        } else {
            sessionStorage.removeItem('needle_force_reset_required');
        }
        setUser(nextUser);
        return nextUser;
    };

    const login = async (username, password, rememberMe = false) => {
        const data = await apiPost('/api/auth/login', { username, password });
        return establishSession(data.user, data.token, rememberMe);
    };

    const logout = async () => {
        const token = getStoredValue('needle_token');
        if (token) {
            try {
                const logoutPath = user?.is_support_access_session ? '/api/support-access/end' : '/api/logout';
                await fetch(`${API_BASE}${logoutPath}`, {
                    method: 'POST',
                    headers: { Authorization: `Bearer ${token}` },
                });
            } catch {}
        }
        clearStoredValue('needle_token');
        clearStoredValue('needle_user');
        sessionStorage.removeItem('needle_force_reset_required');
        setAuthNotice('');
        setUser(null);
    };

    const completeForcedPasswordReset = async (currentPassword, newPassword) => {
        const data = await apiPost('/api/auth/complete-forced-password-reset', {
            current_password: currentPassword,
            new_password: newPassword,
        });
        return establishSession(data.user, data.token, false);
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, loading, completeForcedPasswordReset, establishSession }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be inside AuthProvider');
    return ctx;
}
