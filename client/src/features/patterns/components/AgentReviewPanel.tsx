import { useState } from "react";
import { Badge } from "@/components/Badge";
import type { PatternCheckResponse, ResumeResponse } from "@/types";

interface Props {
  check: {
    data: PatternCheckResponse | null;
    loading: boolean;
    error: string | null;
    run: () => void;
  };
  resume: {
    data: ResumeResponse | null;
    loading: boolean;
    error: string | null;
    run: (threadId: string, decision: string) => void;
  };
}

const DECISIONS = ["approve", "dismiss", "escalate"];

/** Human-in-the-loop control for the interrupted LangGraph agent. */
export function AgentReviewPanel({ check, resume }: Props) {
  const [decision, setDecision] = useState(DECISIONS[0]);
  const threadId = check.data?.thread_id ?? null;

  return (
    <div className="stack">
      <div className="row row--between row--wrap">
        <p className="small muted">
          Runs the LangGraph agent, which pauses for a human decision before anything is acted on.
        </p>
        <button type="button" className="btn" disabled={check.loading} onClick={() => check.run()}>
          {check.loading ? "Running agent…" : "Run pattern check"}
        </button>
      </div>

      {check.error ? <p className="small" style={{ color: "var(--danger)" }}>{check.error}</p> : null}

      {check.data && !threadId ? (
        <p className="small muted">{check.data.message ?? "No patterns requiring review were found."}</p>
      ) : null}

      {threadId ? (
        <div className="match-card">
          <div className="row row--between">
            <Badge tone="warning" upper>Awaiting human decision</Badge>
            <span className="mono dim">thread {threadId.slice(0, 8)}</span>
          </div>
          <p className="small">{check.data?.question}</p>
          <p className="small prewrap muted">{check.data?.findings}</p>

          <div className="row row--wrap">
            <select
              className="select"
              value={decision}
              onChange={(e) => setDecision(e.target.value)}
              style={{ width: 140 }}
            >
              {DECISIONS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn--sm"
              disabled={resume.loading}
              onClick={() => resume.run(threadId, decision)}
            >
              {resume.loading ? "Submitting…" : "Submit decision"}
            </button>
          </div>
        </div>
      ) : null}

      {resume.error ? <p className="small" style={{ color: "var(--danger)" }}>{resume.error}</p> : null}
      {resume.data ? (
        <div className="match-card">
          <Badge tone="success" upper>Decision recorded</Badge>
          <p className="small prewrap">{resume.data.final_result}</p>
        </div>
      ) : null}
    </div>
  );
}
