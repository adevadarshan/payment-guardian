// api/types.ts — mirrors the backend AnalysisResult contract (Slice 1).
// The client renders risk_level; it never derives it.

export type RiskLevel = 'SAFE' | 'MEDIUM' | 'HIGH';
export type AnalysisType = 'payment' | 'message' | 'url' | 'qr';
export type SeenStatus = 'previously_seen' | 'new' | 'unable_to_verify' | 'not_applicable';

export interface PaymentInput {
  amount: number;
  currency: string;
  payee_id: string;
  payee_name: string;
  sender_balance: number;
  note?: string;
  channel: string;
  merchant_category: string;
}

export interface AnalyzeRequest {
  analysis_type: 'payment';
  payment: PaymentInput;
}

export interface MessageInput {
  text: string;
  context: 'sms' | 'whatsapp' | 'email' | 'unknown';
}

export interface UrlInput {
  url: string;
}

export interface QrInput {
  image_base64?: string;
  payload?: string;
}

export interface PaymentContext {
  amount?: number;
  sender_balance?: number;
  payee_name?: string;
}

export interface GenericAnalyzeRequest {
  analysis_type: AnalysisType;
  payment?: PaymentInput;
  message?: MessageInput;
  url?: UrlInput;
  qr?: QrInput;
  payment_context?: PaymentContext;
  timestamp?: string;
}

export interface Reason {
  code: string;
  signal: string;
  title: string;
  observation: string;
  impact: 'low' | 'medium' | 'high' | 'informational';
}

export interface Signal {
  name: string;
  source: 'rule' | 'ml' | 'advisory';
  value: number | null;
  weight: number | null;
  contribution: number | null;
}

export interface Evidence {
  extracted_urls: string[];
  matched_phrases: string[];
  qr_payload: string | null;
  decoded: boolean;
  parsed_qr: Record<string, string | number | null>;
  payload_class: string | null;
  qr_decode: string;
}

export interface SeenInfo {
  status: SeenStatus;
  first_seen_at: string | null;
  times_seen: number | null;
}

export interface RecommendedAction {
  headline: string;
  steps: string[];
}

export interface PaymentSummary {
  amount: number;
  payee_id: string;
  payee_name: string | null;
  merchant_category: string;
  channel: string;
  sender_balance: number;
}

export interface AnalysisResult {
  scan_id: string;
  analysis_type: AnalysisType;
  risk_score: number;
  risk_level: RiskLevel;
  reasons: Reason[];
  signals: Signal[];
  evidence: Evidence;
  seen: SeenInfo;
  recommended_action: RecommendedAction;
  advisory: { status: string; provider: string | null; text: string | null };
  model: { backend: string; version: string | null };
  pipeline_version: string;
  created_at: string;
  payment_summary: PaymentSummary | null;
}

export interface ScanSummary {
  scan_id: string;
  analysis_type: AnalysisType;
  risk_score: number;
  risk_level: RiskLevel;
  label: string;
  created_at: string;
}

export interface Stats {
  total: number;
  safe: number;
  medium: number;
  high: number;
  fraud_rate: number;
}

export interface Category {
  label: string;
  key: string;
  type: string;
  risk_weight: number;
}

export interface AuditEntry {
  id: number;
  event_type: string;
  entity_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
  previous_hash: string;
  entry_hash: string;
  created_at: string;
}

export interface ChainVerify {
  valid: boolean;
  entry_count?: number;
  broken_at_id?: number;
  reason?: string;
}
