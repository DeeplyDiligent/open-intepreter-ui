// API service for Research Agent

import type { Job, Step, Report, Question, CreateJobRequest } from './types';

const API_BASE = '/api';

export async function fetchJobs(): Promise<Job[]> {
  const response = await fetch(`${API_BASE}/jobs`);
  const data = await response.json();
  return data.jobs;
}

export async function fetchJob(jobId: number): Promise<{ job: Job; steps: Step[]; report: Report | null }> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}`);
  return response.json();
}

export async function createJob(request: CreateJobRequest): Promise<{ job_id: number; status: string }> {
  const response = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return response.json();
}

export async function deleteJob(jobId: number): Promise<void> {
  await fetch(`${API_BASE}/jobs/${jobId}`, { method: 'DELETE' });
}

export async function generateClarifyingQuestions(jobId: number): Promise<{ questions: Question[]; extracted_info?: Record<string, unknown> }> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/clarify`, { method: 'POST' });
  return response.json();
}

export async function submitAnswers(jobId: number, answers: Record<string, unknown>): Promise<{ status: string; job_id: number }> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/answers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId, answers }),
  });
  return response.json();
}

export async function fetchReport(jobId: number): Promise<{ report: Report }> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/report`);
  return response.json();
}

export function createJobStream(jobId: number): EventSource {
  return new EventSource(`${API_BASE}/jobs/${jobId}/stream`);
}

export async function fetchInitialQuestions(): Promise<{ questions: Question[] }> {
  const response = await fetch(`${API_BASE}/initial-questions`);
  return response.json();
}
