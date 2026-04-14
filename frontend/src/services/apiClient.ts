import axios from 'axios';
import type { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';

// Create a configured axios instance
export const apiClient = axios.create({
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
