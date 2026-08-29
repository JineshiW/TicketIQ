# TicketIQ — React Client

TicketIQ is an AI-assisted ticket analysis system designed to help teams understand, organise, and identify recurring patterns in support or issue tickets.

This repository contains the **React + TypeScript frontend** for TicketIQ. It communicates with the TicketIQ FastAPI backend, which handles ticket processing, similarity checking, pattern detection, and AI-assisted analysis.

## What TicketIQ Does

TicketIQ helps users move beyond simply reading tickets one by one.

The system can:

* Submit and store individual or multiple tickets
* Check whether a new ticket is similar to existing tickets
* Identify recurring patterns across stored tickets
* Group related tickets into meaningful patterns
* Present detected patterns through visualisations and statistics
* Allow a human user to review detected patterns
* Approve or reject identified patterns
* Use an AI agent to perform an additional pattern check
* Continue the analysis after a human decision

The aim is to help support and business teams identify repeated issues faster and make better use of historical ticket information.

---

## Technology

### Frontend

* React
* TypeScript
* Vite
* CSS
* SVG-based charts

### Backend

* FastAPI
* Python

### AI & Data Processing

* Qdrant — stores and searches ticket information
* Sentence Transformers — converts tickets into searchable representations
* Ollama — provides local AI processing
* LangGraph — manages the AI agent workflow

The frontend runs separately from the backend but communicates with it through the available API endpoints.

---

## Running the Project

### Requirements

Before running the frontend, make sure you have:

* Node.js 18 or newer
* The TicketIQ FastAPI backend running locally
* The required AI and database services configured for the backend

### 1. Install dependencies

```bash
npm install
```

### 2. Run the frontend locally

After installing the dependencies, start the React development server:

```bash
npm run dev
```

The terminal will display the local address where the frontend is running, normally:

```text
http://localhost:5173
```

Open this address in your browser to access the TicketIQ frontend.

### 3. Start the TicketIQ backend

Open a **second terminal window** and navigate to the TicketIQ backend directory.

Create and activate the Python virtual environment if it has not already been created:

```bash
python -m venv venv
```

Activate the virtual environment.

**Windows:**

```bash
venv\Scripts\activate
```

**macOS / Linux:**

```bash
source venv/bin/activate
```

Install the backend dependencies:

```bash
pip install -r requirements.txt
```

Start the FastAPI server:

```bash
uvicorn main:app --reload
```

The backend will normally be available at:

```text
http://127.0.0.1:8000
```

### 4. Start the required services

Make sure the services required by the backend are running before testing the full application.

These include:

```bash
qdrant
```

and:

```bash
ollama serve
```

If the required Ollama model has not already been downloaded, pull it using:

```bash
ollama pull llama3
```

### 5. Run TicketIQ

Once the frontend, FastAPI backend, Qdrant, and Ollama services are running:

1. Open the frontend address shown by Vite.
2. Submit a ticket through the TicketIQ interface.
3. Use the similarity feature to compare it with existing tickets.
4. Open the recurring-pattern analysis section.
5. Review the detected patterns and their supporting tickets.
6. Approve or reject patterns where required.
7. Use the AI-assisted pattern check to continue the analysis.

The frontend and backend must both be running for the complete TicketIQ functionality to work correctly.
