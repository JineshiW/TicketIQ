import type { ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  flush?: boolean;
}

export function Card({ title, subtitle, action, children, flush }: CardProps) {
  if (!title) {
    return <section className={flush ? "card card--flush" : "card"}>{children}</section>;
  }
  return (
    <section className="card card--flush">
      <div className="card__header">
        <div>
          <h2 className="card__title">{title}</h2>
          {subtitle ? <p className="card__subtitle">{subtitle}</p> : null}
        </div>
        {action}
      </div>
      {flush ? children : <div className="card__body">{children}</div>}
    </section>
  );
}
