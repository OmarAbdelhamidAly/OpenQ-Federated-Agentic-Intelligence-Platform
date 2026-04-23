import { apiClient } from './apiClient';

export const VisionAPI = {
  getCameras: async () => {
    const response = await apiClient.get('/vision/cameras');
    return response.data;
  },
  
  getUserTimeline: async (userId: string, date: string) => {
    const response = await apiClient.get(`/vision/logs/${userId}?date=${date}`);
    return response.data;
  },
  
  getGlobalEngagement: async () => {
    const response = await apiClient.get('/vision/analytics/engagement');
    return response.data;
  }
};
