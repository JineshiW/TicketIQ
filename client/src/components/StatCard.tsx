interface StatCardProps {
  label: string;
  value: number | string;
  accent?: boolean;
  icon?: string;
}

export function StatCard({ label, value, accent, icon }: StatCardProps) {
  return (
    <section className="card">
      <div className="stat">
        <div>
          <p className="stat__label">{label}</p>
          <p className={accent ? "stat__value stat__value--accent" : "stat__value"}>{value}</p>
        </div>
        {icon ? <span className="stat__icon">{icon}</span> : null}
      </div>
    </section>
  );
}
