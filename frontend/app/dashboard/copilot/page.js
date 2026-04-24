'use client';

import { useState, useRef, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiPost } from '@/lib/api';
import { Upload, FileText, Send, Trash2, Loader2, Bot, User } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';

export default function CopilotPage() {
    const { user } = useAuth();

    const [docPages, setDocPages] = useState([]);
    const [docFilename, setDocFilename] = useState('');
    const [uploading, setUploading] = useState(false);
    const fileRef = useRef(null);

    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [chatLoading, setChatLoading] = useState(false);
    const endRef = useRef(null);

    const color = user?.theme_color || '#006a4d';
    const docContext = docPages.map(p => `[Page ${p.page}]\n${p.text}`).join('\n\n');

    useEffect(() => { 
        endRef.current?.scrollIntoView({ behavior: 'smooth' }); 
    }, [messages]);

    const handleUpload = async (file) => {
        if (!file) return;
        setUploading(true);
        try {
            const token = localStorage.getItem('needle_token') || '';
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/copilot/upload`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData,
            });
            if (!res.ok) throw new Error('Upload failed');
            const data = await res.json();
            setDocPages(data.content || []);
            setDocFilename(data.filename || file.name);
            setMessages([{ 
                role: 'assistant', 
                content: `Document loaded: **${data.filename || file.name}** (${data.pages} pages). You can now ask me questions about it.` 
            }]);
        } catch (err) {
            alert('Failed to upload: ' + err.message);
        } finally {
            setUploading(false);
        }
    };

    const askChat = async () => {
        if (!input.trim() || chatLoading) return;
        const q = input.trim();
        setInput('');
        const newMsgs = [...messages, { role: 'user', content: q }];
        setMessages(newMsgs);
        setChatLoading(true);
        try {
            const data = await apiPost('/api/copilot/chat', { 
                document_context: docContext, 
                message: q, 
                history: newMsgs,
            });
            setMessages([...newMsgs, { role: 'assistant', content: data.response || data.reply || 'No response returned.' }]);
        } catch (err) {
            setMessages([...newMsgs, { role: 'assistant', content: 'Error: ' + err.message }]);
        } finally {
            setChatLoading(false);
        }
    };

    const clearSession = () => {
        setDocFilename('');
        setDocPages([]);
        setMessages([]);
    };

    return (
        <div className="space-y-6 h-full flex flex-col">
            <div>
                <h1 className="text-2xl font-bold text-foreground">Research Desk</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    AI-powered document analysis and Q&A
                </p>
            </div>

            {!docFilename ? (
                <div className="flex-1 flex items-center justify-center p-6">
                    <Card className="w-full max-w-2xl text-center border-t-4 border-t-primary">
                        <CardHeader>
                            <CardTitle>AI Co-Pilot</CardTitle>
                            <CardDescription>
                                Upload a document to start analyzing
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="pb-12 pt-8">
                            <div className="flex flex-col items-center">
                                <div className="w-20 h-20 rounded-2xl bg-muted flex items-center justify-center mb-6">
                                    <FileText className="h-10 w-10 text-muted-foreground" />
                                </div>
                                <h3 className="text-xl font-bold text-foreground mb-2">
                                    Upload a PDF Document
                                </h3>
                                <p className="text-muted-foreground mb-8">
                                    Bills, Acts, Ordinances, Policy Documents
                                </p>

                                <input 
                                    type="file" 
                                    ref={fileRef} 
                                    className="hidden" 
                                    accept=".pdf" 
                                    onChange={e => handleUpload(e.target.files[0])} 
                                />

                                <Button 
                                    variant="outline"
                                    size="lg"
                                    onClick={() => fileRef.current?.click()} 
                                    disabled={uploading}
                                    className="gap-2 border-primary text-primary hover:bg-primary/10"
                                >
                                    {uploading ? (
                                        <>
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                            Scanning...
                                        </>
                                    ) : (
                                        <>
                                            <Upload className="h-4 w-4" />
                                            Choose PDF File
                                        </>
                                    )}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            ) : (
                <Card className="flex-1 flex flex-col overflow-hidden" style={{ minHeight: 600 }}>
                    <CardHeader className="border-b bg-muted/50 py-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle className="text-base">AI Co-Pilot</CardTitle>
                                <CardDescription className="flex items-center gap-2 mt-1">
                                    <FileText className="h-3 w-3" />
                                    Analyzing: {docFilename}
                                </CardDescription>
                            </div>
                            <Button 
                                variant="ghost" 
                                size="sm" 
                                onClick={clearSession}
                                className="text-destructive hover:text-destructive hover:bg-destructive/10"
                            >
                                <Trash2 className="h-4 w-4" />
                                Clear Session
                            </Button>
                        </div>
                    </CardHeader>

                    <ScrollArea className="flex-1 bg-muted/30">
                        <div className="p-6 space-y-4">
                            {messages.map((m, i) => (
                                <div 
                                    key={i} 
                                    className={cn(
                                        "flex gap-3",
                                        m.role === 'user' ? 'justify-end' : 'justify-start'
                                    )}
                                >
                                    {m.role === 'assistant' && (
                                        <div 
                                            className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-white"
                                            style={{ background: color }}
                                        >
                                            <Bot className="h-4 w-4" />
                                        </div>
                                    )}
                                    <div 
                                        className={cn(
                                            "max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed",
                                            m.role === 'user' 
                                                ? 'text-white rounded-br-md' 
                                                : 'bg-card border shadow-sm text-foreground rounded-bl-md'
                                        )}
                                        style={m.role === 'user' ? { background: color } : {}}
                                    >
                                        {m.content}
                                    </div>
                                    {m.role === 'user' && (
                                        <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center shrink-0">
                                            <User className="h-4 w-4 text-muted-foreground" />
                                        </div>
                                    )}
                                </div>
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
                                        Thinking...
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
                                onChange={e => setInput(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && askChat()}
                                placeholder="Ask any question about the document..."
                                className="flex-1"
                            />
                            <Button 
                                onClick={askChat} 
                                disabled={chatLoading || !input.trim()}
                                style={{ background: color }}
                            >
                                <Send className="h-4 w-4" />
                                Send
                            </Button>
                        </div>
                    </div>
                </Card>
            )}
        </div>
    );
}
