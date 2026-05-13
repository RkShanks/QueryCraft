"""T-087 — Prompt builder (test + impl combined)."""

from app.llm.prompt_builder import build_prompt


def test_includes_question_text():
    """The generated prompt contains the user question."""
    prompt = build_prompt("How many users signed up last week?", "users:\n  - id")
    assert "How many users signed up last week?" in prompt


def test_includes_schema_yaml():
    """The generated prompt contains the schema YAML."""
    schema = "users:\n  - id: integer\n  - email: string"
    prompt = build_prompt("List all users", schema)
    assert schema in prompt


def test_empty_schema_produces_valid_prompt():
    """An empty schema string still produces a well-formed prompt."""
    prompt = build_prompt("What is 1 + 1?", "")
    assert "Schema:" in prompt
    assert "SQL:" in prompt


def test_special_characters_escaped():
    """Questions with quotes and newlines are rendered safely."""
    question = 'What\'s the "total" cost?\nAnd tax?'
    prompt = build_prompt(question, "orders:\n  - total: decimal")
    assert 'What\'s the "total" cost?\nAnd tax?' in prompt
