'use client';

import { createContext, useContext, useState, useEffect } from 'react';
import { apiPost, apiGet } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Check for existing token
        const token = localStorage.getItem('needle_token');
        const userStr = localStorage.getItem('needle_user');
        if (token && userStr) {
            try {
                setUser(JSON.parse(userStr));
            } catch {
                localStorage.removeItem('needle_token');
                localStorage.removeItem('needle_user');
            }
        }
        setLoading(false);
    }, []);

    const login = async (username, password) => {
        const data = await apiPost('/api/auth/login', { username, password });
        localStorage.setItem('needle_token', data.token);
        localStorage.setItem('needle_user', JSON.stringify(data.user));
        setUser(data.user);
        return data.user;
    };

    const logout = () => {
        localStorage.removeItem('needle_token');
        localStorage.removeItem('needle_user');
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
