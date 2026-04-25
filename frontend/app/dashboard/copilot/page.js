'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { apiDelete, apiGet, apiPost, AI_TIMEOUT, API_BASE } from '@/lib/api';
import {
    Upload,
    FileText,
    Send,
    Trash2,
    Loader2,
    Bot,
    User,
    Search,
    Sparkles,
    MessageSquare,
    BookOpen,
    Plus,
    Clock3,
    Files,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

function buildDocumentContext(documents) {
    return (documents || [])
        .map((doc) => {
            const pages = Array.isArray(doc?.pages) ? doc.pages : [];
            const body = pages.length
                ? pages.map((page) => `[Page ${page.page}]\n${page.text}`).join('\n\n')
                : '';
            return `[Document: ${doc.filename || 'document'}]\n${body}`.trim();
        })
        .filter(Boolean)
        .join('\n\n');
}

function buildResearchUrl(routeBase, fixedParams, sessionId) {
    const params = new URLSearchParams();
    Object.entries(fixedParams || {}).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
            params.set(key, String(value));
        }
    });
    if (sessionId) {
        params.set('session', String(sessionId));
    }
    const query = params.toString();
    return query ? `${routeBase}?${query}` : routeBase;
}

function SourceList({ sources }) {
    if (!sources?.length) return null;
    return (
        <div className="mt-3 flex flex-wrap gap-2">
            {sources.map((source, index) => (
                <Badge key={`${source.citation || source.title || 'src'}-${index}`} variant="secondary" className="max-w-full">
                    <span className="truncate">
                        {source.citation || source.title || source.source_type || `Source ${index + 1}`}
                    </span>
                </Badge>
            ))}
        </div>
    );
}

function ResearchMessage({ message, color }) {
    return (
        <div
            className={cn(
                'flex gap-3',
                message.role === 'user' ? 'justify-end' : 'justify-start'
            )}
        >
            {message.role === 'assistant' && (
                <div
                    className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-white"
                    style={{ background: color }}
                >
                    <Bot className="h-4 w-4" />
                </div>
            )}
            <div
                className={cn(
                    'max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap',
                    message.role === 'user'
                        ? 'text-white rounded-br-md'
                        : 'bg-card border shadow-sm text-foreground rounded-bl-md'
                )}
                style={message.role === 'user' ? { background: color } : {}}
            >
                {message.content}
                <SourceList sources={message.sources} />
            </div>
            {message.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center shrink-0">
                    <User className="h-4 w-4 text-muted-foreground" />
                </div>
            )}
        </div>
    );
}

function SessionCard({ item, active, onClick }) {
    return (
        <button
            type="button"
            onClick={onClick}
            className={cn(
                'w-full rounded-xl border p-3 text-left transition-colors',
                active ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/40'
            )}
        >
            <div className="text-sm font-medium text-foreground line-clamp-2">
                {item.title || 'Research Session'}
            </div>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                    <Files className="h-3 w-3" />
                    {item.document_count || 0} docs
                </span>
                <span className="inline-flex items-center gap-1">
                    <MessageSquare className="h-3 w-3" />
                    {item.message_count || 0} msgs
                </span>
            </div>
        </button>
    );
}

export function ResearchDeskExperience({
    embedded = false,
    heading = 'Research Desk',
    description = 'Analyse documents, interrogate them, and connect them to parliamentary memory.',
    routeBase = '/dashboard/sansadai',
    fixedParams = { tab: 'research' },
    initialSessionId = null,
}) {
    const { user } = useAuth();
    const router = useRouter();
    const color = user?.theme_color || '#006a4d';

    const parsedInitialSessionId = useMemo(() => {
        const numeric = Number(initialSessionId);
        return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
    }, [initialSessionId]);

    const [sessions, setSessions] = useState([]);
    const [sessionsLoading, setSessionsLoading] = useState(true);
    const [sessionLoading, setSessionLoading] = useState(false);
    const [selectedSessionId, setSelectedSessionId] = useState(parsedInitialSessionId);
    const [sessionTitle, setSessionTitle] = useState('Research Session');
    const [documents, setDocuments] = useState([]);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState('');
    const [activeTab, setActiveTab] = useState('analyse');
    const [analysisDepth, setAnalysisDepth] = useState('Quick Scan');
    const [analysisLanguage, setAnalysisLanguage] = useState('English');
    const [analysis, setAnalysis] = useState('');
    const [analysisSources, setAnalysisSources] = useState([]);
    const [analysisLoading, setAnalysisLoading] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [chatLoading, setChatLoading] = useState(false);
    const fileRef = useRef(null);
    const endRef = useRef(null);

    const docContext = useMemo(() => buildDocumentContext(documents), [documents]);
    const documentCount = documents.length;
    const pageCount = useMemo(
        () => documents.reduce((sum, doc) => sum + Number(doc.page_count || 0), 0),
        [documents]
    );
    const charCount = useMemo(
        () => documents.reduce((sum, doc) => sum + Number(doc.char_count || 0), 0),
        [documents]
    );

    const resetWorkspace = useCallback(() => {
        setSessionTitle('Research Session');
        setDocuments([]);
        setAnalysis('');
        setAnalysisSources([]);
        setMessages([]);
        setInput('');
        setError('');
        setActiveTab('analyse');
        setAnalysisDepth('Quick Scan');
        setAnalysisLanguage('English');
    }, []);

    const syncSessionUrl = useCallback((sessionId) => {
        router.replace(buildResearchUrl(routeBase, fixedParams, sessionId), { scroll: false });
    }, [fixedParams, routeBase, router]);

    const loadSessions = useCallback(async () => {
        setSessionsLoading(true);
        try {
            const data = await apiGet('/api/copilot/sessions');
            setSessions(data.items || []);
        } catch (err) {
            setError(err.message || 'Failed to load research sessions.');
        } finally {
            setSessionsLoading(false);
        }
    }, []);

    const applySessionPayload = useCallback((payload) => {
        setSessionTitle(payload.title || 'Research Session');
        setDocuments(payload.documents || []);
        setMessages(payload.messages || []);
        setAnalysis(payload.latest_analysis || '');
        setAnalysisLanguage(payload.analysis_language || 'English');
        setAnalysisDepth(payload.analysis_depth || 'Quick Scan');
        setAnalysisSources([]);
        setError('');
    }, []);

    const loadSession = useCallback(async (sessionId) => {
        if (!sessionId) {
            resetWorkspace();
            return;
        }
        setSessionLoading(true);
        try {
            const data = await apiGet(`/api/copilot/sessions/${sessionId}`);
            applySessionPayload(data);
        } catch (err) {
            setError(err.message || 'Failed to load research session.');
        } finally {
            setSessionLoading(false);
        }
    }, [applySessionPayload, resetWorkspace]);

    const createSession = useCallback(async (title = '') => {
        const data = await apiPost('/api/copilot/sessions', { title });
        setSelectedSessionId(data.id);
        setSessionTitle(data.title || 'Research Session');
        syncSessionUrl(data.id);
        await loadSessions();
        return data.id;
    }, [loadSessions, syncSessionUrl]);

    const ensureSession = useCallback(async (title = '') => {
        if (selectedSessionId) return selectedSessionId;
        return createSession(title);
    }, [createSession, selectedSessionId]);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    useEffect(() => {
        loadSessions();
    }, [loadSessions]);

    useEffect(() => {
        setSelectedSessionId(parsedInitialSessionId);
    }, [parsedInitialSessionId]);

    useEffect(() => {
        syncSessionUrl(selectedSessionId);
        loadSession(selectedSessionId);
    }, [loadSession, selectedSessionId, syncSessionUrl]);

    const handleNewSession = async () => {
        resetWorkspace();
        setSelectedSessionId(null);
        setError('');
        await createSession('Research Session');
    };

    const handleDeleteSession = async () => {
        if (!selectedSessionId) return;
        setError('');
        try {
            await apiDelete(`/api/copilot/sessions/${selectedSessionId}`);
            resetWorkspace();
            setSelectedSessionId(null);
            syncSessionUrl(null);
            await loadSessions();
        } catch (err) {
            setError(err.message || 'Failed to delete research session.');
        }
    };

    const runAnalysis = async (opts = {}) => {
        const sessionId = opts.sessionId || selectedSessionId;
        const content = opts.content ?? docContext;
        const filename = opts.filename ?? (documents[0]?.filename || 'document');
        if (!content.trim()) {
            setError('Upload at least one PDF before running structured analysis.');
            return;
        }
        setAnalysisLoading(true);
        setError('');
        setActiveTab('analyse');
        try {
            const data = await apiPost('/api/copilot/analyse', {
                session_id: sessionId,
                document_text: content,
                filename,
                language: analysisLanguage,
                depth: analysisDepth,
            }, { timeout: AI_TIMEOUT, noRetry: true });
            setAnalysis(data.analysis || 'No analysis returned.');
            setAnalysisSources(data.sources || []);
            if (data.documents) {
                setDocuments(data.documents);
            }
            if (data.session_id) {
                setSelectedSessionId(data.session_id);
            }
            if (data.session_title) {
                setSessionTitle(data.session_title);
            }
            await loadSessions();
        } catch (err) {
            setError(err.message || 'Failed to analyse document.');
        } finally {
            setAnalysisLoading(false);
        }
    };

    const handleUpload = async (file) => {
        if (!file) return;
        setUploading(true);
        setError('');
        try {
            const sessionId = await ensureSession(file.name);
            const token = sessionStorage.getItem('needle_token') || localStorage.getItem('needle_token') || '';
            const formData = new FormData();
            formData.append('file', file);
            formData.append('session_id', String(sessionId));
            const res = await fetch(`${API_BASE}/api/copilot/upload`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}` },
                body: formData,
            });
            if (!res.ok) throw new Error('Upload failed');
            const data = await res.json();
            setSelectedSessionId(data.session_id);
            setSessionTitle(data.session_title || 'Research Session');
            setDocuments(data.documents || []);
            setMessages((prev) => [
                ...prev,
                {
                    role: 'assistant',
                    content: `Added ${data.filename || file.name} to this research workspace.`,
                    sources: [],
                },
            ]);
            await runAnalysis({
                sessionId: data.session_id,
                content: buildDocumentContext(data.documents || []),
                filename: data.filename || file.name,
            });
        } catch (err) {
            setError(`Failed to upload: ${err.message}`);
        } finally {
            setUploading(false);
            if (fileRef.current) fileRef.current.value = '';
        }
    };

    const askChat = async (prefill) => {
        const question = (prefill ?? input).trim();
        if (!question || chatLoading) return;
        setInput('');
        setError('');
        setActiveTab('ask');

        const sessionId = await ensureSession(question);
        const nextMessages = [...messages, { role: 'user', content: question, sources: [] }];
        setMessages(nextMessages);
        setChatLoading(true);
        try {
            const data = await apiPost('/api/copilot/chat', {
                session_id: sessionId,
                document_context: docContext,
                message: question,
                history: nextMessages,
            }, { timeout: AI_TIMEOUT, noRetry: true });
            setSelectedSessionId(data.session_id);
            setSessionTitle(data.session_title || sessionTitle);
            if (data.documents) {
                setDocuments(data.documents);
            }
            setMessages([
                ...nextMessages,
                {
                    role: 'assistant',
                    content: data.response || data.reply || 'No response returned.',
                    sources: data.sources || [],
                },
            ]);
            await loadSessions();
        } catch (err) {
            setMessages([
                ...nextMessages,
                { role: 'assistant', content: `Error: ${err.message || 'Request failed.'}`, sources: [] },
            ]);
        } finally {
            setChatLoading(false);
        }
    };

    const quickAskPrompts = [
        'What are the three biggest political risks here?',
        'Summarize the key government commitments and gaps.',
        'What are the strongest Parliament talking points?',
        'What should the MP ask for next?',
    ];

    return (
        <div className="space-y-6 max-w-6xl mx-auto">
            {!embedded && (
                <div>
                    <h1 className="text-2xl font-bold text-foreground">{heading}</h1>
                    <p className="text-sm text-muted-foreground mt-1">{description}</p>
                </div>
            )}

            <div className="grid gap-6 xl:grid-cols-[280px,minmax(0,1fr)]">
                <Card className="border-border/60 xl:sticky xl:top-24 h-fit">
                    <CardHeader className="pb-4">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <CardTitle className="text-base">Research Sessions</CardTitle>
                                <CardDescription className="mt-1">
                                    Saved workspaces with documents, analysis, and chat.
                                </CardDescription>
                            </div>
                            <Button size="sm" variant="outline" onClick={handleNewSession} className="gap-2">
                                <Plus className="h-4 w-4" />
                                New
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent>
                        {sessionsLoading ? (
                            <div className="text-sm text-muted-foreground flex items-center gap-2">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Loading sessions...
                            </div>
                        ) : sessions.length ? (
                            <div className="space-y-3">
                                {sessions.map((item) => (
                                    <SessionCard
                                        key={item.id}
                                        item={item}
                                        active={item.id === selectedSessionId}
                                        onClick={() => setSelectedSessionId(item.id)}
                                    />
                                ))}
                            </div>
                        ) : (
                            <div className="rounded-xl border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                                No saved research sessions yet.
                            </div>
                        )}
                    </CardContent>
                </Card>

                <div className="space-y-6">
                    <Card className="border-border/60">
                        <CardHeader className="pb-4">
                            <div className="flex items-start justify-between gap-4 flex-wrap">
                                <div>
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <BookOpen className="h-4 w-4 text-primary" />
                                        {sessionTitle || 'Research Workspace'}
                                    </CardTitle>
                                    <CardDescription className="mt-1">
                                        Persistent research workspace with multi-document uploads, structured analysis, and evidence-backed chat.
                                    </CardDescription>
                                </div>
                                <div className="flex items-center gap-2 flex-wrap">
                                    <input
                                        type="file"
                                        ref={fileRef}
                                        className="hidden"
                                        accept=".pdf"
                                        onChange={(e) => handleUpload(e.target.files?.[0])}
                                    />
                                    <Button
                                        variant="outline"
                                        onClick={() => fileRef.current?.click()}
                                        disabled={uploading}
                                        className="gap-2"
                                    >
                                        {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                                        {documentCount ? 'Add PDF' : 'Upload PDF'}
                                    </Button>
                                    {selectedSessionId ? (
                                        <Button
                                            variant="ghost"
                                            onClick={handleDeleteSession}
                                            className="text-destructive hover:text-destructive hover:bg-destructive/10 gap-2"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                            Delete
                                        </Button>
                                    ) : null}
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex items-center gap-2 flex-wrap">
                                {selectedSessionId ? (
                                    <Badge variant="secondary" className="gap-1.5">
                                        <Clock3 className="h-3 w-3" />
                                        Session #{selectedSessionId}
                                    </Badge>
                                ) : null}
                                <Badge variant="secondary" className="gap-1.5">
                                    <Files className="h-3 w-3" />
                                    {documentCount} documents
                                </Badge>
                                <Badge variant="secondary" className="gap-1.5">
                                    <FileText className="h-3 w-3" />
                                    {pageCount} pages
                                </Badge>
                                <Badge variant="secondary">{charCount.toLocaleString()} chars</Badge>
                            </div>

                            {documents.length ? (
                                <div className="flex flex-wrap gap-2">
                                    {documents.map((doc) => (
                                        <Badge key={doc.id || doc.filename} variant="outline" className="gap-1.5">
                                            <FileText className="h-3 w-3" />
                                            {doc.filename}
                                        </Badge>
                                    ))}
                                </div>
                            ) : (
                                <div className="rounded-xl border border-dashed border-border bg-muted/20 px-4 py-6 text-center">
                                    <p className="text-sm font-medium text-foreground">No PDFs in this workspace yet</p>
                                    <p className="text-sm text-muted-foreground mt-1">
                                        Upload one or more briefing documents, reports, or notes. The workspace will persist across visits.
                                    </p>
                                </div>
                            )}

                            {error ? (
                                <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                                    {error}
                                </div>
                            ) : null}
                        </CardContent>
                    </Card>

                    <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
                        <TabsList className="grid grid-cols-2 w-full">
                            <TabsTrigger value="analyse" className="gap-2">
                                <Sparkles className="h-4 w-4" />
                                Analyse
                            </TabsTrigger>
                            <TabsTrigger value="ask" className="gap-2">
                                <MessageSquare className="h-4 w-4" />
                                Ask
                            </TabsTrigger>
                        </TabsList>

                        <TabsContent value="analyse" className="space-y-4">
                            <Card className="border-border/60">
                                <CardHeader>
                                    <CardTitle className="text-base">Structured Analysis</CardTitle>
                                    <CardDescription>
                                        Use the saved document bundle in this session to generate a briefing note, risks, and parliamentary action points.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="flex flex-wrap gap-3">
                                        <div className="space-y-2">
                                            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Depth</p>
                                            <div className="flex gap-2">
                                                {['Quick Scan', 'Deep Dive'].map((option) => (
                                                    <Button
                                                        key={option}
                                                        type="button"
                                                        size="sm"
                                                        variant={analysisDepth === option ? 'default' : 'outline'}
                                                        onClick={() => setAnalysisDepth(option)}
                                                    >
                                                        {option}
                                                    </Button>
                                                ))}
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Language</p>
                                            <div className="flex gap-2">
                                                {['English', 'Hindi'].map((option) => (
                                                    <Button
                                                        key={option}
                                                        type="button"
                                                        size="sm"
                                                        variant={analysisLanguage === option ? 'default' : 'outline'}
                                                        onClick={() => setAnalysisLanguage(option)}
                                                    >
                                                        {option}
                                                    </Button>
                                                ))}
                                            </div>
                                        </div>
                                    </div>

                                    <Button
                                        onClick={() => runAnalysis()}
                                        disabled={analysisLoading || !documents.length}
                                        className="gap-2"
                                        style={{ background: color }}
                                    >
                                        {analysisLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                                        Run Analysis
                                    </Button>

                                    {sessionLoading ? (
                                        <div className="rounded-xl border bg-card px-4 py-8 text-sm text-muted-foreground flex items-center gap-2">
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                            Loading workspace...
                                        </div>
                                    ) : analysisLoading ? (
                                        <div className="rounded-xl border bg-card px-4 py-8 text-sm text-muted-foreground flex items-center gap-2">
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                            Analysing documents...
                                        </div>
                                    ) : analysis ? (
                                        <div className="rounded-2xl border bg-card shadow-sm">
                                            <div className="border-b px-5 py-3">
                                                <p className="text-sm font-medium text-foreground">Research Brief</p>
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    Saved to this session and reusable in follow-up chat.
                                                </p>
                                            </div>
                                            <div className="px-5 py-4">
                                                <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                                                    {analysis}
                                                </div>
                                                <SourceList sources={analysisSources} />
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="rounded-xl border border-dashed border-border bg-card px-4 py-8 text-center">
                                            <p className="text-sm font-medium text-foreground">No analysis yet</p>
                                            <p className="text-sm text-muted-foreground mt-1">
                                                Upload PDFs and run a structured analysis. The result will persist inside this research session.
                                            </p>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </TabsContent>

                        <TabsContent value="ask" className="space-y-4">
                            <Card className="border-border/60 overflow-hidden">
                                <CardHeader className="border-b bg-muted/20">
                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div>
                                            <CardTitle className="text-base">Research Chat</CardTitle>
                                            <CardDescription className="mt-1">
                                                Ask across the saved document bundle and parliamentary memory. Assistant messages carry their evidence sources.
                                            </CardDescription>
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                            {quickAskPrompts.map((prompt) => (
                                                <Button
                                                    key={prompt}
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => askChat(prompt)}
                                                    disabled={chatLoading}
                                                    className="text-xs"
                                                >
                                                    {prompt}
                                                </Button>
                                            ))}
                                        </div>
                                    </div>
                                </CardHeader>

                                <ScrollArea className="h-[520px] bg-muted/20">
                                    <div className="p-6 space-y-4">
                                        {messages.length === 0 && (
                                            <div className="rounded-xl border border-dashed border-border bg-card px-4 py-8 text-center">
                                                <p className="text-sm font-medium text-foreground">No questions yet</p>
                                                <p className="text-sm text-muted-foreground mt-1">
                                                    Start with a research question. This session will retain the conversation, uploaded documents, and the latest analysis.
                                                </p>
                                            </div>
                                        )}

                                        {messages.map((message, index) => (
                                            <ResearchMessage key={message.id || index} message={message} color={color} />
                                        ))}

                                        {chatLoading && (
                                            <div className="flex gap-3 justify-start">
                                                <div
                                                    className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-white"
                                                    style={{ background: color }}
                                                >
                                                    <Bot className="h-4 w-4" />
                                                </div>
                                                <div className="bg-card border shadow-sm px-4 py-3 rounded-2xl rounded-bl-md text-sm text-muted-foreground flex items-center gap-2">
                                                    <Loader2 className="h-4 w-4 animate-spin" />
                                                    Researching...
                                                </div>
                                            </div>
                                        )}
                                        <div ref={endRef} />
                                    </div>
                                </ScrollArea>

                                <div className="p-4 bg-card border-t">
                                    <div className="flex gap-3">
                                        <Input
                                            value={input}
                                            onChange={(e) => setInput(e.target.value)}
                                            onKeyDown={(e) => e.key === 'Enter' && askChat()}
                                            placeholder="Ask a question about the documents or issue..."
                                            className="flex-1"
                                        />
                                        <Button
                                            onClick={() => askChat()}
                                            disabled={chatLoading || !input.trim()}
                                            style={{ background: color }}
                                            className="gap-2"
                                        >
                                            <Send className="h-4 w-4" />
                                            Ask
                                        </Button>
                                    </div>
                                </div>
                            </Card>
                        </TabsContent>
                    </Tabs>
                </div>
            </div>
        </div>
    );
}

export default function CopilotPage() {
    const router = useRouter();

    useEffect(() => {
        router.replace('/dashboard/sansadai?tab=research');
    }, [router]);

    return (
        <div className="min-h-[60vh] flex items-center justify-center">
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Redirecting to SansadAI Research...
            </div>
        </div>
    );
}
