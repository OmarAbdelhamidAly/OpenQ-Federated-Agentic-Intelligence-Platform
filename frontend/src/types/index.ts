// ─── Authentication & User ──────────────────────────────────────────────────

export interface BrandingConfig {
  primary_color?: string;
  secondary_color?: string;
  logo_url?: string;
  system_persona?: string;
}

export interface AuthUser {
  id: string;
  email?: string;
  role: string;
  tenant_id: string;
  group_id?: string;
  branding_config?: BrandingConfig;
}

export type User = AuthUser;


// ─── Routing & Navigation ──────────────────────────────────────────────────

export type ViewKey =
  | 'about'
  | 'dashboard'
  | 'csv'
  | 'sql'
  | 'pdf'
  | 'json'
  | 'codebase'
  | 'sentinel'
  | 'team'
  | 'nexus'
  | 'image'
  | 'audio'
  | 'video'
  | 'about';

export type PortalType = Extract<ViewKey, 'csv' | 'sql' | 'pdf' | 'json' | 'codebase' | 'image' | 'audio' | 'video'>;

export const PORTAL_TYPES: PortalType[] = ['csv', 'sql', 'pdf', 'json', 'codebase', 'image', 'audio', 'video'];

// ─── Data Sources ───────────────────────────────────────────────────────────

export interface DataSource {
  id: string;
  name: string;
  type: string;
  status: string;
  created_at: string;
  schema_json?: any;
  auto_analysis_json?: any;
  indexing_status: 'pending' | 'running' | 'done' | 'failed';
  auto_analysis_status: 'pending' | 'running' | 'done' | 'failed';
}

// ─── Analysis & Jobs ────────────────────────────────────────────────────────

export interface AnalysisJob {
  id: string;
  status: 'pending' | 'running' | 'done' | 'error' | 'awaiting_approval';
  question: string;
  source_id: string;
  source_type?: string;
  created_at: string;
  completed_at: string;
  generated_sql?: string;
  error_message?: string;
  thinking_steps: Array<{ node: string; status: string; timestamp: string }>;
  chart_json?: Record<string, any>;
  insight_report?: string;
  synthesis_report?: string;
  executive_summary?: string;
  multi_source_ids?: string[];
  required_pillars?: string[];
  complexity_index?: number;
  total_pills?: number;
  recommendations_json?: any[] | string | any;
  follow_up_suggestions?: string[];
  visual_context?: Array<{ page_number: number; image_base64: string }>;
  structured_data?: any;
}

// ─── Chat Interface ─────────────────────────────────────────────────────────

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content?: string;
  isStreaming?: boolean;
  job?: AnalysisJob;
}
