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

    const login = async (username, password, rememberMe = false) => {
        const data = await apiPost('/api/auth/login', { username, password });
        setStoredValuePersistent('needle_token', data.token, rememberMe);
        setStoredValuePersistent('needle_user', JSON.stringify(data.user), rememberMe);
        if (data.user?.must_change_password) {
            sessionStorage.setItem('needle_force_reset_required', '1');
        } else {
            sessionStorage.removeItem('needle_force_reset_required');
        }
        setUser(data.user);
        return data.user;
    };

    const logout = async () => {
        const token = getStoredValue('needle_token');
        if (token) {
            try {
                await fetch(`${API_BASE}/api/logout`, {
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
        setStoredValue('needle_token', data.token);
        setStoredValue('needle_user', JSON.stringify(data.user));
        sessionStorage.removeItem('needle_force_reset_required');
        setUser(data.user);
        return data.user;
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, loading, completeForcedPasswordReset }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be inside AuthProvider');
    return ctx;
}
