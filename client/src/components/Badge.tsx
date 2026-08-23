import type { ReactNode } from "react";

type Tone = "default" | "primary" | "success" | "warning" | "danger";

export function Badge({
  children,
  tone = "default",
  upper,
}: {
  children: ReactNode;
  tone?: Tone;
  upper?: boolean;
}) {
  const cls = ["badge", tone !== "default" ? `badge--${tone}` : "", upper ? "badge--upper" : ""]
    .filter(Boolean)
    .join(" ");
  return <span className={cls}>{children}</span>;
}

export function statusTone(status: string): Tone {
  if (status === "approved") return "success";
  if (status === "rejected") return "danger";
  return "warning";
}
