import { apiClient } from './apiClient';

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
