'use client';

import {
    Compass, Landmark, ClipboardCheck, Inbox, MessageCircle, Map as MapIcon,
    Server, Users, ShieldCheck, Search, Bell, ChevronRight, ChevronDown,
    LogOut, Menu, X, PanelLeftClose, HelpCircle, ArrowRight,
} from 'lucide-react';

// Destination icons, keyed by the `icon` field in lib/admin-nav.js.
export const NAV_ICONS = {
    command: Compass,
    accounts: Landmark,
    onboarding: ClipboardCheck,
    cases: Inbox,
    messaging: MessageCircle,
    geography: MapIcon,
    system: Server,
    people: Users,
    audit: ShieldCheck,
};

export {
    Search, Bell, ChevronRight, ChevronDown, LogOut, Menu, X, PanelLeftClose, HelpCircle, ArrowRight,
};
