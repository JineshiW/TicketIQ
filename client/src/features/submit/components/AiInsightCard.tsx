export function AiInsightCard({ summary }: { summary: string }) {
  return (
    <article className="match-card match-card--insight">
      <span className="small" style={{ letterSpacing: "0.1em", textTransform: "uppercase" }}>
        ✦ AI Insights
      </span>
      <p className="small prewrap">{summary}</p>
    </article>
  );
}
