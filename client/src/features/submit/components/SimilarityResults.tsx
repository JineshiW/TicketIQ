import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { EmptyState, ErrorState, Loading } from "@/components/States";
import type { BatchSimilarResult } from "@/types";
import { AiInsightCard } from "./AiInsightCard";
import { SimilarTicketCard } from "./SimilarTicketCard";

interface Props {
  results: BatchSimilarResult[] | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

export function SimilarityResults({ results, loading, error, onRetry }: Props) {
  const matchCount = results?.reduce((sum, r) => sum + r.result.similar_tickets.length, 0) ?? 0;

  return (
    <Card
      title="⟲ Similar Past Tickets"
      action={results ? <Badge>{matchCount} matches found</Badge> : null}
    >
      {loading ? <Loading label="Searching the vector store and asking the local model…" /> : null}
      {!loading && error ? <ErrorState message={error} onRetry={onRetry} /> : null}
      {!loading && !error && !results ? (
        <EmptyState message="Fill in a ticket and run Check Similarity to see matches." />
      ) : null}

      {!loading && !error && results
        ? results.map((entry) => (
            <div key={entry.ticket_id} className="stack" style={{ marginBottom: 22 }}>
              <div className="row row--between row--wrap">
                <span className="small muted">{entry.ticket_title}</span>
                <Badge tone="default" upper>
                  Quality: {entry.result.quality}
                </Badge>
              </div>

              <p className="small dim mono">Normalized: {entry.result.normalized_text}</p>

              {entry.result.similar_tickets.length === 0 ? (
                <EmptyState message="No similar past tickets stored yet." />
              ) : (
                <div className="grid grid--2">
                  {entry.result.similar_tickets.map((ticket, i) => (
                    <SimilarTicketCard key={`${ticket.title}-${i}`} ticket={ticket} />
                  ))}
                  <AiInsightCard summary={entry.result.ai_summary} />
                </div>
              )}
            </div>
          ))
        : null}
    </Card>
  );
}
