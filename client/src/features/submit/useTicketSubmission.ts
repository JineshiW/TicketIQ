import { useCallback, useState } from "react";
import { ticketsApi } from "@/api";
import { useAsyncAction } from "@/hooks/useAsync";
import type { BatchSimilarResult, Ticket } from "@/types";

export interface DraftTicket {
  key: string;
  id: string;
  title: string;
  description: string;
  resolution: string;
}

let counter = 0;
export function emptyDraft(): DraftTicket {
  counter += 1;
  return { key: `draft-${counter}`, id: "", title: "", description: "", resolution: "" };
}

function toTicket(draft: DraftTicket, index: number): Ticket {
  return {
    id: draft.id.trim() || `TMP-${Date.now()}-${index}`,
    title: draft.title.trim(),
    description: draft.description.trim(),
    resolution: draft.resolution.trim(),
  };
}

/**
 * Owns the multi-ticket draft state plus the two backend calls it can make:
 * similarity check (single or batch) and storing tickets in the vector DB.
 */
export function useTicketSubmission() {
  const [drafts, setDrafts] = useState<DraftTicket[]>([emptyDraft()]);

  const similarity = useAsyncAction(async (tickets: Ticket[]): Promise<BatchSimilarResult[]> => {
    if (tickets.length === 1) {
      const result = await ticketsApi.findSimilar(tickets[0]);
      return [{ ticket_id: tickets[0].id, ticket_title: tickets[0].title, result }];
    }
    const response = await ticketsApi.findSimilarBatch(tickets);
    return response.results;
  });

  const save = useAsyncAction(async (tickets: Ticket[]) =>
    tickets.length === 1 ? ticketsApi.addTicket(tickets[0]) : ticketsApi.addTicketsBatch(tickets),
  );

  const updateDraft = useCallback((key: string, patch: Partial<DraftTicket>) => {
    setDrafts((current) => current.map((d) => (d.key === key ? { ...d, ...patch } : d)));
  }, []);

  const addDraft = useCallback(() => setDrafts((c) => [...c, emptyDraft()]), []);

  const removeDraft = useCallback(
    (key: string) => setDrafts((c) => (c.length === 1 ? c : c.filter((d) => d.key !== key))),
    [],
  );

  const isValid = drafts.every((d) => d.title.trim() && d.description.trim());

  const checkSimilarity = useCallback(
    () => similarity.run(drafts.map(toTicket)),
    [drafts, similarity],
  );

  const storeTickets = useCallback(() => save.run(drafts.map(toTicket)), [drafts, save]);

  return {
    drafts,
    isValid,
    addDraft,
    removeDraft,
    updateDraft,
    similarity,
    save,
    checkSimilarity,
    storeTickets,
  };
}
