// Types for the Research Agent

export interface Job {
  id: number;
  title: string;
  description: string;
  stock_symbols: string;
  user_query: string;
  clarifying_questions: string | null;
  user_answers: string | null;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export type JobStatus = 
  | 'pending' 
  | 'clarifying' 
  | 'researching' 
  | 'summarizing' 
  | 'completed' 
  | 'failed';

export interface Step {
  id: number;
  job_id: number;
  step_type: 'browse' | 'summarize';
  step_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  input_data: string | null;
  output_data: string | null;
  url: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export interface Report {
  id: number;
  job_id: number;
  title: string;
  summary: string;
  sentiment: 'Bullish' | 'Bearish' | 'Neutral' | 'Mixed';
  recommendation: 'Buy' | 'Sell' | 'Hold' | 'Monitor';
  full_report: string;
  sources: string[];
  created_at: string;
}

export interface Question {
  id: string;
  question: string;
  type: 'text' | 'select' | 'multiselect';
  placeholder?: string;
  options?: string[];
}

export interface CreateJobRequest {
  title: string;
  user_query: string;
  description?: string;
  stock_symbols?: string;
}

export interface StreamUpdate {
  type: 'init' | 'stage' | 'step' | 'job_completed' | 'job_failed' | 'heartbeat';
  job?: Job;
  steps?: Step[];
  stage?: string;
  status?: string;
  step_id?: number;
  step_type?: string;
  step_name?: string;
  url?: string;
  output?: string;
  error?: string;
  report?: Report;
}
