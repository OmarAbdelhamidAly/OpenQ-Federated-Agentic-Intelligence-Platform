import { apiClient } from './apiClient';
import type { AnalysisJob } from '../types';

export const AnalysisAPI = {
  submitQuery: async (question: string, sourceId: string, multiSourceIds?: string[], depthIndex: number = 3, chatHistory?: {role: string, content: string}[], sessionId?: string): Promise<{job_id: string}> => {
    const res = await apiClient.post('/analysis/query', {
      question,
      source_id: sourceId,
      multi_source_ids: multiSourceIds,
      complexity_index: depthIndex,
      chat_history: chatHistory,
      session_id: sessionId
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

  
  exportReport: async (jobId: string, format: 'pdf' | 'csv' | 'png'): Promise<{ file_url: string, status: string }> => {
    const res = await apiClient.post(`/reports/${jobId}/${format}`);
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
