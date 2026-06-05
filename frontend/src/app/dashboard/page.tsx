"use client";

import RouteGuard from "@/components/RouteGuard";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Dashboard — placeholder for the main authenticated view.
 * Protected by RouteGuard; redirects unauthenticated visitors to /login.
 */
function DashboardContent() {
  const { user, logout } = useAuth();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-gray-50 px-4">
      <div className="rounded-2xl bg-white px-10 py-8 shadow-sm ring-1 ring-gray-200 text-center space-y-4">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        {user && (
          <p className="text-sm text-gray-600">
            Signed in as <span className="font-medium">{user.email}</span>
          </p>
        )}
        <p className="text-sm text-gray-500">
          Full dashboard UI coming soon.
        </p>
        <button
          onClick={logout}
          className="mt-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Sign out
        </button>
      </div>
    </main>
  );
}

export default function DashboardPage() {
  return (
    <RouteGuard>
      <DashboardContent />
    </RouteGuard>
  );
}
