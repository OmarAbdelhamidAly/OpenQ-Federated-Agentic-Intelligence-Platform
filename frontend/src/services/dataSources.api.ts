import { apiClient } from './apiClient';
import type { DataSource } from '../types';

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

  connectGithub: async (data: { github_url: string, branch?: string, access_token?: string }): Promise<DataSource> => {
    const res = await apiClient.post('/data-sources/connect-github', data);
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
