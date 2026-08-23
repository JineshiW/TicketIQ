import { request } from "./client";
import type {
  AddTicketResponse,
  BatchSimilarResponse,
  SimilarTicketsResponse,
  Ticket,
} from "@/types";

/** POST /tickets — store a single resolved ticket in the vector DB. */
export function addTicket(ticket: Ticket) {
  return request<AddTicketResponse>("/tickets", { method: "POST", body: ticket });
}

/** POST /tickets/batch — store many tickets in one call. */
export function addTicketsBatch(tickets: Ticket[]) {
  return request<AddTicketResponse>("/tickets/batch", { method: "POST", body: tickets });
}

/** POST /tickets/similar — similarity search + AI summary for one ticket. */
export function findSimilar(ticket: Ticket) {
  return request<SimilarTicketsResponse>("/tickets/similar", {
    method: "POST",
    body: ticket,
  });
}

/** POST /tickets/similar/batch — similarity search for several tickets at once. */
export function findSimilarBatch(tickets: Ticket[]) {
  return request<BatchSimilarResponse>("/tickets/similar/batch", {
    method: "POST",
    body: tickets,
  });
}
