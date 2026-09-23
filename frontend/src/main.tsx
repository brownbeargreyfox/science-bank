import "@fontsource/atkinson-hyperlegible/400.css";
import "@fontsource/atkinson-hyperlegible/700.css";
import "@fontsource/atkinson-hyperlegible/400-italic.css";
import "@fontsource/source-serif-4/400.css";
import "@fontsource/source-serif-4/600.css";
import "@fontsource/source-serif-4/400-italic.css";
import "./index.css";

import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter } from "react-router";
import { RouterProvider } from "react-router/dom";
import { queryClient } from "./api/queries";
import { AppLayout, RequireAuth } from "./components/Layout";
import AssessmentBuilderPage from "./pages/AssessmentBuilder";
import AssessmentsPage from "./pages/Assessments";
import BundlesPage from "./pages/Bundles";
import GeneratePage from "./pages/Generate";
import HomePage from "./pages/Home";
import LoginPage from "./pages/Login";
import NotFoundPage from "./pages/NotFound";
import PrintPage from "./pages/Print";
import QuestionDetailPage from "./pages/QuestionDetail";
import QuestionsPage from "./pages/Questions";
import StandardDetailPage from "./pages/StandardDetail";
import StandardsPage from "./pages/Standards";

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      // Print views render without the app chrome.
      { path: "/assessments/:id/print/:variant", element: <PrintPage /> },
      {
        element: <AppLayout />,
        children: [
          { path: "/", element: <HomePage /> },
          { path: "/standards", element: <StandardsPage /> },
          { path: "/standards/:id", element: <StandardDetailPage /> },
          { path: "/bundles", element: <BundlesPage /> },
          { path: "/generate", element: <GeneratePage /> },
          { path: "/questions", element: <QuestionsPage /> },
          { path: "/questions/:id", element: <QuestionDetailPage /> },
          { path: "/assessments", element: <AssessmentsPage /> },
          { path: "/assessments/:id", element: <AssessmentBuilderPage /> },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
