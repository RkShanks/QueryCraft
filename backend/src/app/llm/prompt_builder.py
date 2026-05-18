"""Prompt builder — constructs a normalised prompt for LLM adapters.

T-087: Provider-agnostic prompt construction. Each adapter wraps this in
its model-specific format (system/user/assistant roles).
T-432: Added target_dialect parameter for dialect-aware SQL generation.
"""

PROMPT_TEMPLATE = """You are a SQL analytics assistant. Given a database schema and a user question,
generate a single SELECT statement that answers the question.

Rules:
- Read-only SELECT only. Never INSERT/UPDATE/DELETE/DDL.
- Use only tables and columns from the schema.
- Single statement, no semicolons.
{dialect_instruction}
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

DIALECT_INSTRUCTION_TEMPLATE = "- Generate SQL in {dialect} dialect. Use {dialect}-specific syntax and conventions.\n"


def build_prompt(
    question: str,
    schema_context: str,
    conversation_history: list[dict] | None = None,
    target_dialect: str | None = None,
) -> str:
    """Build a normalised prompt string from a question and schema context.

    Args:
        question: The user's natural-language question.
        schema_context: YAML (or plain-text) description of the database schema.
        conversation_history: Optional list of prior Q&A dicts with 'question' and 'sql' keys.
        target_dialect: Optional SQL dialect (e.g. "postgresql", "mysql", "tsql").
            When provided, includes TARGET_DIALECT instruction in the prompt.

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

    dialect_instruction = ""
    if target_dialect:
        dialect_instruction = f"TARGET_DIALECT: {target_dialect}\n" + DIALECT_INSTRUCTION_TEMPLATE.format(dialect=target_dialect)

    return PROMPT_TEMPLATE.format(
        schema_yaml=schema_context or "",
        conversation_history=history_block,
        question=question,
        dialect_instruction=dialect_instruction,
    )
