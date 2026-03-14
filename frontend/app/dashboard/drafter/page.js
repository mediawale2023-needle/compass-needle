'use client';

import { useState } from 'react';
import { useAuth } from '@/lib/auth';
import { apiPost, AI_TIMEOUT } from '@/lib/api';
import { useSearchParams } from 'next/navigation';
import { FileText, HelpCircle, Download, Save, Loader2, CheckCircle, Sparkles } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';

const RECIPIENT_TYPES = ['Cabinet Minister', 'Minister of State', 'Secretary to GoI', 'Chief Secretary', 'District Collector', 'Other Official'];
const TONES = ['Assertive (Opposition Style)', 'Requesting (Ministerial Courtesy)', 'Formal (Neutral)'];
const LANGUAGES = ['English', 'Hindi', 'Kannada', 'Marathi', 'Tamil', 'Telugu', 'Bengali'];

export default function DrafterPage() {
    const { user } = useAuth();
    const searchParams = useSearchParams();

    const [mode, setMode] = useState('letter');

    // Letter fields
    const [recipientType, setRecipientType] = useState('Cabinet Minister');
    const [recipientName, setRecipientName] = useState(searchParams.get('recipient') || '');
    const [ministry, setMinistry] = useState('');
    const [subject, setSubject] = useState(searchParams.get('subject') || '');
    const [reference, setReference] = useState('');
    const [keyPoints, setKeyPoints] = useState(searchParams.get('context') || '');
    const [tone, setTone] = useState('Assertive (Opposition Style)');
    const [language, setLanguage] = useState('English');

    // PQ fields
    const [pqSubject, setPqSubject] = useState('');
    const [pqMinistry, setPqMinistry] = useState('');
    const [pqPoints, setPqPoints] = useState('');
    const [pqLang, setPqLang] = useState('English');

    const [draft, setDraft] = useState('');
    const [loading, setLoading] = useState(false);
    const [saved, setSaved] = useState(false);
    const color = user?.theme_color || '#006a4d';

    const generate = async () => {
        setLoading(true);
        setDraft('');
        setSaved(false);
        try {
            const body = mode === 'letter'
                ? { mode, subject, recipient_name: recipientName, recipient_type: recipientType, ministry, reference, key_points: keyPoints, tone, language }
                : { mode: 'question', subject: pqSubject, ministry: pqMinistry, key_points: pqPoints, language: pqLang };
            const data = await apiPost('/api/drafter/generate', body, { timeout: AI_TIMEOUT, noRetry: true });
            setDraft(data.content || 'No content generated.');
        } catch (err) {
            setDraft('Error: ' + err.message);
        } finally {
            setLoading(false);
        }
    };

    const downloadDraft = () => {
        const blob = new Blob([draft], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const title = mode === 'letter' ? (subject || 'letter') : (pqSubject || 'question');
        a.download = `${mode === 'letter' ? 'Letter' : 'PQ'}_${title.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 30)}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const saveDraft = async () => {
        const title = mode === 'letter' ? (subject || 'Untitled Letter') : (pqSubject || 'Untitled Question');
        try {
            await apiPost('/api/history/save', {
                activity_type: mode === 'letter' ? 'draft_letter' : 'draft_question',
                title,
                content: draft,
                metadata: mode === 'letter'
                    ? { recipient: recipientName, ministry, tone, language }
                    : { ministry: pqMinistry, language: pqLang },
            });
            setSaved(true);
        } catch (err) {
            alert('Failed to save: ' + err.message);
        }
    };

    return (
        <div className="space-y-6 max-w-4xl mx-auto">
            <div>
                <h1 className="text-2xl font-bold text-foreground">Drafter</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    AI-powered letter and parliamentary question drafting
                </p>
            </div>

            <Card>
                <CardHeader className="pb-0">
                    <Tabs value={mode} onValueChange={(v) => { setMode(v); setDraft(''); setSaved(false); }}>
                        <TabsList className="grid w-full grid-cols-2 max-w-md">
                            <TabsTrigger value="letter" className="gap-2">
                                <FileText className="h-4 w-4" />
                                Write Letter
                            </TabsTrigger>
                            <TabsTrigger value="question" className="gap-2">
                                <HelpCircle className="h-4 w-4" />
                                Parliamentary Question
                            </TabsTrigger>
                        </TabsList>
                    </Tabs>
                </CardHeader>

                <CardContent className="pt-6 space-y-6">
                    {mode === 'letter' ? (
                        <>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <Label>Recipient Type</Label>
                                    <Select value={recipientType} onValueChange={setRecipientType}>
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {RECIPIENT_TYPES.map(t => (
                                                <SelectItem key={t} value={t}>{t}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label>Recipient Name</Label>
                                    <Input
                                        value={recipientName}
                                        onChange={e => setRecipientName(e.target.value)}
                                        placeholder="e.g., Secretary, Ministry Name"
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label>Ministry/Department</Label>
                                <Input
                                    value={ministry}
                                    onChange={e => setMinistry(e.target.value)}
                                    placeholder="e.g., Ministry of Road Transport and Highways"
                                />
                            </div>

                            <div className="space-y-2">
                                <Label>Subject</Label>
                                <Input
                                    value={subject}
                                    onChange={e => setSubject(e.target.value)}
                                    placeholder="Brief subject line"
                                />
                            </div>

                            <div className="space-y-2">
                                <Label>Reference No. (Optional)</Label>
                                <Input
                                    value={reference}
                                    onChange={e => setReference(e.target.value)}
                                    placeholder="e.g., MP/2026/123"
                                />
                            </div>

                            <div className="space-y-2">
                                <Label>Key Points (one per line)</Label>
                                <Textarea
                                    value={keyPoints}
                                    onChange={e => setKeyPoints(e.target.value)}
                                    placeholder="Enter key points, one per line"
                                    rows={4}
                                />
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <Label>Language</Label>
                                    <Select value={language} onValueChange={setLanguage}>
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {LANGUAGES.map(l => (
                                                <SelectItem key={l} value={l}>{l}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label>Tone</Label>
                                    <Select value={tone} onValueChange={setTone}>
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {TONES.map(t => (
                                                <SelectItem key={t} value={t}>{t}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="space-y-6">
                            <div className="space-y-2">
                                <Label>Target Ministry</Label>
                                <Input
                                    value={pqMinistry}
                                    onChange={e => setPqMinistry(e.target.value)}
                                    placeholder="Target Ministry"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Question Subject</Label>
                                <Input
                                    value={pqSubject}
                                    onChange={e => setPqSubject(e.target.value)}
                                    placeholder="Issue to raise"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Specific Data Points Needed</Label>
                                <Textarea
                                    value={pqPoints}
                                    onChange={e => setPqPoints(e.target.value)}
                                    placeholder="e.g. state-wise breakdown, funds allocated vs used"
                                    rows={4}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Language</Label>
                                <Select value={pqLang} onValueChange={setPqLang}>
                                    <SelectTrigger className="w-full md:w-1/2">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="English">English</SelectItem>
                                        <SelectItem value="Hindi">Hindi</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    )}

                    <div className="pt-4 border-t flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                        <p className="text-xs text-muted-foreground">
                            Uses AI to generate a structured, formal draft
                        </p>
                        <Button
                            onClick={generate}
                            disabled={loading}
                            className="w-full sm:w-auto gap-2"
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Generating...
                                </>
                            ) : (
                                <>
                                    <Sparkles className="h-4 w-4" />
                                    Generate {mode === 'letter' ? 'Letter' : 'Question'}
                                </>
                            )}
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Results Output */}
            {draft && (
                <Card className="animate-fade-in">
                    <CardHeader className="bg-muted/50 border-b">
                        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                            <div>
                                <CardTitle className="text-base">
                                    Generated {mode === 'letter' ? 'Letter Draft' : 'Parliamentary Question'}
                                </CardTitle>
                                <CardDescription>
                                    Review and edit your draft below
                                </CardDescription>
                            </div>
                            <div className="flex flex-wrap gap-2 w-full sm:w-auto">
                                {saved ? (
                                    <Badge variant="secondary" className="bg-green-100 text-green-700 gap-1">
                                        <CheckCircle className="h-3 w-3" />
                                        Saved to Archives
                                    </Badge>
                                ) : (
                                    <Button variant="outline" size="sm" onClick={saveDraft}>
                                        <Save className="h-4 w-4" />
                                        Save to Archives
                                    </Button>
                                )}
                                <Button size="sm" onClick={downloadDraft} className="gap-2">
                                    <Download className="h-4 w-4" />
                                    Download
                                </Button>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="p-0">
                        <Textarea
                            value={draft}
                            onChange={(e) => setDraft(e.target.value)}
                            className="min-h-[400px] border-0 rounded-none rounded-b-xl resize-y font-serif text-foreground leading-relaxed focus-visible:ring-0 focus-visible:ring-offset-0"
                        />
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
