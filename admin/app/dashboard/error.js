'use client';

import { useEffect } from 'react';

export default function AdminDashboardError({ error, reset }) {
  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      console.error('Admin dashboard error:', error);
    }
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-950 text-white">
      <div className="text-center max-w-md px-6">
        <div className="text-5xl mb-4">⚠️</div>
        <h2 className="text-xl font-semibold mb-2">Admin Dashboard Error</h2>
        <p className="text-gray-400 mb-6 text-sm">
          An unexpected error occurred in the admin panel. Please try again or contact the system administrator.
        </p>
        <button
          onClick={reset}
          className="px-5 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
