import { apiClient } from './apiClient';

export const UserAPI = {
  list: async (): Promise<any[]> => {
    const res = await apiClient.get('/users');
    return res.data?.users || [];
  },
  invite: async (email: string, role: string, password: string, groupId?: string): Promise<any> => {
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
