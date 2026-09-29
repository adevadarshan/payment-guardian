// api/analyze.ts + scans.ts entry points (Slice 1).
import { apiGet, apiPost } from './client';
import type {
  AnalysisResult,
  AnalyzeRequest,
  AuditEntry,
  Category,
  ChainVerify,
  GenericAnalyzeRequest,
  ScanSummary,
  Stats,
} from './types';

export const analyzePayment = (payment: AnalyzeRequest['payment']) =>
  apiPost<AnalysisResult>('/analyze', { analysis_type: 'payment', payment });

export const analyze = (body: GenericAnalyzeRequest) =>
  apiPost<AnalysisResult>('/analyze', body);

export const fetchCategories = () => apiGet<Category[]>('/categories');
export const fetchScans = (limit = 50, level?: string, type?: string) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (level) params.set('level', level);
  if (type) params.set('type', type);
  return apiGet<ScanSummary[]>(`/scans?${params.toString()}`);
};
export const fetchStats = () => apiGet<Stats>('/stats');
export const fetchScan = (id: string) => apiGet<AnalysisResult>(`/scans/${id}`);
export const fetchHealth = () =>
  apiGet<{ status: string; db: string; model_backend: string; pipeline_version: string }>('/health');
export const fetchAudit = (limit = 200) => apiGet<AuditEntry[]>(`/audit?limit=${limit}`);
export const verifyChain = () => apiPost<ChainVerify>('/audit/verify', {});
