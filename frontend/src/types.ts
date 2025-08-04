export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface Chat {
  id: number;
  user_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface Message {
  id: number;
  chat_id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginData {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
}

export enum PageType {
  prd = "prd",
  research = "research",
  analytics = "analytics",
}

export enum RetrieverType {
  NAIVE = "naive",
  CONTEXTUAL_COMPRESSION = "contextual_compression",
}

export interface NotionSettings {
  id: number;
  user_id: number;
  notion_token: string | null;
  prd_database_id: string | null;
  research_database_id: string | null;
  analytics_database_id: string | null;
  import_prd: boolean;
  import_research: boolean;
  import_analytics: boolean;
  retriever_type: RetrieverType;
  created_at: string;
  updated_at: string;
}

export interface NotionSettingsUpdate {
  notion_token?: string;
  prd_database_id?: string;
  research_database_id?: string;
  analytics_database_id?: string;
  import_prd?: boolean;
  import_research?: boolean;
  import_analytics?: boolean;
  retriever_type?: RetrieverType;
}

export interface NotionPage {
  id: number;
  notion_page_id: string;
  user_id: number;
  title: string;
  content: string | null;
  page_type: PageType;
  notion_url: string | null;
  parent_page_id: string | null;
  last_edited_time: string | null;
  created_at: string;
  updated_at: string;
}

export interface NotionChunk {
  id: number;
  page_id: number;
  chunk_index: number;
  content: string;
  token_count: number | null;
  created_at: string;
}

export interface NotionComment {
  id: number;
  page_id: number;
  notion_comment_id: string;
  content: string;
  author: string | null;
  created_time: string | null;
  created_at: string;
}

export interface NotionPageWithDetails extends NotionPage {
  chunks: NotionChunk[];
  comments: NotionComment[];
}

export interface ImportStatusResponse {
  has_data: boolean;
  total_pages: number;
  by_type: {
    [key: string]: any;
  };
  last_import: string | null;
}

export interface KnowledgeBaseStats {
  total_pages: number;
  by_type: { [key: string]: number };
  total_chunks: number;
  total_comments: number;
}

export interface PageSearchResponse {
  pages: NotionPage[];
  total_found: number;
}

export interface TestConnectionResponse {
  connected: boolean;
  message: string;
}

// PRD Review specific types
export interface LocalPRD {
  id: string;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
  is_local: true;
}

export interface PRDDocument {
  id: string;
  title: string;
  content?: string;
  created_at: string;
  updated_at: string;
  is_local: boolean;
  notion_url?: string | null;
  file_type?: 'markdown' | 'pdf' | 'text';
}

export interface PRDAnalysis {
  overview: string;
  key_features: string[];
  user_personas: string[];
  success_metrics: string[];
  risks: string[];
  recommendations: string[];
} 