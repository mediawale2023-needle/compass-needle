'use client';

import { createContext, useContext, useState, useEffect } from 'react';
import { apiPost, apiGet } from './api';

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

function clearStoredValue(key) {
    if (typeof window === 'undefined') return;
    sessionStorage.removeItem(key);
    localStorage.removeItem(key);
}

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const token = getStoredValue('needle_token');
        const userStr = getStoredValue('needle_user');
        if (token && userStr) {
            try {
                setUser(JSON.parse(userStr));
                setStoredValue('needle_token', token);
                setStoredValue('needle_user', userStr);
            } catch {
                clearStoredValue('needle_token');
                clearStoredValue('needle_user');
            }
        }
        setLoading(false);
    }, []);

    const login = async (username, password) => {
        const data = await apiPost('/api/auth/login', { username, password });
        setStoredValue('needle_token', data.token);
        setStoredValue('needle_user', JSON.stringify(data.user));
        setUser(data.user);
        return data.user;
    };

    const logout = () => {
        clearStoredValue('needle_token');
        clearStoredValue('needle_user');
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be inside AuthProvider');
    return ctx;
}
