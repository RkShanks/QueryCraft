"""T-087 — Prompt builder (test + impl combined). T-432 — dialect parameterization."""

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


class TestPromptBuilderDialectParameterization:
    """T-432: Verify target_dialect is included in prompt."""

    def test_includes_target_dialect_instruction(self):
        """Prompt includes TARGET_DIALECT instruction when dialect is provided."""
        prompt = build_prompt(
            "Show all users",
            "users:\n  - id: integer",
            target_dialect="postgresql",
        )
        assert "TARGET_DIALECT:" in prompt
        assert "postgresql" in prompt

    def test_mysql_dialect_in_prompt(self):
        """MySQL dialect instruction appears in prompt."""
        prompt = build_prompt(
            "Show all orders",
            "orders:\n  - id: integer",
            target_dialect="mysql",
        )
        assert "TARGET_DIALECT: mysql" in prompt

    def test_tsql_dialect_in_prompt(self):
        """T-SQL dialect instruction appears in prompt."""
        prompt = build_prompt(
            "Show all records",
            "records:\n  - id: integer",
            target_dialect="tsql",
        )
        assert "TARGET_DIALECT: tsql" in prompt

    def test_no_dialect_when_none(self):
        """TARGET_DIALECT instruction is absent when dialect is None."""
        prompt = build_prompt(
            "Show all users",
            "users:\n  - id: integer",
            target_dialect=None,
        )
        assert "TARGET_DIALECT:" not in prompt

    def test_backward_compatible_no_dialect(self):
        """build_prompt without target_dialect arg works (backward compatible)."""
        prompt = build_prompt("Show users", "users:\n  - id: integer")
        assert "TARGET_DIALECT:" not in prompt
        assert "Show users" in prompt
