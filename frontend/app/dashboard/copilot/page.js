'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { apiPost, AI_TIMEOUT } from '@/lib/api';
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
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

function buildDocumentContext(pages) {
    return (pages || []).map((p) => `[Page ${p.page}]\n${p.text}`).join('\n\n');
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
            </div>
            {message.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center shrink-0">
                    <User className="h-4 w-4 text-muted-foreground" />
                </div>
            )}
        </div>
    );
}

export function ResearchDeskExperience({
    embedded = false,
    heading = 'Research Desk',
    description = 'Analyse documents, interrogate them, and connect them to parliamentary memory.',
}) {
    const { user } = useAuth();
    const color = user?.theme_color || '#006a4d';

    const [docPages, setDocPages] = useState([]);
    const [docFilename, setDocFilename] = useState('');
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState('');
    const [activeTab, setActiveTab] = useState('analyse');
    const [analysisDepth, setAnalysisDepth] = useState('Quick Scan');
    const [analysisLanguage, setAnalysisLanguage] = useState('English');
    const [analysis, setAnalysis] = useState('');
    const [analysisLoading, setAnalysisLoading] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [chatLoading, setChatLoading] = useState(false);
    const fileRef = useRef(null);
    const endRef = useRef(null);

    const docContext = useMemo(() => buildDocumentContext(docPages), [docPages]);
    const pageCount = docPages.length;
    const charCount = docContext.length;

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const runAnalysis = async (opts = {}) => {
        const content = opts.content ?? docContext;
        const filename = opts.filename ?? docFilename;
        if (!content.trim()) {
            setError('Upload a PDF before running structured analysis.');
            return;
        }
        setAnalysisLoading(true);
        setError('');
        setActiveTab('analyse');
        try {
            const data = await apiPost('/api/copilot/analyse', {
                document_text: content,
                filename: filename || 'document',
                language: analysisLanguage,
                depth: analysisDepth,
            }, { timeout: AI_TIMEOUT, noRetry: true });
            setAnalysis(data.analysis || 'No analysis returned.');
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
            const token = sessionStorage.getItem('needle_token') || localStorage.getItem('needle_token') || '';
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/copilot/upload`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}` },
                body: formData,
            });
            if (!res.ok) throw new Error('Upload failed');
            const data = await res.json();
            const pages = data.content || [];
            const filename = data.filename || file.name;
            setDocPages(pages);
            setDocFilename(filename);
            setMessages([
                {
                    role: 'assistant',
                    content: `Document loaded: ${filename} (${data.pages} pages).\nRun analysis or ask follow-up questions.`,
                },
            ]);
            await runAnalysis({ content: buildDocumentContext(pages), filename });
        } catch (err) {
            setError(`Failed to upload: ${err.message}`);
        } finally {
            setUploading(false);
        }
    };

    const askChat = async (prefill) => {
        const question = (prefill ?? input).trim();
        if (!question || chatLoading) return;
        setInput('');
        setError('');
        setActiveTab('ask');
        const nextMessages = [...messages, { role: 'user', content: question }];
        setMessages(nextMessages);
        setChatLoading(true);
        try {
            const data = await apiPost('/api/copilot/chat', {
                document_context: docContext,
                message: question,
                history: nextMessages,
            }, { timeout: AI_TIMEOUT, noRetry: true });
            setMessages([
                ...nextMessages,
                { role: 'assistant', content: data.response || data.reply || 'No response returned.' },
            ]);
        } catch (err) {
            setMessages([
                ...nextMessages,
                { role: 'assistant', content: `Error: ${err.message || 'Request failed.'}` },
            ]);
        } finally {
            setChatLoading(false);
        }
    };

    const clearSession = () => {
        setDocFilename('');
        setDocPages([]);
        setAnalysis('');
        setMessages([]);
        setInput('');
        setError('');
        setActiveTab('analyse');
    };

    const quickAskPrompts = [
        'What are the three biggest political risks here?',
        'Summarize the key government commitments and gaps.',
        'What are the strongest Parliament talking points?',
        'What should the MP ask for next?',
    ];

    return (
        <div className="space-y-6 max-w-5xl mx-auto">
            {!embedded && (
                <div>
                    <h1 className="text-2xl font-bold text-foreground">{heading}</h1>
                    <p className="text-sm text-muted-foreground mt-1">{description}</p>
                </div>
            )}

            <Card className="border-border/60">
                <CardHeader className="pb-4">
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                        <div>
                            <CardTitle className="text-base flex items-center gap-2">
                                <BookOpen className="h-4 w-4 text-primary" />
                                Research Workspace
                            </CardTitle>
                            <CardDescription className="mt-1">
                                Structured analysis first, then open-ended research against your document and parliamentary memory.
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
                                {docFilename ? 'Replace PDF' : 'Upload PDF'}
                            </Button>
                            {(docFilename || messages.length || analysis) && (
                                <Button
                                    variant="ghost"
                                    onClick={clearSession}
                                    className="text-destructive hover:text-destructive hover:bg-destructive/10 gap-2"
                                >
                                    <Trash2 className="h-4 w-4" />
                                    Clear
                                </Button>
                            )}
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="space-y-4">
                    {docFilename ? (
                        <div className="flex items-center gap-2 flex-wrap">
                            <Badge variant="secondary" className="gap-1.5">
                                <FileText className="h-3 w-3" />
                                {docFilename}
                            </Badge>
                            <Badge variant="outline">{pageCount} pages</Badge>
                            <Badge variant="outline">{Math.round(charCount / 1000)}k chars extracted</Badge>
                        </div>
                    ) : (
                        <div className="rounded-xl border border-dashed border-border px-4 py-5 bg-muted/20">
                            <p className="text-sm font-medium text-foreground">No document loaded</p>
                            <p className="text-sm text-muted-foreground mt-1">
                                Upload a bill, policy, ordinance, committee note, or briefing PDF. You can still use Ask mode for general parliamentary research without a document.
                            </p>
                        </div>
                    )}

                    {error && (
                        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                            {error}
                        </div>
                    )}
                </CardContent>
            </Card>

            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList>
                    <TabsTrigger value="analyse" className="gap-1.5">
                        <Sparkles className="h-3.5 w-3.5" />
                        Analyse
                    </TabsTrigger>
                    <TabsTrigger value="ask" className="gap-1.5">
                        <MessageSquare className="h-3.5 w-3.5" />
                        Ask
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="analyse" className="mt-6">
                    <div className="space-y-4">
                        <Card>
                            <CardHeader className="pb-4">
                                <CardTitle className="text-base">Structured Analysis</CardTitle>
                                <CardDescription>
                                    Generate a parliamentary briefing with summary, risks, stakeholder impact, talking points, and recommended action.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Depth</span>
                                    {['Quick Scan', 'Deep Dive'].map((option) => (
                                        <Button
                                            key={option}
                                            type="button"
                                            variant={analysisDepth === option ? 'default' : 'outline'}
                                            size="sm"
                                            onClick={() => setAnalysisDepth(option)}
                                        >
                                            {option}
                                        </Button>
                                    ))}
                                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider ml-3">Language</span>
                                    {['English', 'Hindi'].map((option) => (
                                        <Button
                                            key={option}
                                            type="button"
                                            variant={analysisLanguage === option ? 'default' : 'outline'}
                                            size="sm"
                                            onClick={() => setAnalysisLanguage(option)}
                                        >
                                            {option}
                                        </Button>
                                    ))}
                                    <Button
                                        onClick={() => runAnalysis()}
                                        disabled={analysisLoading || !docFilename}
                                        className="ml-auto gap-2"
                                    >
                                        {analysisLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                                        Run Analysis
                                    </Button>
                                </div>

                                {!docFilename ? (
                                    <div className="rounded-xl border border-border/60 bg-muted/20 px-4 py-10 text-center">
                                        <p className="text-sm font-medium text-foreground">Analysis needs a document</p>
                                        <p className="text-sm text-muted-foreground mt-1">
                                            Upload a PDF and Research Desk will generate a structured parliamentary brief.
                                        </p>
                                    </div>
                                ) : analysisLoading ? (
                                    <div className="rounded-xl border border-border/60 bg-muted/20 px-4 py-12 flex items-center justify-center gap-3 text-sm text-muted-foreground">
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        Building structured brief...
                                    </div>
                                ) : analysis ? (
                                    <div className="rounded-xl border border-border/60 bg-card overflow-hidden">
                                        <div className="px-4 py-3 border-b border-border/40 bg-muted/30 flex items-center gap-2">
                                            <Sparkles className="h-4 w-4 text-primary" />
                                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Analysis Output</p>
                                        </div>
                                        <div className="p-4">
                                            <pre className="whitespace-pre-wrap text-sm text-foreground leading-relaxed font-sans">
                                                {analysis}
                                            </pre>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="rounded-xl border border-border/60 bg-muted/20 px-4 py-10 text-center">
                                        <p className="text-sm font-medium text-foreground">No analysis yet</p>
                                        <p className="text-sm text-muted-foreground mt-1">
                                            Run a quick scan first, then use Ask mode for follow-up questions.
                                        </p>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </TabsContent>

                <TabsContent value="ask" className="mt-6">
                    <Card className="overflow-hidden">
                        <CardHeader className="border-b bg-muted/40 py-4">
                            <div className="flex items-center justify-between gap-4 flex-wrap">
                                <div>
                                    <CardTitle className="text-base">Research Chat</CardTitle>
                                    <CardDescription>
                                        Ask about the uploaded document, government positions, prior PQs, schemes, or next parliamentary moves.
                                    </CardDescription>
                                </div>
                                {docFilename && (
                                    <Badge variant="outline" className="gap-1.5">
                                        <FileText className="h-3 w-3" />
                                        Using {docFilename}
                                    </Badge>
                                )}
                            </div>
                            <div className="flex gap-2 flex-wrap pt-2">
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
                        </CardHeader>

                        <ScrollArea className="h-[520px] bg-muted/20">
                            <div className="p-6 space-y-4">
                                {messages.length === 0 && (
                                    <div className="rounded-xl border border-dashed border-border bg-card px-4 py-8 text-center">
                                        <p className="text-sm font-medium text-foreground">No questions yet</p>
                                        <p className="text-sm text-muted-foreground mt-1">
                                            Start with a research question. If a document is loaded, answers will combine document reading with parliamentary retrieval.
                                        </p>
                                    </div>
                                )}

                                {messages.map((message, index) => (
                                    <ResearchMessage key={index} message={message} color={color} />
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
                                    placeholder="Ask a question about the document or issue..."
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
