import { Badge } from "@/components/Badge";
import type { AlgorithmComparison as Comparison } from "@/types";

interface Props {
  comparison: Comparison;
  best: string | null;
}

export function AlgorithmComparisonPanel({ comparison, best }: Props) {
  const rows = Object.entries(comparison ?? {});
  if (rows.length === 0) return null;

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Algorithm</th>
          <th className="num">Clusters</th>
          <th className="num">Silhouette</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {rows.map(([name, metrics]) => (
          <tr key={name}>
            <td style={{ textTransform: "uppercase" }}>{name}</td>
            <td className="num">{metrics.n_clusters}</td>
            <td className="num">{Number(metrics.silhouette).toFixed(3)}</td>
            <td>{name === best ? <Badge tone="primary">Selected</Badge> : null}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
