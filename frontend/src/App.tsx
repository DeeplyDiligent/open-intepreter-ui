import { useState, useEffect, useCallback } from 'react';
import { JobList, NewJobForm, QuestionsForm, PipelineView, ReportView } from './components';
import * as api from './api';
import type { Job, Question, Step } from './types';

type View = 'list' | 'new' | 'questions' | 'pipeline' | 'report';

function App() {
  const [view, setView] = useState<View>('list');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [currentJobId, setCurrentJobId] = useState<number | null>(null);
  const [currentJob, setCurrentJob] = useState<Job | null>(null);
  const [currentSteps, setCurrentSteps] = useState<Step[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);

  const loadJobs = useCallback(async () => {
    try {
      const jobList = await api.fetchJobs();
      setJobs(jobList);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    }
  }, []);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const handleNewJob = () => {
    setView('new');
  };

  const handleBack = () => {
    setView('list');
    setCurrentJobId(null);
    setCurrentJob(null);
    setCurrentSteps([]);
    setQuestions([]);
    loadJobs();
  };

  const handleJobClick = async (job: Job) => {
    setCurrentJobId(job.id);
    setCurrentJob(job);

    if (job.status === 'pending') {
      try {
        const data = await api.generateClarifyingQuestions(job.id);
        setQuestions(data.questions);
        setView('questions');
      } catch (error) {
        console.error('Failed to get questions:', error);
      }
    } else if (job.status === 'clarifying') {
      try {
        const data = await api.fetchJob(job.id);
        const parsedQuestions = JSON.parse(data.job.clarifying_questions || '[]');
        setQuestions(parsedQuestions);
        setView('questions');
      } catch (error) {
        console.error('Failed to load job:', error);
      }
    } else if (job.status === 'researching' || job.status === 'summarizing') {
      try {
        const data = await api.fetchJob(job.id);
        setCurrentJob(data.job);
        setCurrentSteps(data.steps);
        setView('pipeline');
      } catch (error) {
        console.error('Failed to load job:', error);
      }
    } else if (job.status === 'completed') {
      try {
        const data = await api.fetchJob(job.id);
        setCurrentJob(data.job);
        setCurrentSteps(data.steps);
        setView('pipeline');
      } catch (error) {
        console.error('Failed to load job:', error);
      }
    } else if (job.status === 'failed') {
      try {
        const data = await api.fetchJob(job.id);
        setCurrentJob(data.job);
        setCurrentSteps(data.steps);
        setView('pipeline');
      } catch (error) {
        console.error('Failed to load job:', error);
      }
    }
  };

  const handleDeleteJob = async (jobId: number) => {
    try {
      await api.deleteJob(jobId);
      loadJobs();
    } catch (error) {
      console.error('Failed to delete job:', error);
    }
  };

  const handleCreateJob = async (data: { title: string; user_query: string; stock_symbols: string }) => {
    try {
      const result = await api.createJob({
        title: data.title,
        user_query: data.user_query,
        stock_symbols: data.stock_symbols,
      });
      
      setCurrentJobId(result.job_id);
      
      const clarifyData = await api.generateClarifyingQuestions(result.job_id);
      setQuestions(clarifyData.questions);
      setView('questions');
    } catch (error) {
      console.error('Failed to create job:', error);
    }
  };

  const handleSubmitAnswers = async (answers: Record<string, string | string[]>) => {
    if (!currentJobId) return;
    
    try {
      await api.submitAnswers(currentJobId, answers);
      setView('pipeline');
    } catch (error) {
      console.error('Failed to submit answers:', error);
    }
  };

  const handleViewReport = (jobId: number) => {
    setCurrentJobId(jobId);
    setView('report');
  };

  return (
    <div className="bg-gray-950 text-gray-100 min-h-screen">
      <div className="max-w-7xl mx-auto p-6">
        {/* Header */}
        <header className="mb-8 flex items-center gap-4">
          <img src="/vite.svg" alt="Logo" className="w-10 h-10" />
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Financial Research Agent
            </h1>
            <p className="text-gray-400 mt-1">AI-powered stock research and sentiment analysis</p>
          </div>
        </header>

        {/* Main Content */}
        <main>
          {view === 'list' && (
            <JobList
              jobs={jobs}
              onJobClick={handleJobClick}
              onDeleteJob={handleDeleteJob}
              onNewJob={handleNewJob}
              onViewReport={handleViewReport}
            />
          )}

          {view === 'new' && (
            <NewJobForm
              onSubmit={handleCreateJob}
              onBack={handleBack}
            />
          )}

          {view === 'questions' && (
            <QuestionsForm
              questions={questions}
              onSubmit={handleSubmitAnswers}
              onBack={handleBack}
            />
          )}

          {view === 'pipeline' && currentJobId && (
            <PipelineView
              jobId={currentJobId}
              initialJob={currentJob || undefined}
              initialSteps={currentSteps}
              onBack={handleBack}
              onViewReport={handleViewReport}
            />
          )}

          {view === 'report' && currentJobId && (
            <ReportView
              jobId={currentJobId}
              onBack={handleBack}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
