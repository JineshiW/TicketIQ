import type { DraftTicket } from "../useTicketSubmission";

interface Props {
  draft: DraftTicket;
  index: number;
  canRemove: boolean;
  onChange: (key: string, patch: Partial<DraftTicket>) => void;
  onRemove: (key: string) => void;
}

export function TicketForm({ draft, index, canRemove, onChange, onRemove }: Props) {
  return (
    <fieldset
      style={{
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-sm)",
        padding: 14,
        margin: 0,
      }}
    >
      <legend className="small dim" style={{ padding: "0 6px" }}>
        Ticket {index + 1}
      </legend>

      <div className="field">
        <label className="field__label" htmlFor={`${draft.key}-id`}>
          Ticket ID (optional)
        </label>
        <input
          id={`${draft.key}-id`}
          className="input"
          placeholder="e.g. INF-2011"
          value={draft.id}
          onChange={(e) => onChange(draft.key, { id: e.target.value })}
        />
      </div>

      <div className="field">
        <label className="field__label" htmlFor={`${draft.key}-title`}>
          Title
        </label>
        <input
          id={`${draft.key}-title`}
          className="input"
          placeholder="Enter ticket title..."
          value={draft.title}
          onChange={(e) => onChange(draft.key, { title: e.target.value })}
        />
      </div>

      <div className="field">
        <label className="field__label" htmlFor={`${draft.key}-desc`}>
          Description
        </label>
        <textarea
          id={`${draft.key}-desc`}
          className="textarea"
          placeholder="Detailed description of the issue..."
          value={draft.description}
          onChange={(e) => onChange(draft.key, { description: e.target.value })}
        />
      </div>

      <div className="field">
        <label className="field__label" htmlFor={`${draft.key}-res`}>
          Resolution (only needed when storing a solved ticket)
        </label>
        <input
          id={`${draft.key}-res`}
          className="input"
          placeholder="How it was fixed..."
          value={draft.resolution}
          onChange={(e) => onChange(draft.key, { resolution: e.target.value })}
        />
      </div>

      {canRemove ? (
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={() => onRemove(draft.key)}
        >
          Remove ticket
        </button>
      ) : null}
    </fieldset>
  );
}
