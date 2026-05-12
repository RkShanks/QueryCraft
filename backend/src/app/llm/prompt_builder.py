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
{conversation_history}
Question: {question}

SQL:
"""

HISTORY_TEMPLATE = """
Conversation history:
{history}
"""


def build_prompt(
    question: str,
    schema_context: str,
    conversation_history: list[dict] | None = None,
) -> str:
    """Build a normalised prompt string from a question and schema context.

    Args:
        question: The user's natural-language question.
        schema_context: YAML (or plain-text) description of the database schema.
        conversation_history: Optional list of prior Q&A dicts with 'question' and 'sql' keys.

    Returns:
        A fully formatted prompt ready to send to an LLM adapter.
    """
    history_block = ""
    if conversation_history:
        history_lines = []
        for item in conversation_history:
            history_lines.append(f"Q: {item.get('question', '')}")
            history_lines.append(f"SQL: {item.get('sql', '')}")
        history_block = HISTORY_TEMPLATE.format(history="\n".join(history_lines))

    return PROMPT_TEMPLATE.format(
        schema_yaml=schema_context or "",
        conversation_history=history_block,
        question=question,
    )
