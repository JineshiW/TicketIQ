import json
import os

_TERMS_PATH = os.path.join(os.path.dirname(__file__), "domain_terms.json")

def load_domain_terms() -> list[str]:
    """Loads the domain-specific vector of terms that must be preserved
    during normalization, so the LLM doesn't genericize important
    technical vocabulary while cleaning up ticket wording."""
    try:
        with open(_TERMS_PATH, "r") as f:
            data = json.load(f)
        return data.get("domain_terms", [])
    except FileNotFoundError:
        return []

def vector_prompt_hint() -> str:
    """Formats the term vector into a short string to inject into prompts."""
    terms = load_domain_terms()
    if not terms:
        return ""
    return ", ".join(terms)