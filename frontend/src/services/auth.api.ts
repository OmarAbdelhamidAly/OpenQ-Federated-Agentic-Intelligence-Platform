import { apiClient } from './apiClient';

interface AuthResponse {
  message: string;
  access_token: string;
  refresh_token: string;
  user: any;
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
