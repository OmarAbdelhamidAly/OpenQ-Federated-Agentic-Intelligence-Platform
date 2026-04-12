import { useState, useCallback } from 'react';
import { AnalysisAPI } from '../services/api';
import type { AnalysisJob, Message } from '../types';

export function useAnalysisPolling() {
  const [isProcessing, setIsProcessing] = useState(false);

  const startPolling = useCallback(async (
    jobId: string, 
    systemMessageId: string,
    onUpdate: (id: string, data: Partial<Message>) => void,
    onComplete: () => void,
    onHITL?: (jobId: string, job: AnalysisJob) => void
  ) => {
    setIsProcessing(true);
    
    const pollInterval = setInterval(async () => {
      try {
        const jobData = await AnalysisAPI.getJobTracker(jobId);
        
        const isDone = jobData.status === 'done';
        const isError = jobData.status === 'error';
        const isAwaitingApproval = jobData.status === 'awaiting_approval';

        onUpdate(systemMessageId, {
          job: jobData,
          isStreaming: jobData.status === 'running' || jobData.status === 'pending'
        });

        if (isDone || isError || isAwaitingApproval) {
          clearInterval(pollInterval);
          setIsProcessing(false);

          if (isDone) {
            try {
              const result = await AnalysisAPI.getJobResult(jobId);
              onUpdate(systemMessageId, {
                job: { ...jobData, ...result },
                isStreaming: false
              });
            } catch (resErr) {
              console.error("Result fetch failed", resErr);
              onUpdate(systemMessageId, { job: jobData, isStreaming: false });
            }
          } else if (isAwaitingApproval && onHITL) {
            onUpdate(systemMessageId, { job: jobData, isStreaming: false });
            onHITL(jobId, jobData);
          } else {
            // error state
            onUpdate(systemMessageId, { job: jobData, isStreaming: false });
          }

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
