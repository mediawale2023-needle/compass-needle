'use client';

import { useEffect } from 'react';

export default function DashboardError({ error, reset }) {
  useEffect(() => {
    // Log to error monitoring (not console in production)
    if (process.env.NODE_ENV === 'development') {
      console.error('Dashboard error:', error);
    }
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-950 text-white">
      <div className="text-center max-w-md px-6">
        <div className="text-5xl mb-4">⚠️</div>
        <h2 className="text-xl font-semibold mb-2">Something went wrong</h2>
        <p className="text-gray-400 mb-6 text-sm">
          An unexpected error occurred. Please try again or contact support if the problem persists.
        </p>
        <button
          onClick={reset}
          className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
