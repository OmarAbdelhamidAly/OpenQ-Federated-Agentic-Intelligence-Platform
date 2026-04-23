import { useState, useEffect, useCallback } from 'react';
import { VisionAPI } from '../services/api';

export const useVision = () => {
  const [cameras, setCameras] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchVisionData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await VisionAPI.getCameras();
      setCameras(data);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch vision data", err);
      setError("Failed to sync with vision sensors");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchVisionData();
  }, [fetchVisionData]);

  return { cameras, loading, error, refresh: fetchVisionData };
};
