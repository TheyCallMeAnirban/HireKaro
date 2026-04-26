/**
 * api.ts — Typed client for the HireKaro FastAPI backend.
 * All calls use /api prefix, which Vite proxies to http://localhost:8000.
 * Set VITE_API_KEY in frontend/.env to enable API key auth.
 */

import type {
  AnalyzeJDResponse,
  HistoryResponse,
  UploadResumeResponse,
} from './types';

const BASE    = '/api';
const API_KEY = (import.meta as any).env?.VITE_API_KEY as string | undefined;

// Auth token stored in localStorage
export const getToken   = (): string | null => localStorage.getItem('hk_token');
export const setToken   = (t: string)       => localStorage.setItem('hk_token', t);
export const clearToken = ()                => localStorage.removeItem('hk_token');

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getToken();
  return {
    ...(token   ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(API_KEY && !token ? { 'X-API-Key': API_KEY } : {}),
    ...extra,
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ── 1. Analyze a Job Description ─────────────────────────────────────────────
export async function analyzeJD(jd_text: string): Promise<AnalyzeJDResponse> {
  const res = await fetch(`${BASE}/analyze-jd`, {
    method:  'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body:    JSON.stringify({ jd_text }),
  });
  return handleResponse<AnalyzeJDResponse>(res);
}

// ── 2. Upload a PDF Resume ────────────────────────────────────────────────────
export async function uploadResume(file: File, jd_text = ''): Promise<UploadResumeResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('jd_text', jd_text);
  const res = await fetch(`${BASE}/upload-resume`, {
    method:  'POST',
    headers: authHeaders(),
    body:    form,
  });
  return handleResponse<UploadResumeResponse>(res);
}

// ── 3. List Analysis History (paginated) ─────────────────────────────────────
export async function getHistory(page = 1, limit = 20): Promise<HistoryResponse> {
  const res = await fetch(`${BASE}/history?page=${page}&limit=${limit}`, {
    headers: authHeaders(),
  });
  return handleResponse<HistoryResponse>(res);
}

// ── 4. Get a Single History Item ──────────────────────────────────────────────
export async function getHistoryItem(id: number): Promise<AnalyzeJDResponse> {
  const res = await fetch(`${BASE}/history/${id}`, { headers: authHeaders() });
  return handleResponse<AnalyzeJDResponse>(res);
}

// ── 5. Delete a History Item ──────────────────────────────────────────────────
export async function deleteHistoryItem(id: number): Promise<void> {
  const res = await fetch(`${BASE}/history/${id}`, {
    method:  'DELETE',
    headers: authHeaders(),
  });
  await handleResponse<unknown>(res);
}

// ── 6. CSV Export URL (direct link, triggers browser download) ────────────────
export function exportCSVUrl(analysis_id: number): string {
  const keyParam = API_KEY ? `?key=${encodeURIComponent(API_KEY)}` : '';
  return `${BASE}/export-csv/${analysis_id}${keyParam}`;
}

// ── 7. Auth ───────────────────────────────────────────────────────────────────
export interface AuthResponse {
  access_token: string;
  token_type:   string;
  user: { id: string; email: string; role: string };
}

export async function registerUser(email: string, password: string): Promise<AuthResponse> {
  const res  = await fetch(`${BASE}/auth/register`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ email, password }),
  });
  const data = await handleResponse<AuthResponse>(res);
  setToken(data.access_token);
  return data;
}

export async function loginUser(email: string, password: string): Promise<AuthResponse> {
  const res  = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ email, password }),
  });
  const data = await handleResponse<AuthResponse>(res);
  setToken(data.access_token);
  return data;
}

export function logoutUser(): void { clearToken(); }

// ── 8. Feedback ───────────────────────────────────────────────────────────────
export async function addFeedback(
  analysis_id:    number,
  candidate_name: string,
  action:         'shortlist' | 'reject' | 'hire',
): Promise<void> {
  const res = await fetch(`${BASE}/feedback`, {
    method:  'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body:    JSON.stringify({ analysis_id, candidate_name, action }),
  });
  await handleResponse<unknown>(res);
}
