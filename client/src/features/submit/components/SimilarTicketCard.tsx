import { Badge } from "@/components/Badge";
import { formatPercent, truncate } from "@/lib/format";
import type { SimilarTicketResult } from "@/types";

export function SimilarTicketCard({ ticket }: { ticket: SimilarTicketResult }) {
  return (
    <article className="match-card">
      <div className="row row--between">
        <span className="mono dim">{truncate(ticket.title, 26)}</span>
        <Badge tone="primary">{formatPercent(ticket.similarity_score)} Match</Badge>
      </div>
      <h3 style={{ fontSize: 13 }}>{ticket.title}</h3>
      <p className="small muted">{ticket.resolution || "No resolution recorded."}</p>
    </article>
  );
}
