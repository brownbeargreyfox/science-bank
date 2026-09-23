import { QueryClient, useQuery } from "@tanstack/react-query";
import { ApiError, api, cleanQuery, setUnauthorizedHandler, unwrap } from "./client";
import type { Status } from "./types";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (count, err) => {
        if (err instanceof ApiError && err.status >= 400 && err.status < 500) return false;
        return count < 2;
      },
    },
  },
});

export const ME_KEY = ["auth", "me"] as const;

setUnauthorizedHandler(() => {
  if (queryClient.getQueryData(ME_KEY) !== null) queryClient.setQueryData(ME_KEY, null);
});

export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async () => {
      try {
        return await unwrap(api.GET("/api/auth/me"));
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: Infinity,
  });
}

export function useCourses() {
  return useQuery({
    queryKey: ["courses"],
    queryFn: () => unwrap(api.GET("/api/courses")),
    staleTime: 5 * 60_000,
  });
}

export function useFamilies() {
  return useQuery({
    queryKey: ["families"],
    queryFn: () => unwrap(api.GET("/api/families")),
    staleTime: 5 * 60_000,
  });
}

export interface StandardsFilter {
  course_id?: number | null;
  q?: string | null;
  domain?: string | null;
  topic?: string | null;
  with_family_only?: boolean;
}

export function useStandards(filter: StandardsFilter, enabled = true) {
  return useQuery({
    queryKey: ["standards", filter],
    queryFn: () =>
      unwrap(
        api.GET("/api/standards", {
          params: {
            query: cleanQuery({
              course_id: filter.course_id,
              q: filter.q,
              domain: filter.domain,
              topic: filter.topic,
              with_family_only: filter.with_family_only || undefined,
            }),
          },
        }),
      ),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useStandard(id: number | null) {
  return useQuery({
    queryKey: ["standard", id],
    queryFn: () => unwrap(api.GET("/api/standards/{standard_id}", { params: { path: { standard_id: id ?? 0 } } })),
    enabled: id !== null,
  });
}

export interface QuestionFilter {
  status?: Status[];
  course_id?: number | null;
  standard_id?: number | null;
  family_key?: string | null;
  dok?: number[];
  question_type?: "multiple_choice" | "constructed_response" | null;
  stimulus_id?: number | null;
  q?: string | null;
  page?: number;
  page_size?: number;
}

export function fetchQuestions(filter: QuestionFilter) {
  return unwrap(api.GET("/api/questions", { params: { query: cleanQuery({ ...filter }) } }));
}

export function useQuestions(filter: QuestionFilter) {
  return useQuery({
    queryKey: ["questions", filter],
    queryFn: () => fetchQuestions(filter),
    placeholderData: (prev) => prev,
  });
}

export function useAssessments() {
  return useQuery({
    queryKey: ["assessments"],
    queryFn: () => unwrap(api.GET("/api/assessments")),
  });
}
