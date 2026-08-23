import { request } from "./client";
import type { PatternCheckResponse, ResumeResponse } from "@/types";

/** POST /agent/check-patterns — runs the LangGraph agent, pauses for human review. */
export function checkPatterns() {
  return request<PatternCheckResponse>("/agent/check-patterns", { method: "POST" });
}

/** POST /agent/resume/{thread_id}?decision=... — resume the interrupted graph. */
export function resumePatternCheck(threadId: string, decision: string) {
  return request<ResumeResponse>(`/agent/resume/${encodeURIComponent(threadId)}`, {
    method: "POST",
    query: { decision },
  });
}
