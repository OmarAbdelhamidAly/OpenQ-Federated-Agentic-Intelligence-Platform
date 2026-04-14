import { apiClient } from './apiClient';

export interface CodeNode {
  id: number;
  type: string;
  name?: string;
  path?: string;
  summary?: string;
}

export interface CodeLink {
  source: number;
  target: number;
  type: string;
}

export interface CodeGraphResponse {
  nodes: CodeNode[];
  links: CodeLink[];
}

export const CodebaseAPI = {
  getGraph: async (sourceId: string): Promise<CodeGraphResponse> => {
    const response = await apiClient.get<CodeGraphResponse>(`/api/v1/codebase/${sourceId}/graph`);
    return response.data;
  },
};
