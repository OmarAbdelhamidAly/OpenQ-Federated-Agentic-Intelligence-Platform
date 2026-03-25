import axios from 'axios';
import type { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';

// Create a configured axios instance
const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

const subscribeTokenRefresh = (cb: (token: string) => void) => {
  refreshSubscribers.push(cb);
};

const onRefreshed = (token: string) => {
  refreshSubscribers.map((cb) => cb(token));
  refreshSubscribers = [];
};

// Request interceptor to add JWT token
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor to handle auth errors and service-specific failures
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const { config, response } = error;
    const status = response?.status;
    
    if (status === 401 && config && !(config as any)._retry) {
      if (isRefreshing) {
        return new Promise((resolve) => {
          subscribeTokenRefresh((token: string) => {
            config.headers.Authorization = `Bearer ${token}`;
            resolve(apiClient(config));
          });
        });
      }

      (config as any)._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('auth_refresh_token');
      if (refreshToken) {
        try {
          const res = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken });
          const { access_token, refresh_token: newRefreshToken } = res.data;
          
          localStorage.setItem('auth_token', access_token);
          if (newRefreshToken) localStorage.setItem('auth_refresh_token', newRefreshToken);
          
          onRefreshed(access_token);
          isRefreshing = false;
          
          if (config.headers) {
            config.headers.Authorization = `Bearer ${access_token}`;
          }
          return apiClient(config);
        } catch (refreshError) {
          isRefreshing = false;
          localStorage.removeItem('auth_token');
          localStorage.removeItem('auth_refresh_token');
          localStorage.removeItem('auth_user');
          window.location.reload(); // Force login
          return Promise.reject(refreshError);
        }
      } else {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
      }
    } else if (status === 403) {
      console.error("[SECURITY] Forbidden access attempt:", error.config?.url);
    } else if (status && status >= 500) {
      console.warn("[SERVICE] Backend error or worker unavailability detected:", status);
    }
    
    return Promise.reject(error);
  }
);

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
  thinking_steps: Array<{node: string, status: string, timestamp: string}>;
  chart_json?: Record<string, any>;
  insight_report?: string;
  synthesis_report?: string;
  executive_summary?: string;
  multi_source_ids?: string[];
  recommendations_json?: any[];
  follow_up_suggestions?: string[];
  visual_context?: Array<{ page_number: number, image_base64: string }>;
  structured_data?: any;
}

export interface User {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
  group_id?: string;
  branding_config?: {
    primary_color?: string;
    secondary_color?: string;
    logo_url?: string;
    system_persona?: string;
  };
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

export const AuthAPI = {
  login: async (credentials: any): Promise<AuthResponse> => {
    const res = await apiClient.post('/auth/login', credentials);
    return res.data;
  },
  register: async (data: any): Promise<AuthResponse> => {
    const res = await apiClient.post('/auth/register', data);
    return res.data;
  },
  logout: async () => {
    const refreshToken = localStorage.getItem('auth_refresh_token');
    if (refreshToken) {
      await apiClient.post('/auth/logout', { refresh_token: refreshToken });
    }
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_refresh_token');
    localStorage.removeItem('auth_user');
  }
};

export const DataSourcesAPI = {
  list: async (): Promise<DataSource[]> => {
    const res = await apiClient.get('/data-sources');
    return res.data?.data_sources || [];
  },
  
  upload: async (file: File, contextHint?: string, indexingMode?: string): Promise<DataSource> => {
    const formData = new FormData();
    formData.append('file', file);
    if (contextHint) formData.append('context_hint', contextHint);
    if (indexingMode) formData.append('indexing_mode', indexingMode);
    
    const res = await apiClient.post('/data-sources/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  
  connectSQL: async (data: any): Promise<DataSource> => {
    const res = await apiClient.post('/data-sources/connect-sql', data);
    return res.data;
  },

  delete: async (id: string): Promise<{status: string}> => {
    const res = await apiClient.delete(`/data-sources/${id}`);
    return res.data;
  },

  getDataSource: async (id: string): Promise<DataSource> => {
    const res = await apiClient.get(`/data-sources/${id}/dashboard`);
    return res.data;
  },
  
  get: async (id: string): Promise<DataSource> => {
    const res = await apiClient.get(`/data-sources/${id}`);
    return res.data;
  }
};

export const AnalysisAPI = {
  submitQuery: async (question: string, sourceId: string, multiSourceIds?: string[], depthIndex: number = 3, chatHistory?: {role: string, content: string}[]): Promise<{job_id: string}> => {
    const res = await apiClient.post('/analysis/query', {
      question,
      source_id: sourceId,
      multi_source_ids: multiSourceIds,
      complexity_index: depthIndex,
      chat_history: chatHistory
    });
    return { job_id: res.data.id || res.data.job_id };
  },

  getHistory: async (): Promise<AnalysisJob[]> => {
    const res = await apiClient.get('/analysis/history');
    return res.data?.jobs || [];
  },

  getJobTracker: async (jobId: string): Promise<AnalysisJob> => {
    const res = await apiClient.get(`/analysis/${jobId}`);
    return res.data;
  },

  approveJob: async (jobId: string): Promise<{status: string}> => {
    const res = await apiClient.post(`/analysis/${jobId}/approve`);
    return res.data;
  },

  getJobResult: async (jobId: string): Promise<any> => {
    const res = await apiClient.get(`/analysis/${jobId}/result`);
    return res.data;
  },
  getSupersetToken: async (dashboardId: string): Promise<{ guest_token: string, superset_url: string }> => {
    const res = await apiClient.get('/superset/token', {
      params: { dashboard_id: dashboardId }
    });
    return res.data;
  }
};

export const VoiceAPI = {
  stt: async (audioBlob: Blob): Promise<{text: string}> => {
    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.webm');
    const res = await apiClient.post('/voice/stt', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  }
};

export const UserAPI = {
  list: async (): Promise<User[]> => {
    const res = await apiClient.get('/users');
    return res.data?.users || [];
  },
  invite: async (email: string, role: string, password: string, groupId?: string): Promise<User> => {
    const res = await apiClient.post('/users/invite', { 
      email, 
      role, 
      group_id: groupId,
      password: password
    });
    return res.data;
  },
  remove: async (userId: string): Promise<void> => {
    await apiClient.delete(`/users/${userId}`);
  }
};

export const GovernanceAPI = {
  list: async (): Promise<any[]> => {
    const res = await apiClient.get('/policies');
    return res.data?.policies || [];
  },
  create: async (data: any): Promise<any> => {
    const res = await apiClient.post('/policies', data);
    return res.data;
  },
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/policies/${id}`);
  }
};

export const KnowledgeAPI = {
  list: async (): Promise<any[]> => {
    const res = await apiClient.get('/knowledge');
    return res.data?.knowledge_bases || [];
  },
  create: async (data: any): Promise<any> => {
    const res = await apiClient.post('/knowledge', data);
    return res.data;
  },
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/knowledge/${id}`);
  },
  listDocuments: async (kbId: string): Promise<any[]> => {
    const res = await apiClient.get(`/knowledge/${kbId}/documents`);
    return res.data?.documents || [];
  },
  uploadDocument: async (kbId: string, file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await apiClient.post(`/knowledge/${kbId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  deleteDocument: async (kbId: string, docId: string): Promise<void> => {
    await apiClient.delete(`/knowledge/${kbId}/documents/${docId}`);
  }
};

export const MetricsAPI = {
  list: async (): Promise<any[]> => {
    const res = await apiClient.get('/metrics');
    return res.data?.metrics || [];
  },
  create: async (data: any): Promise<any> => {
    const res = await apiClient.post('/metrics', data);
    return res.data;
  },
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/metrics/${id}`);
  }
};

export const GroupsAPI = {
  list: async (): Promise<any[]> => {
    const res = await apiClient.get('/groups');
    return res.data || [];
  },
  create: async (data: { name: string, description?: string, permissions?: any }): Promise<any> => {
    const res = await apiClient.post('/groups', data);
    return res.data;
  },
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/groups/${id}`);
  }
};

export default apiClient;
