# TicketIQ — React Client

TicketIQ is an AI-assisted ticket analysis system designed to help teams understand, organise, and identify recurring patterns in support or issue tickets.

This repository contains the **React + TypeScript frontend** for TicketIQ. It communicates with the TicketIQ FastAPI backend, which handles ticket processing, similarity checking, pattern detection, and AI-assisted analysis.

## What TicketIQ Does

TicketIQ helps users move beyond simply reading tickets one by one.

The system can:

- Submit and store individual or multiple tickets
- Check whether a new ticket is similar to existing tickets
- Identify recurring patterns across stored tickets
- Group related tickets into meaningful patterns
- Present detected patterns through visualisations and statistics
- Allow a human user to review detected patterns
- Approve or reject identified patterns
- Use an AI agent to perform an additional pattern check
- Continue the analysis after a human decision

The aim is to help support and business teams identify repeated issues faster and make better use of historical ticket information.

---

## Technology

### Frontend

- React
- TypeScript
- Vite
- CSS
- SVG-based charts

### Backend

- FastAPI
- Python

### AI & Data Processing

- Qdrant — stores and searches ticket information
- Sentence Transformers — converts tickets into searchable representations
- Ollama — provides local AI processing
- LangGraph — manages the AI agent workflow

The frontend runs separately from the backend but communicates with it through the available API endpoints.

---

## Running the Project

### Requirements

Before running the frontend, make sure you have:

- Node.js 18 or newer
- The TicketIQ FastAPI backend running locally
- The required AI and database services configured for the backend

### 1. Install dependencies

```bash
npm install