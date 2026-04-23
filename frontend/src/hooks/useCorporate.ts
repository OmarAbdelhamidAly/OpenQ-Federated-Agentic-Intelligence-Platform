import { useState, useEffect, useCallback } from 'react';
import { CorporateAPI } from '../services/api';

export const useCorporate = () => {
  const [stats, setStats] = useState({ nodes: 0, goals: 0, policies: 0 });
  const [hierarchy, setHierarchy] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      const [nodes, goals, policies] = await Promise.all([
        CorporateAPI.getHierarchy(),
        CorporateAPI.getGoals(),
        CorporateAPI.getPolicies()
      ]);
      
      setStats({
        nodes: nodes.length,
        goals: goals.length,
        policies: policies.length
      });
      setHierarchy(nodes);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch corporate data", err);
      setError("Failed to sync with corporate records");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  return { stats, hierarchy, loading, error, refresh: fetchDashboardData };
};
