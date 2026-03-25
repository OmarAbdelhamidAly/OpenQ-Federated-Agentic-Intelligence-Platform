import { useState, useCallback } from 'react';
import { AnalysisAPI } from '../services/api';
import type { AnalysisJob } from '../services/api';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content?: string;
  job?: AnalysisJob;
  isStreaming?: boolean;
}

export function useAnalysisPolling() {
  const [isProcessing, setIsProcessing] = useState(false);

  const startPolling = useCallback(async (
    jobId: string, 
    systemMessageId: string,
    onUpdate: (id: string, data: Partial<Message>) => void,
    onComplete: () => void
  ) => {
    setIsProcessing(true);
    
    const pollInterval = setInterval(async () => {
      try {
        const jobData = await AnalysisAPI.getJobTracker(jobId);
        
        const isDone = jobData.status === 'done';
        const isError = jobData.status === 'error';

        onUpdate(systemMessageId, {
          job: jobData,
          isStreaming: jobData.status === 'running' || jobData.status === 'pending'
        });

        if (isDone || isError) {
          clearInterval(pollInterval);
          
          if (isDone) {
            try {
              const result = await AnalysisAPI.getJobResult(jobId);
              onUpdate(systemMessageId, {
                job: { ...jobData, ...result },
                isStreaming: false
              });
            } catch (resErr) {
              console.error("Result fetch failed", resErr);
            }
          }

          setIsProcessing(false);
          onComplete();
        }
      } catch (err) {
        console.error("Polling error", err);
        clearInterval(pollInterval);
        setIsProcessing(false);
        onComplete();
      }
    }, 2000);

    return () => clearInterval(pollInterval);
  }, []);

  return {
    isProcessing,
    setIsProcessing,
    startPolling
  };
}
