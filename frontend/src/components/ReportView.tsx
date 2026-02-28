import { useEffect, useState } from 'react';
import type { Report } from '../types';
import { fetchReport } from '../api';

interface ReportViewProps {
  jobId: number;
  onBack: () => void;
}

export function ReportView({ jobId, onBack }: ReportViewProps) {
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadReport();
  }, [jobId]);

  const loadReport = async () => {
    try {
      const data = await fetchReport(jobId);
      setReport(data.report);
    } catch (error) {
      console.error('Failed to load report:', error);
    } finally {
      setLoading(false);
    }
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'Bullish': return 'bg-green-600/20 text-green-400';
      case 'Bearish': return 'bg-red-600/20 text-red-400';
      case 'Mixed': return 'bg-yellow-600/20 text-yellow-400';
      default: return 'bg-gray-600/20 text-gray-400';
    }
  };

  const getRecommendationColor = (rec: string) => {
    switch (rec) {
      case 'Buy': return 'bg-green-600/20 text-green-400';
      case 'Sell': return 'bg-red-600/20 text-red-400';
      case 'Hold': return 'bg-yellow-600/20 text-yellow-400';
      default: return 'bg-blue-600/20 text-blue-400';
    }
  };

  // Simple markdown renderer
  const renderMarkdown = (text: string) => {
    if (!text) return '';
    
    // Process tables first
    const tableRegex = /\|(.+)\|\n\|[-:| ]+\|\n((?:\|.+\|\n?)+)/g;
    let html = text.replace(tableRegex, (match, headerRow, bodyRows) => {
      const headers = headerRow.split('|').map((h: string) => h.trim()).filter(Boolean);
      const rows = bodyRows.trim().split('\n').map((row: string) => 
        row.split('|').map((cell: string) => cell.trim()).filter(Boolean)
      );
      
      let table = '<div class="overflow-x-auto my-4"><table class="min-w-full border-collapse">';
      table += '<thead><tr class="border-b border-gray-700">';
      headers.forEach((h: string) => {
        table += `<th class="px-4 py-2 text-left text-gray-200 font-semibold">${h}</th>`;
      });
      table += '</tr></thead><tbody>';
      rows.forEach((row: string[]) => {
        table += '<tr class="border-b border-gray-800">';
        row.forEach((cell: string) => {
          table += `<td class="px-4 py-2 text-gray-300">${cell}</td>`;
        });
        table += '</tr>';
      });
      table += '</tbody></table></div>';
      return table;
    });

    // Horizontal rules (must be on its own line)
    html = html.replace(/^---+$/gm, '<hr class="my-6 border-gray-700" />');
    html = html.replace(/^\*\*\*+$/gm, '<hr class="my-6 border-gray-700" />');
    html = html.replace(/^___+$/gm, '<hr class="my-6 border-gray-700" />');
    
    // Blockquotes (process before other inline formatting)
    html = html.replace(/^> (.+)$/gm, '<blockquote class="border-l-4 border-indigo-500 pl-4 my-3 text-gray-400 italic">$1</blockquote>');
    
    // Convert markdown to HTML (basic implementation)
    html = html
      // Headers (order matters - longer patterns first)
      .replace(/^#### (.+)$/gm, '<h4 class="text-base font-semibold mt-3 mb-2 text-gray-300">$1</h4>')
      .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-4 mb-2 text-gray-200">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="text-xl font-bold mt-6 mb-3 text-gray-100">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-6 mb-4 text-white">$1</h1>')
      // Bold
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-gray-100">$1</strong>')
      // Italic
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // Code blocks
      .replace(/```[\s\S]*?```/g, (match) => {
        const code = match.replace(/```\w*\n?/g, '').trim();
        return `<pre class="bg-gray-800 p-4 rounded-lg my-4 overflow-x-auto"><code class="text-sm text-gray-300">${code}</code></pre>`;
      })
      // Inline code
      .replace(/`(.+?)`/g, '<code class="bg-gray-800 px-1 py-0.5 rounded text-sm">$1</code>')
      // Lists
      .replace(/^- (.+)$/gm, '<li class="ml-4">$1</li>')
      .replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>')
      // Paragraphs
      .replace(/\n\n/g, '</p><p class="my-3 text-gray-300">')
      // Line breaks
      .replace(/\n/g, '<br/>');
    
    return `<p class="my-3 text-gray-300">${html}</p>`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500">Report not found</p>
        <button onClick={onBack} className="mt-4 text-indigo-400 hover:text-indigo-300">
          Back to Jobs
        </button>
      </div>
    );
  }

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

      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        {/* Report Header */}
        <div className="p-6 border-b border-gray-800 bg-gradient-to-r from-indigo-900/30 to-purple-900/30">
          <h2 className="text-2xl font-bold mb-2">{report.title}</h2>
          <div className="flex flex-wrap gap-4 text-sm">
            <span className={`px-3 py-1 rounded-full ${getSentimentColor(report.sentiment)}`}>
              Sentiment: {report.sentiment}
            </span>
            <span className={`px-3 py-1 rounded-full ${getRecommendationColor(report.recommendation)}`}>
              Recommendation: {report.recommendation}
            </span>
          </div>
        </div>

        {/* Report Summary */}
        <div className="p-6 border-b border-gray-800">
          <h3 className="text-lg font-semibold mb-3 text-indigo-400">Executive Summary</h3>
          <p className="text-gray-300 leading-relaxed">{report.summary}</p>
        </div>

        {/* Full Report */}
        <div className="p-6">
          <h3 className="text-lg font-semibold mb-4 text-indigo-400">Full Report</h3>
          <div 
            className="prose prose-invert max-w-none"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(report.full_report) }}
          />
        </div>

        {/* Sources */}
        <div className="p-6 border-t border-gray-800 bg-gray-950/50">
          <h3 className="text-sm font-semibold mb-3 text-gray-400">Sources</h3>
          <div className="flex flex-wrap gap-2">
            {report.sources?.map((source, index) => (
              <a
                key={index}
                href={source}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs px-2 py-1 bg-gray-800 rounded hover:bg-gray-700 transition-colors truncate max-w-xs"
              >
                {source.replace(/https?:\/\//, '').substring(0, 40)}...
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
