import { Badge, statusTone } from "@/components/Badge";
import { EmptyState } from "@/components/States";
import { formatDate } from "@/lib/format";
import type { ReviewRecord, ReviewStatus } from "@/types";

interface Props {
  reviews: ReviewRecord[];
  busy: boolean;
  onDecide: (signature: string, status: ReviewStatus) => void;
}

export function ReviewTable({
  reviews,
  busy,
  onDecide,
}: Props) {
  if (reviews.length === 0) {
    return (
      <EmptyState message="No recurring patterns tracked yet. Run a pattern check to populate this list." />
    );
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Repository</th>
          <th>Type</th>
          <th>Summary</th>
          <th className="num">Size</th>
          <th>First seen</th>
          <th>Status</th>
          <th style={{ textAlign: "right" }}>Actions</th>
        </tr>
      </thead>

      <tbody>
        {reviews.map((review) => (
          <tr key={review.signature}>
            {/* Repository */}
            <td className="small mono">
              {review.repository}
            </td>

            {/* Pattern type */}
            <td>
              <Badge upper>
                {review.type}
              </Badge>
            </td>

            {/* Pattern summary */}
            <td>
              {review.summary}
            </td>

            {/* Cluster size */}
            <td className="num">
              {review.size}
            </td>

            {/* First detected */}
            <td className="small dim">
              {formatDate(review.first_seen)}
            </td>

            {/* Review status */}
            <td>
              <Badge
                tone={statusTone(review.status)}
                upper
              >
                {review.status}
              </Badge>
            </td>

            {/* Approve / Reject */}
            <td>
              <div
                className="row"
                style={{
                  justifyContent: "flex-end",
                }}
              >
                <button
                  type="button"
                  className="btn btn--success btn--sm"
                  disabled={
                    busy ||
                    review.status === "approved"
                  }
                  onClick={() =>
                    onDecide(
                      review.signature,
                      "approved",
                    )
                  }
                >
                  Approve
                </button>

                <button
                  type="button"
                  className="btn btn--danger btn--sm"
                  disabled={
                    busy ||
                    review.status === "rejected"
                  }
                  onClick={() =>
                    onDecide(
                      review.signature,
                      "rejected",
                    )
                  }
                >
                  Reject
                </button>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}