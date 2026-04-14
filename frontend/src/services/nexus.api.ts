import { apiClient } from './apiClient';
import type { AnalysisJob } from '../types';

export interface AnalysisQueryRequest {
  question: string;
  source_ids: string[];
}

export const nexusApi = {
  /**
   * Submit a multi-source Strategic Nexus query.
   */
  submitQuery: async (data: AnalysisQueryRequest): Promise<AnalysisJob> => {
    const payload = {
      question: data.question,
      source_id: data.source_ids[0],
      multi_source_ids: data.source_ids.slice(1)
    };
    const response = await apiClient.post<AnalysisJob>('/analysis/nexus/query', payload);
    return response.data;
  },

  /**
   * Get nexus job status.
   */
  getJobStatus: async (jobId: string): Promise<AnalysisJob> => {
    const response = await apiClient.get<AnalysisJob>(`/analysis/${jobId}`);
    return response.data;
  },

  /**
   * Get final synthesis result.
   */
  getResult: async (jobId: string) => {
    const response = await apiClient.get<AnalysisJob>(`/analysis/${jobId}/result`);
    return response.data;
  }
};
