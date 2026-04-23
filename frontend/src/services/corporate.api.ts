import { apiClient } from './apiClient';

export const CorporateAPI = {
  getHierarchy: async () => {
    const response = await apiClient.get('/corporate/hierarchy/nodes');
    return response.data;
  },
  
  getStrategicAnalysis: async (tenantId: string) => {
    const response = await apiClient.get(`/corporate/strategy/analysis?tenant_id=${tenantId}`);
    return response.data;
  },
  
  getGoals: async () => {
    const response = await apiClient.get('/corporate/strategy/goals');
    return response.data;
  },
  
  getPolicies: async () => {
    const response = await apiClient.get('/corporate/strategy/policies');
    return response.data;
  }
};
