'use client';

import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiGet } from '@/lib/api';
import { ALL_NAV_ITEMS } from '@/lib/admin-nav';
import { Search } from './icons';

/**
 * Global jump box. Searches only what Needle really has: Admin destinations
 * and accounts from /api/admin/mps (loaded on first focus). No fake
 * full-text search across cases or phone numbers.
 */
const MAX_ACCOUNTS = 6;

function normalise(text) {
    return String(text || '').toLowerCase();
}

export default function CommandSearch() {
    const router = useRouter();
    const inputRef = useRef(null);
    const listId = useId();
    const [query, setQuery] = useState('');
    const [open, setOpen] = useState(false);
    const [accounts, setAccounts] = useState(null);
    const [accountsState, setAccountsState] = useState('idle');
    const [activeIndex, setActiveIndex] = useState(0);

    const loadAccounts = useCallback(async () => {
        if (accountsState !== 'idle') return;
        setAccountsState('loading');
        try {
            const data = await apiGet('/api/admin/mps');
            setAccounts(Array.isArray(data?.mps) ? data.mps : []);
            setAccountsState('ready');
        } catch {
            setAccountsState('error');
        }
    }, [accountsState]);

    useEffect(() => {
        const onKey = (event) => {
            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
                event.preventDefault();
                inputRef.current?.focus();
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, []);

    const results = useMemo(() => {
        const q = normalise(query).trim();
        if (!q) return [];
        const destinations = ALL_NAV_ITEMS
            .filter((item) => normalise(`${item.label} ${item.group}`).includes(q))
            .map((item) => ({ key: `nav-${item.id}`, kind: 'Go to', label: item.label, detail: item.group, href: item.href }));
        const seen = new Set();
        const accountMatches = (accounts || [])
            .filter((account) => {
                const haystack = normalise(`${account.display_name} ${account.mp_name} ${account.parliamentary_constituency} ${account.profile?.constituency} ${account.profile?.state} ${account.username}`);
                return haystack.includes(q);
            })
            .filter((account) => {
                if (seen.has(account.tenant_id)) return false;
                seen.add(account.tenant_id);
                return true;
            })
            .slice(0, MAX_ACCOUNTS)
            .map((account) => ({
                key: `acct-${account.tenant_id}`,
                kind: 'Account',
                label: account.display_name || account.mp_name,
                detail: [account.profile?.constituency || account.parliamentary_constituency, account.profile?.state].filter(Boolean).join(' · '),
                href: `/dashboard/mps/${account.tenant_id}`,
            }));
        return [...destinations, ...accountMatches];
    }, [query, accounts]);

    useEffect(() => { setActiveIndex(0); }, [query]);

    const go = (result) => {
        if (!result) return;
        setOpen(false);
        setQuery('');
        inputRef.current?.blur();
        router.push(result.href);
    };

    const onKeyDown = (event) => {
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            setOpen(true);
            setActiveIndex((index) => Math.min(index + 1, Math.max(results.length - 1, 0)));
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActiveIndex((index) => Math.max(index - 1, 0));
        } else if (event.key === 'Enter') {
            event.preventDefault();
            go(results[activeIndex]);
        } else if (event.key === 'Escape') {
            setOpen(false);
            inputRef.current?.blur();
        }
    };

    const showList = open && query.trim().length > 0;

    return (
        <div className="nx-search" onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
            <Search className="nx-search-icon" size={16} strokeWidth={1.9} aria-hidden="true" />
            <input
                ref={inputRef}
                type="search"
                role="combobox"
                aria-label="Search accounts and pages"
                aria-expanded={showList}
                aria-controls={listId}
                aria-activedescendant={showList && results[activeIndex] ? `${listId}-${activeIndex}` : undefined}
                aria-autocomplete="list"
                placeholder="Search accounts and pages…"
                value={query}
                onFocus={() => { setOpen(true); loadAccounts(); }}
                onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
                onKeyDown={onKeyDown}
            />
            <kbd className="nx-kbd" aria-hidden="true">⌘ K</kbd>
            {showList && (
                <div className="nx-popover nx-search-list" role="listbox" id={listId} aria-label="Search results">
                    {results.map((result, index) => (
                        <button
                            type="button"
                            key={result.key}
                            id={`${listId}-${index}`}
                            role="option"
                            aria-selected={index === activeIndex}
                            className="nx-search-option"
                            onMouseDown={(event) => event.preventDefault()}
                            onMouseEnter={() => setActiveIndex(index)}
                            onClick={() => go(result)}
                        >
                            <span className="nx-search-kind">{result.kind}</span>
                            <span className="nx-search-label">{result.label}</span>
                            {result.detail && <span className="nx-search-detail">{result.detail}</span>}
                        </button>
                    ))}
                    {!results.length && (
                        <div className="nx-search-empty">
                            {accountsState === 'loading' ? 'Loading accounts…' : 'No matching pages or accounts'}
                        </div>
                    )}
                    {accountsState === 'error' && <div className="nx-search-empty">Account search is unavailable right now.</div>}
                </div>
            )}
        </div>
    );
}
