"use client";

import { useEffect, useState } from "react";

type HealthStatus = "checking" | "healthy" | "unreachable";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    fetch(`${API_URL}/healthz`, { signal: controller.signal })
      .then((res) => {
        if (res.ok) setStatus("healthy");
        else setStatus("unreachable");
      })
      .catch(() => setStatus("unreachable"))
      .finally(() => clearTimeout(timeout));

    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, []);

  const statusColors: Record<HealthStatus, string> = {
    checking: "bg-yellow-400",
    healthy: "bg-green-500",
    unreachable: "bg-red-500",
  };

  const statusLabels: Record<HealthStatus, string> = {
    checking: "Checking…",
    healthy: "Backend healthy",
    unreachable: "Backend unreachable",
  };

  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gray-50 dark:bg-gray-950 p-8">
      <div className="max-w-lg w-full text-center space-y-8">
        {/* Logo / wordmark */}
        <div className="space-y-2">
          <h1 className="text-5xl font-bold tracking-tight text-gray-900 dark:text-white">
            CairnBooks
          </h1>
          <p className="text-lg text-gray-500 dark:text-gray-400">
            Open-source, multi-tenant bookkeeping for small businesses.
          </p>
        </div>

        {/* Health badge */}
        <div className="inline-flex items-center gap-2 rounded-full border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-2 shadow-sm">
          <span
            className={`h-2.5 w-2.5 rounded-full ${statusColors[status]} ${
              status === "checking" ? "animate-pulse" : ""
            }`}
          />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {statusLabels[status]}
          </span>
        </div>

        {/* Placeholder nav links */}
        <nav className="flex justify-center gap-6 text-sm text-gray-400 dark:text-gray-500">
          <a
            href="#"
            className="hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
          >
            Docs
          </a>
          <a
            href="#"
            className="hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
          >
            API
          </a>
          <a
            href="https://github.com/ray-berg/CairnBooks"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
          >
            GitHub
          </a>
        </nav>
      </div>
    </main>
  );
}
