import axios from 'axios';
import { 
  Chat, 
  Message, 
  NotionSettings, 
  NotionSettingsUpdate, 
  NotionPage, 
  NotionPageWithDetails,
  ImportStatusResponse,
  KnowledgeBaseStats,
  PageSearchResponse,
  TestConnectionResponse,
  PageType
} from '../types';

export const api = axios.create({
  baseURL: 'http://localhost:8000',
});

// Chat API functions
export const chatAPI = {
  getChats: () => api.get<Chat[]>('/chats'),
  
  createChat: (title: string) => 
    api.post<Chat>('/chats', { title }),
  
  getChatMessages: (chatId: number) => 
    api.get<Message[]>(`/chats/${chatId}/messages`),
  
  sendMessage: (chatId: number, content: string) => 
    api.post<{ message: string }>(`/chats/${chatId}/messages`, {
      content,
      role: 'user'
    }),
  
  generateChatTitle: (chatId: number) =>
    api.post<{ title: string }>(`/chats/${chatId}/generate-title`),
  
  getChatContext: (chatId: number) =>
    api.get<{ chat_id: number; title: string; context: any }>(`/chats/${chatId}/context`),
  
  healthCheck: () =>
    api.get<{ status: string; services: any; version: string }>('/health'),
};

// Notion API functions
export const notionAPI = {
  getSettings: () => 
    api.get<NotionSettings>('/notion/settings'),
    
  updateSettings: (settings: NotionSettingsUpdate) =>
    api.post<NotionSettings>('/notion/settings', settings),

  testConnection: (settings: NotionSettingsUpdate) =>
    api.post<TestConnectionResponse>('/notion/test-connection', settings),
    
  uploadFile: (file: File, pageType: PageType, onUploadProgress: (progressEvent: any) => void) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('page_type', pageType);

    return api.post('/notion/upload-file', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress,
    });
  },

  startImport: (forceUpdate: boolean) =>
    api.post(`/notion/import?force_update=${forceUpdate}`, {}, { 
      responseType: 'stream' 
    }),

  getImportStatus: () =>
    api.get<ImportStatusResponse>('/notion/import-status'),

  getPages: (pageType?: PageType, limit: number = 100, offset: number = 0) =>
    api.get<NotionPage[]>('/notion/pages', { 
      params: { page_type: pageType, limit, offset } 
    }),

  getPageDetails: (pageId: number) =>
    api.get<NotionPageWithDetails>(`/notion/pages/${pageId}`),
    
  searchPages: (searchTerm: string, pageType?: PageType, limit: number = 50) =>
    api.post<PageSearchResponse>('/notion/pages/search', {
      search_term: searchTerm,
      page_type: pageType,
      limit,
    }),
    
  getStats: () =>
    api.get<KnowledgeBaseStats>('/notion/stats'),
    
  deleteData: () =>
    api.delete('/notion/data'),
};

// PRD API functions for database operations
export interface PRDCreate {
  title: string;
  content?: string;
}

export interface PRDUpdate {
  title?: string;
  content?: string;
}

export interface PRDResponse {
  id: number;
  user_id: number;
  title: string;
  content: string | null;
  created_at: string;
  updated_at: string;
}

export const prdAPI = {
  // Create a new PRD
  createPRD: (prd: PRDCreate) =>
    api.post<PRDResponse>('/prds/', prd),
  
  // Get all PRDs for the current user
  getPRDs: (skip: number = 0, limit: number = 100) =>
    api.get<PRDResponse[]>('/prds/', { params: { skip, limit } }),
  
  // Get a specific PRD by ID
  getPRD: (prdId: number) =>
    api.get<PRDResponse>(`/prds/${prdId}`),
  
  // Update a PRD
  updatePRD: (prdId: number, prdUpdate: PRDUpdate) =>
    api.put<PRDResponse>(`/prds/${prdId}`, prdUpdate),
  
  // Delete a PRD
  deletePRD: (prdId: number) =>
    api.delete(`/prds/${prdId}`),
};

// PRD Analysis API functions
export interface AnalysisSection {
  section_name: string;
  analysis: string;
  recommendations: string[];
  score: number;
  sources?: string[];
}

export interface AnalysisEvent {
  type: 'section' | 'final_report' | 'log' | 'status' | 'error';
  section_name?: string;
  analysis?: string;
  recommendations?: string[];
  score?: number;
  content?: string;
  message?: string;
}

export const prdAnalysisAPI = {
  analyzePRD: (prdId: string, onEvent: (event: AnalysisEvent) => void, onError: (error: string) => void) => {
    const token = localStorage.getItem('token');
    if (!token) {
      onError('No authentication token found');
      return null;
    }

    const url = `http://localhost:8000/prd-analysis/analyze/${prdId}?token=${encodeURIComponent(token)}`;
    console.log('Connecting to EventSource:', url);
    
    const eventSource = new EventSource(url);
    
    eventSource.onopen = () => {
      console.log('EventSource connection opened');
    };
    
    eventSource.onmessage = (event) => {
      console.log('EventSource message received:', event.data);
      try {
        const data: AnalysisEvent = JSON.parse(event.data);
        onEvent(data);
      } catch (error) {
        console.error('Failed to parse EventSource data:', error, event.data);
        onError('Failed to parse analysis response');
      }
    };
    
    eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
      console.log('EventSource readyState:', eventSource.readyState);
      
      let errorMessage = 'Connection error during analysis';
      
      // Provide more specific error information based on readyState
      switch (eventSource.readyState) {
        case EventSource.CONNECTING:
          errorMessage = 'Failed to connect to analysis service';
          break;
        case EventSource.CLOSED:
          errorMessage = 'Connection to analysis service was closed';
          break;
        default:
          errorMessage = 'Unknown connection error during analysis';
      }
      
      onError(errorMessage);
      eventSource.close();
    };
    
    return eventSource;
  },

  testAnalysis: async () => {
    const response = await api.get('/prd-analysis/test');
    return response.data;
  }
}; 

// RAGAS Evaluation API functions
export const ragasAPI = {
  startEvaluation: (data: { user_id?: number; testset_size: number }) =>
    api.post('/ragas-evaluation/start', data),
    
  getStatus: () =>
    api.get('/ragas-evaluation/status'),
    
  getResults: () =>
    api.get('/ragas-evaluation/results'),
    
  resetEvaluation: () =>
    api.delete('/ragas-evaluation/reset'),
    
  testService: () =>
    api.get('/ragas-evaluation/test')
}; 