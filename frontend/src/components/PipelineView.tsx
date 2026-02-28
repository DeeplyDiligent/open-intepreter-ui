import { useEffect, useState, useRef } from 'react';
import type { Job, Step, Report, StreamUpdate } from '../types';
import { createJobStream } from '../api';

interface PipelineViewProps {
  jobId: number;
  initialJob?: Job;
  initialSteps?: Step[];
  onBack: () => void;
  onViewReport: (jobId: number) => void;
}

type StageStatus = 'pending' | 'running' | 'completed';

export function PipelineView({ jobId, initialJob, initialSteps, onBack, onViewReport }: PipelineViewProps) {
  const [job, setJob] = useState<Job | null>(initialJob || null);
  const [steps, setSteps] = useState<Step[]>(initialSteps || []);
  const [pipelineStatus, setPipelineStatus] = useState<string>('Initializing...');
  const [browsingStage, setBrowsingStage] = useState<StageStatus>('pending');
  const [summarizingStage, setSummarizingStage] = useState<StageStatus>('pending');
  const [completeStage, setCompleteStage] = useState<StageStatus>('pending');
  const [quickReport, setQuickReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const stepsContainerRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const eventSource = createJobStream(jobId);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      const data: StreamUpdate = JSON.parse(event.data);
      handleStreamUpdate(data);
    };

    eventSource.onerror = () => {
      console.error('SSE connection error');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [jobId]);

  const handleStreamUpdate = (data: StreamUpdate) => {
    if (data.type === 'init') {
      if (data.job) {
        setJob(data.job);
        setPipelineStatus(data.job.status);
      }
      if (data.steps) {
        setSteps(data.steps);
      }
    } else if (data.type === 'stage') {
      if (data.stage === 'browsing') {
        setBrowsingStage(data.status as StageStatus);
      } else if (data.stage === 'summarizing') {
        setSummarizingStage(data.status as StageStatus);
        if (data.status === 'running') {
          setBrowsingStage('completed');
        }
      }
      if (data.stage) {
        setPipelineStatus(data.stage);
      }
    } else if (data.type === 'step') {
      if (data.status === 'running' && data.step_id) {
        const newStep: Step = {
          id: data.step_id,
          job_id: jobId,
          step_type: (data.step_type as 'browse' | 'summarize') || 'browse',
          step_name: data.step_name || '',
          status: 'running',
          url: data.url || null,
          input_data: null,
          output_data: null,
          started_at: new Date().toISOString(),
          completed_at: null,
          error_message: null,
        };
        setSteps((prev) => [...prev, newStep]);
        
        // Auto-scroll to bottom
        setTimeout(() => {
          if (stepsContainerRef.current) {
            stepsContainerRef.current.scrollTop = stepsContainerRef.current.scrollHeight;
          }
        }, 100);
      } else if (data.step_id) {
        setSteps((prev) =>
          prev.map((step) =>
            step.id === data.step_id
              ? { ...step, status: data.status as Step['status'], error_message: data.error || null }
              : step
          )
        );
      }
    } else if (data.type === 'job_completed') {
      setCompleteStage('completed');
      setSummarizingStage('completed');
      setPipelineStatus('Completed');
      if (data.report) {
        setQuickReport(data.report as Report);
      }
    } else if (data.type === 'job_failed') {
      setPipelineStatus('Failed');
      setError(data.error || 'Unknown error');
    }
  };

  const getStageClasses = (stage: StageStatus) => {
    if (stage === 'running') {
      return 'bg-indigo-600 animate-pulse';
    } else if (stage === 'completed') {
      return 'bg-green-600';
    }
    return 'bg-gray-800';
  };

  const getStageIconClasses = (stage: StageStatus) => {
    if (stage === 'pending') {
      return 'text-gray-500';
    }
    return 'text-white';
  };

  return (
    <div>
      <button
        onClick={onBack}
        className="text-gray-400 hover:text-white mb-4 flex items-center gap-2"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to Jobs
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pipeline Status */}
        <div className="lg:col-span-2">
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <div className="p-4 border-b border-gray-800 flex items-center justify-between">
              <h3 className="font-semibold">Research Pipeline</h3>
              <span className={`text-sm px-3 py-1 rounded-full ${
                pipelineStatus === 'Completed' 
                  ? 'bg-green-600/20 text-green-400'
                  : pipelineStatus === 'Failed'
                  ? 'bg-red-600/20 text-red-400'
                  : 'bg-indigo-600/20 text-indigo-400'
              }`}>
                {pipelineStatus}
              </span>
            </div>

            {/* Stage Indicators */}
            <div className="p-4 border-b border-gray-800">
              <div className="flex items-center justify-between">
                <div className="flex flex-col items-center flex-1">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 transition-all ${getStageClasses(browsingStage)}`}>
                    <svg className={`w-5 h-5 ${getStageIconClasses(browsingStage)}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                    </svg>
                  </div>
                  <span className="text-xs text-gray-400">Browsing</span>
                </div>
                <div className="flex-1 h-0.5 bg-gray-800 -mt-6"></div>
                <div className="flex flex-col items-center flex-1">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 transition-all ${getStageClasses(summarizingStage)}`}>
                    <svg className={`w-5 h-5 ${getStageIconClasses(summarizingStage)}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <span className="text-xs text-gray-400">Summarizing</span>
                </div>
                <div className="flex-1 h-0.5 bg-gray-800 -mt-6"></div>
                <div className="flex flex-col items-center flex-1">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 transition-all ${getStageClasses(completeStage)}`}>
                    <svg className={`w-5 h-5 ${getStageIconClasses(completeStage)}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <span className="text-xs text-gray-400">Complete</span>
                </div>
              </div>
            </div>

            {/* Steps List */}
            <div ref={stepsContainerRef} className="p-4 space-y-3 max-h-[500px] overflow-y-auto relative">
              {steps.length === 0 ? (
                <div className="text-gray-500 text-sm text-center py-4">
                  Waiting for research to start...
                </div>
              ) : (
                <div className="relative">
                  {/* Vertical line */}
                  <div className="absolute left-5 top-5 bottom-5 w-0.5 bg-gradient-to-b from-indigo-500 to-purple-500"></div>
                  
                  {steps.map((step) => (
                    <div key={step.id} className="relative pl-12 pb-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
                      <div className={`absolute left-0 w-10 h-10 rounded-full bg-gray-800 flex items-center justify-center ${
                        step.status === 'running' ? 'animate-pulse' : ''
                      }`}>
                        {step.status === 'completed' ? (
                          <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        ) : step.status === 'failed' ? (
                          <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                          </svg>
                        )}
                      </div>
                      <div className="bg-gray-800/50 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium text-sm">{step.step_name}</span>
                          <span className={`text-xs ${
                            step.status === 'completed' ? 'text-green-400' :
                            step.status === 'failed' ? 'text-red-400' :
                            'text-blue-400'
                          }`}>
                            {step.status}
                          </span>
                        </div>
                        {step.url && (
                          <a
                            href={step.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-gray-500 hover:text-indigo-400 truncate block"
                          >
                            {step.url}
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              
              {error && (
                <div className="bg-red-600/10 border border-red-600/20 rounded-lg p-4 mt-4">
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Job Info */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
            <h3 className="font-semibold mb-3">Job Details</h3>
            <div className="space-y-2 text-sm">
              <div className="text-gray-400">Title</div>
              <div className="text-gray-100 mb-2">{job?.title || 'Loading...'}</div>
              <div className="text-gray-400">Stocks</div>
              <div className="text-indigo-400 mb-2">{job?.stock_symbols || 'Detecting...'}</div>
              <div className="text-gray-400">Query</div>
              <div className="text-gray-300 text-xs">{job?.user_query || ''}</div>
            </div>
          </div>

          {/* Quick Report */}
          {quickReport && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
              <h3 className="font-semibold mb-3">Quick Summary</h3>
              <div className="space-y-2 text-sm">
                <div className="flex gap-2 mb-3">
                  <span className={`px-2 py-1 rounded text-xs ${
                    quickReport.sentiment === 'Bullish' ? 'bg-green-600/20 text-green-400' :
                    quickReport.sentiment === 'Bearish' ? 'bg-red-600/20 text-red-400' :
                    quickReport.sentiment === 'Mixed' ? 'bg-yellow-600/20 text-yellow-400' :
                    'bg-gray-600/20 text-gray-400'
                  }`}>
                    {quickReport.sentiment}
                  </span>
                  <span className="px-2 py-1 rounded text-xs bg-indigo-600/20 text-indigo-400">
                    {quickReport.recommendation}
                  </span>
                </div>
                <p className="text-gray-300 text-sm">
                  {quickReport.summary?.substring(0, 200)}...
                </p>
                <button
                  onClick={() => onViewReport(jobId)}
                  className="mt-3 text-sm text-indigo-400 hover:text-indigo-300"
                >
                  View Full Report →
                </button>
              </div>
            </div>
          )}

          {/* View Report Button - shows when job is completed */}
          {job?.status === 'completed' && (
            <button
              onClick={() => onViewReport(jobId)}
              className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-3 px-4 rounded-xl transition-colors"
            >
              View Full Report
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
