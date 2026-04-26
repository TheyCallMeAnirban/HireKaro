import { Rocket, History, Settings, Bell, CircleHelp, Command, Download, BarChart2, MessageSquare, AlertTriangle, ChevronLeft, ChevronRight, Hash, Upload, Loader2, ThumbsUp, ThumbsDown, Star, LogIn, LogOut, User } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect, useRef } from 'react';
import { View, Candidate, RunHistoryItem, AnalyzeJDResponse, HistoryRow, ApiCandidate, mapApiCandidate } from './types';
import { analyzeJD, getHistory, getHistoryItem, deleteHistoryItem, exportCSVUrl, uploadResume, loginUser, registerUser, logoutUser, addFeedback, getToken } from './api';

const PIPELINE_STEPS = ['Ingestion','Evaluation','Matching','Simulation','Scoring','Briefing','Ranking'];

const Sidebar = ({ activeView, onViewChange, user, onLogout }: { activeView: View; onViewChange: (v: View) => void; user: any; onLogout: () => void }) => (
  <aside className="fixed left-0 top-0 flex flex-col h-full py-8 px-5 w-[220px] bg-surface-bg border-r border-border-subtle tracking-tight z-20">
    <div className="mb-12 px-2 flex flex-col gap-1">
      <div className="flex items-center gap-3">
        <div className="w-7 h-7 bg-primary-main flex items-center justify-center rounded-sm">
          <Rocket className="text-black w-4 h-4" />
        </div>
        <h1 className="text-xl font-serif italic font-bold text-primary-main tracking-wider leading-none">HireKaro</h1>
      </div>
      <p className="text-[9px] text-text-secondary uppercase tracking-[0.3em] mt-2 font-semibold">Intelligence Guild</p>
    </div>
    <nav className="flex-1 space-y-2">
      {(['pipeline','history','settings'] as View[]).map((v) => (
        <button key={v} onClick={() => onViewChange(v)}
          className={`w-full flex items-center gap-3 px-3 py-3 rounded-sm transition-all duration-300 cursor-pointer active:scale-95 text-xs font-semibold uppercase tracking-[0.15em] ${activeView === v ? 'bg-primary-main/10 text-primary-main border-l-2 border-primary-main' : 'text-text-secondary hover:text-white hover:bg-white/5'}`}>
          {v === 'pipeline' && <Rocket className="w-4 h-4" />}
          {v === 'history' && <History className="w-4 h-4" />}
          {v === 'settings' && <Settings className="w-4 h-4" />}
          <span>{v}</span>
        </button>
      ))}
    </nav>
    <div className="mt-auto px-2 pt-6 border-t border-border-subtle">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-full border border-primary-main/30 bg-gradient-to-tr from-[#1A1D23] to-[#2D3139] overflow-hidden p-0.5 flex items-center justify-center shrink-0">
          <User className="w-5 h-5 text-primary-main/70" />
        </div>
        <div className="overflow-hidden flex-1">
          <p className="text-xs font-semibold text-white truncate font-serif italic">{user?.email?.split('@')[0] || 'Operative'}</p>
          <p className="text-[10px] text-text-secondary uppercase tracking-widest truncate">{user?.role || 'Recruiter'}</p>
        </div>
        <button onClick={onLogout} className="text-text-secondary hover:text-error transition-colors p-1 group" title="Sign Out">
          <LogOut className="w-4 h-4 group-hover:scale-110 transition-transform" />
        </button>
      </div>
    </div>
  </aside>
);

const Header = ({ lastSync }: { lastSync: string }) => (
  <header className="h-20 w-full border-b border-border-subtle flex items-center justify-between px-10 bg-surface-bg sticky top-0 z-10">
    <div className="flex items-center gap-6">
      <div className="flex items-center gap-3">
        <div className="w-2 h-2 rounded-full bg-primary-main shadow-[0_0_8px_#D4AF37]"></div>
        <span className="text-primary-main font-bold text-[11px] uppercase tracking-[0.2em] italic font-serif">Status: Operational</span>
      </div>
      <div className="h-4 w-px bg-border-subtle"></div>
      <span className="text-text-secondary text-[10px] uppercase tracking-widest font-medium">{lastSync ? `Last sync: ${lastSync}` : 'Awaiting pipeline'}</span>
    </div>
    <div className="flex items-center gap-8">
      <div className="relative group cursor-pointer">
        <Bell className="text-text-secondary group-hover:text-primary-main transition-colors w-5 h-5" />
        <span className="absolute -top-1 -right-1 w-1.5 h-1.5 bg-primary-main rounded-full border border-surface-bg"></span>
      </div>
      <CircleHelp className="text-text-secondary hover:text-white transition-colors cursor-pointer w-5 h-5" />
      <div className="bg-surface-card border border-border-subtle px-3 py-1.5 rounded-sm flex items-center gap-2">
        <span className="text-[10px] font-bold text-text-secondary flex items-center gap-1 opacity-50"><Command className="w-3 h-3" /> K</span>
      </div>
    </div>
  </header>
);

const BADGE_STYLES: Record<string, string> = {
  'Fast Track': 'text-primary-main border-primary-main/30 bg-primary-main/5',
  'Consider':   'text-blue-400   border-blue-400/30   bg-blue-400/5',
  'Pass':       'text-error       border-error/30       bg-error/5',
};

const CandidateCard = ({
  candidate,
  rawCandidate,
  onFeedback,
}: {
  candidate:    Candidate;
  rawCandidate: ApiCandidate;
  onFeedback?:  (name: string, action: 'shortlist' | 'reject' | 'hire') => Promise<void>;
}) => {
  const [showConvo, setShowConvo] = useState(false);
  const [feedback, setFeedback]   = useState<'shortlist' | 'reject' | 'hire' | null>(null);
  const recommendation = rawCandidate.fit_summary?.recommendation ?? 'Consider';
  const badgeStyle = BADGE_STYLES[recommendation] ?? BADGE_STYLES['Consider'];

  return (
  <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
    className="bg-surface-card border border-border-subtle rounded-sm p-8 flex flex-col gap-6 hover:bg-surface-hover transition-all duration-500 relative group overflow-hidden">
    <div className="absolute top-0 right-0 w-32 h-32 bg-primary-main/5 blur-[50px] rounded-full -mr-16 -mt-16 pointer-events-none transition-opacity opacity-0 group-hover:opacity-100"></div>
    <div className="flex justify-between items-start relative z-10">
      <div className="flex gap-5">
        <div className="w-12 h-12 bg-surface-bg border border-border-subtle flex items-center justify-center rounded-sm text-xs font-bold text-primary-main italic font-serif">{candidate.rank}</div>
        <div>
          <h3 className="text-2xl font-serif italic text-white tracking-tight leading-tight">{candidate.name}</h3>
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mt-1 font-semibold">{candidate.role} • {candidate.experience}</p>
        </div>
      </div>
      <span className={`px-2.5 py-1 rounded-sm border text-[9px] font-bold uppercase tracking-[0.2em] ${badgeStyle}`}>{recommendation}</span>
    </div>
    <div className="grid grid-cols-3 gap-4 py-4 relative z-10">
      {[{ label: 'Final', val: candidate.scores.final, color: 'text-white' },
        { label: 'Match', val: candidate.scores.match, color: 'text-primary-main' },
        { label: 'Interest', val: candidate.scores.interest, color: 'text-text-secondary' }
      ].map((s, i) => (
        <div key={i} className="flex flex-col items-center gap-2 border-r border-border-subtle last:border-0">
          <p className="text-[11px] uppercase tracking-widest text-text-secondary font-medium italic font-serif">{s.label}</p>
          <span className={`text-4xl font-light tracking-tighter ${s.color}`}>{s.val}</span>
        </div>
      ))}
    </div>
    <div className="flex flex-wrap gap-2 relative z-10">
      {candidate.skills.slice(0, 8).map((skill, i) => (
        <span key={i} className={`text-[9px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-sm border transition-all ${
          skill.type === 'success' ? 'text-primary-main bg-primary-main/10 border-primary-main/20' :
          skill.type === 'warning' ? 'text-primary-main bg-primary-main/5 border-primary-main/10' :
          skill.type === 'error' ? 'text-error bg-error/10 border-error/20 line-through' :
          'text-text-secondary bg-surface-bg border-border-subtle'}`}>{skill.name}</span>
      ))}
    </div>
    {candidate.quote && (
      <div className="border-l border-primary-main/50 pl-5 py-4 bg-white/5 italic text-sm font-serif text-white/70 leading-relaxed relative z-10">
        "{candidate.quote}"
      </div>
    )}
    <div className="space-y-4 relative z-10">
      <label className="text-[9px] font-bold text-text-secondary uppercase tracking-[0.3em] opacity-40">Intelligence Brief</label>
      <p className="text-sm font-light text-text-secondary leading-relaxed">{candidate.brief}</p>
      {candidate.strengths[0] && (
        <div className="pt-2 space-y-2">
          <div className="flex items-center gap-3 p-3 bg-white/5 rounded-sm border border-white/5">
            <div className="w-1.5 h-1.5 bg-primary-main rounded-full shadow-[0_0_6px_#D4AF37]"></div>
            <p className="text-xs italic font-serif"><span className="text-primary-main font-semibold mr-2 italic">Strategic Asset:</span>{candidate.strengths[0]}</p>
          </div>
        </div>
      )}
    </div>
    {/* Simulated conversation — expandable */}
    {rawCandidate.conversation?.length > 0 && (
      <div className="relative z-10">
        <button
          onClick={() => setShowConvo(v => !v)}
          className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-text-secondary hover:text-primary-main transition-colors italic"
        >
          <MessageSquare className="w-3.5 h-3.5" />
          {showConvo ? 'Hide' : 'View'} Outreach Simulation
        </button>
        <AnimatePresence>
          {showConvo && (
            <motion.div
              initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }} className="mt-4 space-y-3 overflow-hidden"
            >
              {rawCandidate.conversation.map((msg, i) => (
                <div key={i} className={`flex gap-3 ${
                  msg.role === 'agent' ? 'justify-start' : 'justify-end'
                }`}>
                  <div className={`max-w-[85%] px-4 py-3 rounded-sm text-xs font-light leading-relaxed ${
                    msg.role === 'agent'
                      ? 'bg-white/5 border border-white/10 text-white/60 rounded-tl-none'
                      : 'bg-primary-main/10 border border-primary-main/20 text-primary-main/80 rounded-tr-none'
                  }`}>
                    <span className="block text-[9px] font-bold uppercase tracking-widest opacity-50 mb-1">
                      {msg.role === 'agent' ? 'Recruiter' : candidate.name}
                    </span>
                    {msg.text}
                  </div>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    )}
    {/* Feedback buttons */}
    <div className="flex gap-2 mt-auto relative z-10">
      {(['shortlist','reject','hire'] as const).map(action => {
        const active = feedback === action;
        const styles = {
          shortlist: { icon: <ThumbsUp  className="w-3.5 h-3.5" />, label: 'Shortlist', activeClass: 'bg-primary-main/20 border-primary-main text-primary-main' },
          reject:    { icon: <ThumbsDown className="w-3.5 h-3.5" />, label: 'Pass',      activeClass: 'bg-error/20     border-error     text-error'         },
          hire:      { icon: <Star       className="w-3.5 h-3.5" />, label: 'Hire',      activeClass: 'bg-green-500/20 border-green-500 text-green-400'      },
        }[action];
        return (
          <button key={action}
            disabled={!!feedback}
            onClick={async () => {
              setFeedback(action);
              if (rawCandidate.fit_summary && onFeedback) {
                await onFeedback(rawCandidate.name ?? candidate.name, action).catch(() => {});
              }
            }}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-3 rounded-sm border text-[9px] font-bold uppercase tracking-widest transition-all italic ${
              active
                ? styles.activeClass
                : 'border-white/10 text-white/30 hover:border-white/20 hover:text-white/50 bg-black/20'
            } disabled:cursor-default`}
          >
            {styles.icon} {active ? styles.label + ' ✓' : styles.label}
          </button>
        );
      })}
    </div>
  </motion.div>
  );
};


const PipelineView = ({ onSync, preloadedResult }: { onSync: (t: string) => void; preloadedResult?: AnalyzeJDResponse | null }) => {
  const [jdText, setJdText] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(-1);
  const [result, setResult] = useState<AnalyzeJDResponse | null>(preloadedResult ?? null);
  const [error, setError] = useState('');
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const candidates: Candidate[] = result
    ? result.candidates.map((c, i) => mapApiCandidate(c, i))
    : [];
  const rawCandidates = result?.candidates ?? [];

  const runPipeline = async () => {
    if (!jdText.trim()) { setError('Please enter a job description.'); return; }
    setError(''); setLoading(true); setResult(null); setStep(0);
    try {
      for (let i = 0; i < PIPELINE_STEPS.length; i++) {
        setStep(i);
        await new Promise(r => setTimeout(r, 400));
      }
      const data = await analyzeJD(jdText);
      setResult(data);
      setStep(PIPELINE_STEPS.length);
      onSync(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Pipeline failed. Is the backend running?');
      setStep(-1);
    } finally { setLoading(false); }
  };

  const handleResume = async () => {
    if (!resumeFile) return;
    setError(''); setLoading(true);
    try {
      const data = await uploadResume(resumeFile, jdText);
      const fakeResult: AnalyzeJDResponse = {
        analysis_id: -1,
        parsed_jd: data.parsed_jd,
        bias_report: { flags: [], overall_risk: 'low' },
        candidates: [data.candidate],
      };
      setResult(fakeResult);
      onSync(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Resume upload failed.');
    } finally { setLoading(false); }
  };

  const biasFlags = result?.bias_report?.flags ?? [];
  const parsedJD = result?.parsed_jd;

  return (
    <div className="space-y-12 pb-16">
      {/* JD Input */}
      <section className="bg-surface-card border border-border-subtle rounded-sm p-10 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary-main/5 blur-[80px] rounded-full -mr-32 -mt-32 pointer-events-none"></div>
        <div className="flex justify-between items-center mb-6 relative z-10">
          <label className="text-[10px] font-bold text-text-secondary uppercase tracking-[0.3em] opacity-40">Protocol: Job Specification</label>
          <button onClick={() => setJdText('We are looking for a Senior Fullstack Engineer with 5+ years experience in React, Node.js, and AWS. The ideal candidate is a collaborative engineering professional who can lead technical decisions and mentor junior developers.')}
            className="text-[10px] font-bold uppercase tracking-widest text-primary-main hover:opacity-70 transition-all italic">Load Template</button>
        </div>
        <textarea value={jdText} onChange={e => setJdText(e.target.value)}
          className="w-full bg-black/40 border border-white/10 rounded-sm p-6 text-base font-light text-white/70 focus:outline-none focus:border-primary-main/50 min-h-[160px] resize-none transition-all placeholder:text-white/20"
          placeholder="Input the requisition details here..." />
        {/* Resume upload */}
        <div className="flex items-center gap-4 mt-4">
          <button onClick={() => fileRef.current?.click()}
            className="flex items-center gap-2 px-4 py-2.5 border border-white/10 rounded-sm text-[10px] font-bold uppercase tracking-widest text-text-secondary hover:text-primary-main hover:border-primary-main/30 transition-all italic">
            <Upload className="w-3.5 h-3.5" /> {resumeFile ? resumeFile.name : 'Upload Resume PDF'}
          </button>
          <input ref={fileRef} type="file" accept=".pdf" className="hidden"
            onChange={e => setResumeFile(e.target.files?.[0] ?? null)} />
          {resumeFile && (
            <button onClick={handleResume} disabled={loading}
              className="px-4 py-2.5 bg-white/5 border border-white/10 rounded-sm text-[10px] font-bold uppercase tracking-widest text-primary-main hover:brightness-110 transition-all italic disabled:opacity-40">
              Score Resume
            </button>
          )}
        </div>
        {error && <p className="mt-4 text-xs text-error font-mono">{error}</p>}
        <div className="flex justify-end mt-8 relative z-10">
          <button onClick={runPipeline} disabled={loading}
            className="bg-primary-main text-black px-12 py-5 rounded-sm font-bold text-[11px] uppercase tracking-[0.2em] hover:brightness-110 active:scale-95 transition-all italic shadow-2xl shadow-primary-main/10 disabled:opacity-60 flex items-center gap-3">
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {loading ? 'Executing...' : 'Execute Pipeline →'}
          </button>
        </div>
      </section>

      {/* Pipeline Steps */}
      <div className="flex items-center justify-between px-16 relative">
        <div className="absolute left-16 right-16 top-1 h-[1px] bg-white/5 -z-0"></div>
        {PIPELINE_STEPS.map((label, i) => (
          <div key={i} className="relative z-10 flex flex-col items-center gap-3 bg-surface-bg px-4">
            <div className={`w-2.5 h-2.5 rounded-full ring-4 ring-surface-bg transition-colors ${
              step > i ? 'bg-primary-main shadow-[0_0_8px_#D4AF37]' :
              step === i ? 'bg-white/40 animate-pulse' : 'bg-white/10'}`}></div>
            <span className={`text-[9px] font-bold uppercase tracking-[0.2em] font-mono ${
              step > i ? 'text-primary-main' : step === i ? 'text-white' : 'text-white/20'}`}>{label}</span>
          </div>
        ))}
      </div>

      {/* Bias Alerts */}
      {biasFlags.length > 0 && biasFlags.map((flag, i) => (
        <div key={i} className="bg-[#14161B] border border-primary-main/10 rounded-sm p-8 flex gap-6 relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-r from-primary-main/5 to-transparent pointer-events-none"></div>
          <div className="w-12 h-12 bg-primary-main/10 rounded-full flex items-center justify-center shrink-0 border border-primary-main/20 group-hover:scale-110 transition-transform duration-500">
            <AlertTriangle className="text-primary-main w-6 h-6" />
          </div>
          <div>
            <h4 className="text-[11px] font-bold text-primary-main uppercase tracking-[0.3em] mb-2">Integrity Alert: {flag.reason}</h4>
            <p className="text-sm font-light text-white/50 leading-relaxed max-w-2xl">
              The phrase "<span className="text-primary-main/80">{flag.phrase}</span>" may impact candidate diversity.
              <span className="block mt-2 italic font-serif text-primary-main/80">Recommended: "{flag.suggestion}"</span>
            </p>
          </div>
        </div>
      ))}

      {/* Results */}
      {result && (
        <>
          <div className="flex items-center justify-between bg-surface-card border border-border-subtle rounded-sm px-8 py-6">
            <div className="flex items-center gap-8">
              <h3 className="text-3xl font-serif italic text-white tracking-tight">{parsedJD?.role ?? 'Role'}</h3>
              <div className="flex gap-4">
                <span className="px-3 py-1 bg-white/5 border border-white/10 text-[9px] font-bold text-white/40 uppercase tracking-[0.3em] rounded-sm">{parsedJD?.seniority}</span>
                <span className="px-3 py-1 bg-white/5 border border-white/10 text-[9px] font-bold text-white/40 uppercase tracking-[0.3em] rounded-sm">{parsedJD?.domain}</span>
              </div>
              <div className="h-6 w-px bg-white/5"></div>
              <div className="flex gap-4">
                {(parsedJD?.required_skills ?? []).slice(0, 3).map(tag => (
                  <span key={tag} className="text-[10px] font-mono italic text-primary-main/60 flex items-center gap-2">
                    <span className="w-1 h-1 bg-primary-main rounded-full opacity-40"></span>{tag}
                  </span>
                ))}
              </div>
            </div>
            {result.analysis_id > 0 && (
              <a href={exportCSVUrl(result.analysis_id)} download
                className="text-[10px] font-bold uppercase tracking-[0.3em] text-white/30 flex items-center gap-3 hover:text-primary-main transition-all group italic">
                <Download className="w-4 h-4 group-hover:-translate-y-0.5 transition-transform" /> Protocol.CSV
              </a>
            )}
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-10">
            {candidates.map((c, i) => (
              <CandidateCard
                key={c.id}
                candidate={c}
                rawCandidate={rawCandidates[i]}
                onFeedback={async (name, action) => {
                  if (result?.analysis_id) {
                    await addFeedback(result.analysis_id, name, action);
                  }
                }}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
};

const HistoryView = ({ onOpenResult }: { onOpenResult: (r: AnalyzeJDResponse) => void }) => {
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [page, setPage]       = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal]     = useState(0);
  const [deleting, setDeleting] = useState<number | null>(null);

  const loadPage = (p: number) => {
    setLoading(true);
    setError('');
    getHistory(p)
      .then(d => {
        setHistory(d.history);
        setPage(d.page);
        setTotalPages(d.pages);
        setTotal(d.total);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadPage(1); }, []);

  const open = async (id: number) => {
    try {
      const data = await getHistoryItem(id);
      onOpenResult(data);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Failed to load analysis.');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this analysis? This cannot be undone.')) return;
    setDeleting(id);
    try {
      await deleteHistoryItem(id);
      loadPage(history.length === 1 && page > 1 ? page - 1 : page);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Failed to delete.');
    } finally { setDeleting(null); }
  };

  const toRunItem = (row: HistoryRow): RunHistoryItem => ({
    id: String(row.id),
    role: row.parsed_jd?.role ?? 'Analysis',
    code: `RUN_${String(row.id).padStart(3, '0')}`,
    execution: new Date(row.created_at).toLocaleString(),
    preview: row.jd_text?.slice(0, 120) ?? '',
  });

  return (
    <div className="space-y-12 animate-in fade-in duration-1000">
      <header className="max-w-xl">
        <span className="text-[10px] font-bold text-text-secondary uppercase tracking-[0.3em] block mb-4 opacity-40">Chronicle Database</span>
        <h2 className="text-6xl font-serif italic text-white mb-6 leading-tight">Operational<br/>History</h2>
        <p className="text-lg font-light text-white/50 leading-relaxed font-serif italic">Audit of legacy intelligence pipelines and candidate scraping sessions.</p>
      </header>

      {loading && (
        <div className="flex items-center justify-center py-20 gap-3 text-text-secondary">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm font-mono italic">Loading history...</span>
        </div>
      )}
      {error && <p className="text-error text-sm font-mono">{error}</p>}

      {!loading && history.length === 0 && !error && (
        <div className="text-center py-20 text-text-secondary italic font-serif">No analysis runs yet. Execute a pipeline first.</div>
      )}

      {history.length > 0 && (
        <div className="bg-surface-card border border-border-subtle rounded-sm overflow-hidden shadow-2xl">
          <div className="grid grid-cols-[1fr_180px_280px_160px] px-10 py-6 bg-black/40 border-b border-border-subtle text-text-secondary text-[10px] font-bold uppercase tracking-[0.3em] opacity-40">
            <div>Designation</div><div>Executed</div><div>Preview Intelligence</div><div className="text-right">Actions</div>
          </div>
          {history.map((row, i) => {
            const item = toRunItem(row);
            return (
              <div key={row.id} className={`grid grid-cols-[1fr_180px_280px_160px] items-center px-10 py-8 border-b border-border-subtle hover:bg-surface-hover transition-all duration-500 group ${i === history.length - 1 ? 'border-b-0' : ''}`}>
                <div>
                  <div className="text-xl font-serif italic text-white group-hover:text-primary-main transition-colors mb-2 font-semibold">{item.role}</div>
                  <div className="text-[10px] text-primary-main/50 flex items-center gap-2 font-mono tracking-widest uppercase">
                    <Hash className="w-3 h-3 opacity-30" /> REF_{item.code}
                  </div>
                </div>
                <div className="text-white/40 text-xs font-serif italic">{item.execution}</div>
                <div className="text-white/40 text-sm font-light truncate italic pr-12 leading-relaxed opacity-60">"{item.preview}"</div>
                <div className="flex justify-end gap-2">
                  <a href={exportCSVUrl(row.id)} download
                    className="px-3 py-2 text-white/30 hover:text-white text-[10px] font-bold uppercase tracking-widest border border-transparent hover:border-white/10 rounded-sm transition-all italic">CSV</a>
                  <button onClick={() => handleDelete(row.id)} disabled={deleting === row.id}
                    className="px-3 py-2 text-error/40 hover:text-error text-[10px] font-bold uppercase tracking-widest border border-transparent hover:border-error/20 rounded-sm transition-all italic disabled:opacity-30">DEL</button>
                  <button onClick={() => open(row.id)}
                    className="px-4 py-2 bg-primary-main text-black text-[10px] font-bold uppercase tracking-widest rounded-sm hover:brightness-110 transition-all italic">OPEN</button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <footer className="flex items-center justify-between pt-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/40 italic font-serif opacity-50">
          {total} total {total === 1 ? 'entry' : 'entries'}
        </p>
        <div className="flex items-center gap-6">
          <button onClick={() => loadPage(page - 1)} disabled={page <= 1 || loading}
            className="w-12 h-12 flex items-center justify-center border border-white/5 rounded-sm hover:bg-surface-card transition-colors text-white/20 disabled:opacity-10 hover:text-primary-main">
            <ChevronLeft className="w-5 h-5" />
          </button>
          <div className="text-[10px] font-bold uppercase tracking-[0.3em] text-white">
            {String(page).padStart(2,'0')} / {String(totalPages).padStart(2,'0')}
          </div>
          <button onClick={() => loadPage(page + 1)} disabled={page >= totalPages || loading}
            className="w-12 h-12 flex items-center justify-center border border-white/5 rounded-sm hover:bg-surface-card transition-colors text-white/30 hover:text-primary-main disabled:opacity-10">
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </footer>
    </div>
  );
};

// ── Error Boundary ────────────────────────────────────────────────────────────
import React from 'react';
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary] Caught:', error, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-surface-bg flex items-center justify-center">
          <div className="text-center space-y-6 max-w-md px-8">
            <div className="w-16 h-16 bg-error/10 border border-error/20 rounded-sm flex items-center justify-center mx-auto">
              <AlertTriangle className="text-error w-8 h-8" />
            </div>
            <h1 className="text-3xl font-serif italic text-white">Something went wrong</h1>
            <p className="text-text-secondary text-sm font-mono leading-relaxed">{this.state.error?.message}</p>
            <button onClick={() => this.setState({ hasError: false, error: null })}
              className="px-8 py-4 bg-primary-main text-black font-bold text-xs uppercase tracking-widest rounded-sm hover:brightness-110 transition-all italic">
              Reload Interface
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Settings View ─────────────────────────────────────────────────────────────
const SettingsView = () => {
  const apiKeySet = !!(import.meta as any).env?.VITE_API_KEY;

  return (
    <div className="space-y-12 animate-in fade-in duration-1000">
      <header className="max-w-xl">
        <span className="text-[10px] font-bold text-text-secondary uppercase tracking-[0.3em] block mb-4 opacity-40">Configuration</span>
        <h2 className="text-6xl font-serif italic text-white mb-6 leading-tight">System<br/>Settings</h2>
        <p className="text-lg font-light text-white/50 leading-relaxed font-serif italic">Runtime configuration for the intelligence pipeline.</p>
      </header>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        {/* API Status */}
        <div className="bg-surface-card border border-border-subtle rounded-sm p-8 space-y-6">
          <label className="text-[10px] font-bold text-text-secondary uppercase tracking-[0.3em] opacity-40 block">Connectivity</label>
          <div className="space-y-4">
            <div className="flex items-center justify-between py-4 border-b border-border-subtle">
              <div>
                <p className="text-sm font-semibold text-white font-serif italic">Backend API</p>
                <p className="text-[10px] text-text-secondary mt-0.5">http://localhost:8000</p>
              </div>
              <span className="flex items-center gap-2 text-[10px] font-bold text-primary-main uppercase tracking-widest">
                <span className="w-1.5 h-1.5 rounded-full bg-primary-main shadow-[0_0_6px_#D4AF37]"></span> Operational
              </span>
            </div>
            <div className="flex items-center justify-between py-4 border-b border-border-subtle">
              <div>
                <p className="text-sm font-semibold text-white font-serif italic">API Key Auth</p>
                <p className="text-[10px] text-text-secondary mt-0.5">Set VITE_API_KEY in frontend/.env</p>
              </div>
              <span className={`text-[10px] font-bold uppercase tracking-widest ${
                apiKeySet ? 'text-primary-main' : 'text-white/30'
              }`}>{apiKeySet ? 'Enabled' : 'Dev Mode'}</span>
            </div>
            <div className="flex items-center justify-between py-4">
              <div>
                <p className="text-sm font-semibold text-white font-serif italic">LLM Model</p>
                <p className="text-[10px] text-text-secondary mt-0.5">Google Gemini 2.0 Flash</p>
              </div>
              <span className="text-[10px] font-bold text-primary-main uppercase tracking-widest">Active</span>
            </div>
          </div>
        </div>

        {/* Ranking Weights */}
        <div className="bg-surface-card border border-border-subtle rounded-sm p-8 space-y-6">
          <label className="text-[10px] font-bold text-text-secondary uppercase tracking-[0.3em] opacity-40 block">Ranking Formula</label>
          <div className="space-y-6">
            <div>
              <div className="flex justify-between mb-3">
                <span className="text-sm font-serif italic text-white">Match Score</span>
                <span className="text-primary-main font-bold text-sm font-mono">60%</span>
              </div>
              <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div className="h-full bg-primary-main rounded-full" style={{ width: '60%' }}></div>
              </div>
              <p className="text-[10px] text-text-secondary mt-2 opacity-60">Skill overlap, experience, domain fit</p>
            </div>
            <div>
              <div className="flex justify-between mb-3">
                <span className="text-sm font-serif italic text-white">Interest Score</span>
                <span className="text-primary-main font-bold text-sm font-mono">40%</span>
              </div>
              <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div className="h-full bg-primary-main/60 rounded-full" style={{ width: '40%' }}></div>
              </div>
              <p className="text-[10px] text-text-secondary mt-2 opacity-60">Enthusiasm, clarity, engagement in simulation</p>
            </div>
            <p className="text-[10px] text-text-secondary italic font-serif opacity-40 border-t border-border-subtle pt-4">
              Customizable weight tuning coming in v3.0
            </p>
          </div>
        </div>

        {/* Pipeline Info */}
        <div className="bg-surface-card border border-border-subtle rounded-sm p-8 space-y-6">
          <label className="text-[10px] font-bold text-text-secondary uppercase tracking-[0.3em] opacity-40 block">Pipeline Configuration</label>
          <div className="space-y-4 text-sm">
            {[['Candidate Pool', '20 profiles (static JSON)'],
              ['Concurrency', 'Async — all candidates scored in parallel'],
              ['JD Max Length', '8,000 characters'],
              ['PDF Max Size', '5 MB'],
              ['Rate Limit', '10 analyses / minute / IP'],
              ['Request Timeout', '90 seconds hard cap'],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between items-center py-3 border-b border-border-subtle last:border-0">
                <span className="text-text-secondary font-mono text-[10px] uppercase tracking-widest">{k}</span>
                <span className="text-white font-serif italic text-xs">{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Version */}
        <div className="bg-surface-card border border-border-subtle rounded-sm p-8 space-y-6">
          <label className="text-[10px] font-bold text-text-secondary uppercase tracking-[0.3em] opacity-40 block">System Info</label>
          <div className="space-y-4">
            {[['HireKaro Frontend', 'v2.2.0'],
              ['HireKaro API', 'v2.2.0'],
              ['React', '19'],
              ['FastAPI', '0.110'],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between items-center py-3 border-b border-border-subtle last:border-0">
                <span className="text-text-secondary text-xs font-mono">{k}</span>
                <span className="text-primary-main font-bold text-xs font-mono">{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const LoginView = ({ onLogin }: { onLogin: (user: {email: string; role: string}) => void }) => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (isRegister) {
        const res = await registerUser(email, password);
        onLogin(res.user);
      } else {
        const res = await loginUser(email, password);
        onLogin(res.user);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-bg flex flex-col items-center justify-center relative overflow-hidden animate-in fade-in duration-1000">
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary-main/10 blur-[120px] rounded-full pointer-events-none"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-primary-main/5 blur-[100px] rounded-full pointer-events-none"></div>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }} className="w-full max-w-md bg-surface-card border border-border-subtle p-10 rounded-sm relative z-10 shadow-2xl shadow-black/50">
        <div className="flex flex-col items-center mb-10">
          <div className="w-12 h-12 bg-primary-main/10 border border-primary-main/20 flex items-center justify-center rounded-sm mb-4">
            <Rocket className="text-primary-main w-6 h-6" />
          </div>
          <h1 className="text-3xl font-serif italic font-bold text-white tracking-wider leading-none">HireKaro</h1>
          <p className="text-[9px] text-primary-main/60 uppercase tracking-[0.3em] mt-2 font-semibold">Intelligence Guild</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="text-[10px] font-bold text-text-secondary uppercase tracking-[0.2em] mb-2 block opacity-70">Operative Email</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required
              className="w-full bg-black/40 border border-white/10 rounded-sm px-4 py-3 text-sm font-light text-white focus:outline-none focus:border-primary-main/50 transition-all placeholder:text-white/20"
              placeholder="recruiter@hirekaro.ai" />
          </div>
          <div>
            <label className="text-[10px] font-bold text-text-secondary uppercase tracking-[0.2em] mb-2 block opacity-70">Passcode</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8}
              className="w-full bg-black/40 border border-white/10 rounded-sm px-4 py-3 text-sm font-light text-white focus:outline-none focus:border-primary-main/50 transition-all"
              placeholder="••••••••" />
          </div>

          {error && <p className="text-error text-xs font-mono">{error}</p>}

          <button type="submit" disabled={loading}
            className="w-full bg-primary-main text-black py-4 rounded-sm font-bold text-[11px] uppercase tracking-[0.2em] hover:brightness-110 active:scale-95 transition-all italic shadow-[0_0_15px_rgba(212,175,55,0.15)] disabled:opacity-60 flex items-center justify-center gap-3 mt-4">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : (isRegister ? 'Request Clearance' : 'Authenticate')}
          </button>
        </form>

        <div className="mt-8 text-center border-t border-border-subtle pt-6">
          <p className="text-xs text-text-secondary">
            {isRegister ? "Already an operative?" : "Need security clearance?"}{' '}
            <button type="button" onClick={() => setIsRegister(!isRegister)} className="text-primary-main hover:text-white transition-colors italic font-serif ml-1">
              {isRegister ? "Log In" : "Register"}
            </button>
          </p>
        </div>
      </motion.div>
    </div>
  );
};

export default function App() {
  const [currentView, setCurrentView] = useState<View>('pipeline');
  const [lastSync, setLastSync] = useState('');
  const [preloadedResult, setPreloadedResult] = useState<AnalyzeJDResponse | null>(null);
  
  const [user, setUser] = useState<{email: string; role: string} | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (token) {
      setUser({ email: 'operative@hirekaro.ai', role: 'recruiter' }); // Mocked until we fetch /auth/me
    }
    setCheckingAuth(false);
  }, []);

  const handleLogout = () => {
    logoutUser();
    setUser(null);
  };

  const handleOpenResult = (r: AnalyzeJDResponse) => {
    setPreloadedResult(r);
    setCurrentView('pipeline');
    setLastSync(new Date().toLocaleTimeString());
  };

  if (checkingAuth) {
    return <div className="min-h-screen bg-surface-bg flex items-center justify-center text-primary-main"><Loader2 className="w-6 h-6 animate-spin" /></div>;
  }

  if (!user) {
    return <LoginView onLogin={setUser} />;
  }

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-surface-bg text-text-primary">
        <Sidebar activeView={currentView} onViewChange={setCurrentView} user={user} onLogout={handleLogout} />
        <main className="ml-[220px] transition-all duration-300">
          <Header lastSync={lastSync} />
          <div className="max-w-6xl mx-auto p-8">
            <AnimatePresence mode="wait">
              <motion.div key={currentView}
                initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }} transition={{ duration: 0.3, ease: 'easeOut' }}>
                {currentView === 'pipeline' && (
                  <PipelineView
                    onSync={setLastSync}
                    key={preloadedResult?.analysis_id ?? 'pipeline'}
                    preloadedResult={preloadedResult}
                  />
                )}
                {currentView === 'history'  && <HistoryView onOpenResult={handleOpenResult} />}
                {currentView === 'settings' && <SettingsView />}
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </div>
    </ErrorBoundary>
  );
}
