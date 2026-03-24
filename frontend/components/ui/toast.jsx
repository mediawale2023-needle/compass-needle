'use client';
import { useState, useEffect, createContext, useContext, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { X, CheckCircle2, AlertTriangle, Info } from 'lucide-react';

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
    const [toasts, setToasts] = useState([]);

    const addToast = useCallback((message, type = 'info', duration = 4000) => {
        const id = Date.now() + Math.random();
        setToasts(prev => [...prev, { id, message, type }]);
        if (duration > 0) {
            setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration);
        }
        return id;
    }, []);

    const removeToast = useCallback((id) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    const toastObj = {
        success: (msg) => addToast(msg, 'success'),
        error: (msg) => addToast(msg, 'error', 6000),
        info: (msg) => addToast(msg, 'info'),
        warning: (msg) => addToast(msg, 'warning'),
    };

    return (
        <ToastContext.Provider value={toastObj}>
            {children}
            <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
                {toasts.map(t => (
                    <div
                        key={t.id}
                        className={cn(
                            "flex items-start gap-3 p-4 rounded-lg shadow-lg border animate-fade-in",
                            t.type === 'success' && "bg-emerald-50 border-emerald-200 text-emerald-800",
                            t.type === 'error' && "bg-red-50 border-red-200 text-red-800",
                            t.type === 'warning' && "bg-amber-50 border-amber-200 text-amber-800",
                            t.type === 'info' && "bg-blue-50 border-blue-200 text-blue-800",
                        )}
                    >
                        {t.type === 'success' && <CheckCircle2 className="h-5 w-5 shrink-0 mt-0.5" />}
                        {t.type === 'error' && <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />}
                        {t.type === 'warning' && <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />}
                        {t.type === 'info' && <Info className="h-5 w-5 shrink-0 mt-0.5" />}
                        <p className="text-sm flex-1">{t.message}</p>
                        <button onClick={() => removeToast(t.id)} className="shrink-0 hover:opacity-70">
                            <X className="h-4 w-4" />
                        </button>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
}

export function useToast() {
    const ctx = useContext(ToastContext);
    if (!ctx) throw new Error('useToast must be inside ToastProvider');
    return ctx;
}
