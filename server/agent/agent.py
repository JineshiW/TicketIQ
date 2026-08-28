from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from .agent_tools import check_recurring_patterns


# ============================================================
# OLLAMA MODEL
# ============================================================

llm = ChatOllama(
    model="llama3.2:latest",
    temperature=0,
)


# ============================================================
# RECURRING-PATTERN TOOLS
# ============================================================

tools = [
    check_recurring_patterns,
]


# ============================================================
# RECURRING-PATTERN AGENT
# ============================================================

agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt="""
You are TicketIQ's recurring-pattern analysis agent.

Your responsibility is ONLY to detect recurring patterns
across historical support tickets.

Use the check_recurring_patterns tool when recurring-pattern
analysis is required.

IMPORTANT:

- Do not perform semantic similarity searches.
- Do not search individual repositories.
- Do not normalize tickets.
- Do not call semantic-search tools.
- Do not modify tickets.
- Do not automatically take action based on detected patterns.

Any recurring-pattern finding must be presented as requiring
human review.
""",
)


# ============================================================
# PUBLIC GRAPH
# ============================================================

pattern_review_graph = agent