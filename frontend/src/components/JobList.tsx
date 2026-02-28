import type { Job, JobStatus } from '../types';

interface JobListProps {
  jobs: Job[];
  onJobClick: (job: Job) => void;
  onDeleteJob: (jobId: number) => void;
  onNewJob: () => void;
  onViewReport: (jobId: number) => void;
}

const statusColors: Record<JobStatus, string> = {
  pending: 'bg-gray-600/20 text-gray-400',
  clarifying: 'bg-yellow-600/20 text-yellow-400',
  researching: 'bg-blue-600/20 text-blue-400',
  summarizing: 'bg-purple-600/20 text-purple-400',
  completed: 'bg-green-600/20 text-green-400',
  failed: 'bg-red-600/20 text-red-400',
};

export function JobList({ jobs, onJobClick, onDeleteJob, onNewJob, onViewReport }: JobListProps) {
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold text-gray-200">Research Jobs</h2>
        <button
          onClick={onNewJob}
          className="bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Research Job
        </button>
      </div>

      <div className="space-y-4">
        {jobs.length === 0 ? (
          <div className="text-gray-500 text-center py-12">
            <svg className="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p>No research jobs yet. Create one to get started!</p>
          </div>
        ) : (
          jobs.map((job) => (
            <div
              key={job.id}
              className="bg-gray-900 rounded-xl border border-gray-800 p-4 hover:border-gray-700 transition-colors cursor-pointer animate-in fade-in slide-in-from-bottom-2 duration-300"
              onClick={() => onJobClick(job)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-100">{job.title}</h3>
                  <p className="text-sm text-gray-400 mt-1 line-clamp-2">{job.user_query}</p>
                  {job.stock_symbols && (
                    <p className="text-sm text-indigo-400 mt-2">📈 {job.stock_symbols}</p>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span className={`text-xs px-2 py-1 rounded-full ${statusColors[job.status]}`}>
                    {job.status}
                  </span>
                  <span className="text-xs text-gray-500">
                    {new Date(job.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                {job.status === 'completed' && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onViewReport(job.id);
                    }}
                    className="text-sm px-3 py-1 bg-indigo-600/20 text-indigo-400 rounded-lg hover:bg-indigo-600/30"
                  >
                    View Report
                  </button>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm('Are you sure you want to delete this job?')) {
                      onDeleteJob(job.id);
                    }
                  }}
                  className="text-sm px-3 py-1 bg-red-600/10 text-red-400 rounded-lg hover:bg-red-600/20"
                >
                  Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
