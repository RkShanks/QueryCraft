"""Prompt builder — constructs a normalised prompt for LLM adapters.

T-087: Provider-agnostic prompt construction. Each adapter wraps this in
its model-specific format (system/user/assistant roles).
"""

PROMPT_TEMPLATE = """You are a SQL analytics assistant. Given a database schema and a user question,
generate a single SELECT statement that answers the question.

Rules:
- Read-only SELECT only. Never INSERT/UPDATE/DELETE/DDL.
- Use only tables and columns from the schema.
- Single statement, no semicolons.

Schema:
{schema_yaml}

Question: {question}

SQL:
"""


def build_prompt(question: str, schema_context: str) -> str:
    """Build a normalised prompt string from a question and schema context.

    Args:
        question: The user's natural-language question.
        schema_context: YAML (or plain-text) description of the database schema.

    Returns:
        A fully formatted prompt ready to send to an LLM adapter.
    """
    return PROMPT_TEMPLATE.format(
        schema_yaml=schema_context or "",
        question=question,
    )
