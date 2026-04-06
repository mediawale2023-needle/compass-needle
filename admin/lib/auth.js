'use client';
import { createContext, useContext, useState, useEffect } from 'react';

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
        const token = getStoredValue('admin_token');
        const savedUser = getStoredValue('admin_user');
        if (token && savedUser) {
            try {
                setUser(JSON.parse(savedUser));
                setStoredValue('admin_token', token);
                setStoredValue('admin_user', savedUser);
            } catch {
                clearStoredValue('admin_token');
                clearStoredValue('admin_user');
            }
        }
        setLoading(false);
    }, []);

    const login = (token, userData) => {
        setStoredValue('admin_token', token);
        setStoredValue('admin_user', JSON.stringify(userData));
        setUser(userData);
    };

    const logout = () => {
        clearStoredValue('admin_token');
        clearStoredValue('admin_user');
        setUser(null);
        window.location.href = '/';
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    return useContext(AuthContext);
}
