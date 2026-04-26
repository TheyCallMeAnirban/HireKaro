// ── UI view names ──────────────────────────────────────────────────────────────
export type View = 'pipeline' | 'history' | 'settings';

// ── Frontend display types ─────────────────────────────────────────────────────
export interface Candidate {
  id: string;
  rank: string;
  name: string;
  role: string;
  experience: string;
  scores: {
    final: number;
    match: number;
    interest: number;
  };
  skills: { name: string; type: 'success' | 'warning' | 'error' | 'neutral' }[];
  quote: string;
  brief: string;
  strengths: string[];
  gaps: string[];
}

export interface RunHistoryItem {
  id: string;
  role: string;
  code: string;
  execution: string;
  preview: string;
}

// ── Backend raw API response types ─────────────────────────────────────────────

export interface ApiMatchResult {
  score: number;
  matched_skills: string[];
  missing_skills: string[];
  secondary_matched: string[];
}

export interface ApiInterestResult {
  score: number;
  signal: string;
  flags: string[];
}

export interface ApiFitSummary {
  summary: string;
  recommendation: string;
  key_strength: string;
  key_gap: string;
}

export interface ApiCandidate {
  name: string;
  current_role: string;
  years_experience: number;
  project: string;
  skills: string[];
  match: ApiMatchResult;
  conversation: { role: string; text: string }[];   // backend returns "text", not "content"
  interest: ApiInterestResult;
  fit_summary: ApiFitSummary;
  final_score?: number;
}

export interface ParsedJD {
  role: string;
  seniority: string;
  domain: string;
  required_skills: string[];
  secondary_skills: string[];
}

export interface BiasFlag {
  phrase: string;
  reason: string;
  suggestion: string;
}

export interface BiasReport {
  flags: BiasFlag[];
  overall_risk: string;
}

export interface AnalyzeJDResponse {
  analysis_id: number;
  parsed_jd: ParsedJD;
  bias_report: BiasReport;
  candidates: ApiCandidate[];
}

export interface HistoryRow {
  id: number;
  jd_text: string;
  parsed_jd: ParsedJD;
  created_at: string;
}

export interface HistoryResponse {
  history: HistoryRow[];
  total:   number;
  page:    number;
  pages:   number;
  limit:   number;
}

export interface UploadResumeResponse {
  parsed_jd: ParsedJD;
  candidate: ApiCandidate;
}

// ── Mapper: ApiCandidate → Candidate (UI type) ─────────────────────────────────
export function mapApiCandidate(c: ApiCandidate, index: number): Candidate {
  const matchScore = Math.round(c.match.score);
  const interestScore = Math.round(c.interest.score);
  const finalScore =
    c.final_score !== undefined
      ? Math.round(c.final_score)
      : Math.round(0.6 * matchScore + 0.4 * interestScore);

  const skills: Candidate['skills'] = [
    ...c.match.matched_skills.map((s) => ({ name: s, type: 'success' as const })),
    ...(c.match.secondary_matched ?? []).map((s) => ({ name: s, type: 'warning' as const })),
    ...c.match.missing_skills.map((s) => ({ name: s, type: 'error' as const })),
  ];

  return {
    id: String(index + 1),
    rank: `#${String(index + 1).padStart(2, '0')}`,
    name: c.name,
    role: c.current_role,
    experience: `${c.years_experience} Yr${c.years_experience !== 1 ? 's' : ''} Exp.`,
    scores: { final: finalScore, match: matchScore, interest: interestScore },
    skills,
    quote: c.fit_summary?.recommendation ?? c.project ?? '',
    brief: c.fit_summary?.summary ?? '',
    strengths: c.fit_summary?.key_strength ? [c.fit_summary.key_strength] : [],
    gaps: c.fit_summary?.key_gap ? [c.fit_summary.key_gap] : [],
  };
}
