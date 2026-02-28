import { useState } from 'react';

interface NewJobFormProps {
  onSubmit: (data: { title: string; user_query: string; stock_symbols: string }) => void;
  onBack: () => void;
}

export function NewJobForm({ onSubmit, onBack }: NewJobFormProps) {
  const [title, setTitle] = useState('');
  const [userQuery, setUserQuery] = useState('');
  const [stockSymbols, setStockSymbols] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ title, user_query: userQuery, stock_symbols: stockSymbols });
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

      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h2 className="text-xl font-semibold mb-6">Start New Research</h2>

        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Research Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="e.g., Tech Stock Analysis Q1 2026"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                What would you like to research?
              </label>
              <textarea
                value={userQuery}
                onChange={(e) => setUserQuery(e.target.value)}
                required
                rows={3}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="e.g., I want to understand the current sentiment around NVIDIA stock after their latest earnings report. Should I buy, hold, or sell?"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Stock Symbols (optional)
              </label>
              <input
                type="text"
                value={stockSymbols}
                onChange={(e) => setStockSymbols(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="e.g., NVDA, AAPL, MSFT"
              />
              <p className="text-sm text-gray-500 mt-1">Separate multiple symbols with commas</p>
            </div>
          </div>

          <button
            type="submit"
            className="mt-6 w-full bg-indigo-600 hover:bg-indigo-700 py-3 rounded-lg font-medium transition-colors"
          >
            Continue to Questions
          </button>
        </form>
      </div>
    </div>
  );
}
