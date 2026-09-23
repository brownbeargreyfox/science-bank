import { useEffect, useState } from "react";

type BackendStatus = "checking" | "ok" | "error";

function App() {
  const [status, setStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    fetch("/healthz")
      .then((res) => setStatus(res.ok ? "ok" : "error"))
      .catch(() => setStatus("error"));
  }, []);

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-4 px-6 text-slate-900 dark:text-slate-100">
      <h1 className="text-3xl font-semibold">Science Bank</h1>
      <p className="text-slate-600 dark:text-slate-400">
        Question bank &amp; assessment builder for SC Biology 1, Biology 2, and Chemistry.
      </p>
      <div className="flex items-center gap-2 text-sm">
        <span
          className={`h-2.5 w-2.5 rounded-full ${
            status === "ok" ? "bg-green-500" : status === "error" ? "bg-red-500" : "bg-amber-400"
          }`}
        />
        <span>
          Backend: {status === "checking" ? "checking…" : status === "ok" ? "connected" : "unreachable"}
        </span>
      </div>
    </div>
  );
}

export default App;
