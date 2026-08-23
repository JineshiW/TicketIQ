import { Card } from "@/components/Card";
import { SimilarityResults } from "@/features/submit/components/SimilarityResults";
import { TicketForm } from "@/features/submit/components/TicketForm";
import { useTicketSubmission } from "@/features/submit/useTicketSubmission";

export function SubmitTicketPage() {
  const {
    drafts,
    isValid,
    addDraft,
    removeDraft,
    updateDraft,
    similarity,
    save,
    checkSimilarity,
    storeTickets,
  } = useTicketSubmission();

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Submit a Ticket</h1>
          <p>Find similar past tickets and get instant AI-powered suggestions.</p>
        </div>
      </div>

      <div className="grid grid--split">
        <Card>
          <div className="stack" style={{ gap: 14 }}>
            {drafts.map((draft, index) => (
              <TicketForm
                key={draft.key}
                draft={draft}
                index={index}
                canRemove={drafts.length > 1}
                onChange={updateDraft}
                onRemove={removeDraft}
              />
            ))}

            <div className="row row--between row--wrap">
              <button type="button" className="btn btn--ghost btn--sm" onClick={addDraft}>
                + Add another ticket
              </button>
              <div className="row">
                <button
                  type="button"
                  className="btn btn--ghost btn--sm"
                  disabled={!isValid || save.loading}
                  onClick={() => void storeTickets()}
                >
                  {save.loading ? "Storing…" : "Store ticket"}
                </button>
                <button
                  type="button"
                  className="btn"
                  disabled={!isValid || similarity.loading}
                  onClick={() => void checkSimilarity()}
                >
                  {similarity.loading ? "Checking…" : "Check Similarity ⌕"}
                </button>
              </div>
            </div>

            {save.error ? (
              <p className="small" style={{ color: "var(--danger)" }}>{save.error}</p>
            ) : null}
            {save.data ? (
              <p className="small" style={{ color: "var(--success)" }}>
                {save.data.message ??
                  `Stored ${save.data.added ?? 0} ticket(s), skipped ${save.data.skipped ?? 0}.`}
              </p>
            ) : null}
          </div>
        </Card>

        <SimilarityResults
          results={similarity.data}
          loading={similarity.loading}
          error={similarity.error}
          onRetry={() => void checkSimilarity()}
        />
      </div>
    </div>
  );
}
