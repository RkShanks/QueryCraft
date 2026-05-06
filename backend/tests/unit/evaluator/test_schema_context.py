"""T-098 — SchemaContext model tests."""

from app.evaluator.schema_context import Column, SchemaContext, Table


def test_empty_schema_context():
    ctx = SchemaContext()
    assert ctx.tables == []
    assert ctx.find_table("users") is None
    assert ctx.find_column("users", "id") is None


def test_find_table_returns_table():
    ctx = SchemaContext(
        tables=[Table(name="users", columns=[Column(name="id", type="integer")])]
    )
    table = ctx.find_table("users")
    assert table is not None
    assert table.name == "users"


def test_find_table_case_insensitive():
    """Postgres folds unquoted identifiers to lowercase."""
    ctx = SchemaContext(
        tables=[Table(name="users", columns=[Column(name="id", type="integer")])]
    )
    assert ctx.find_table("USERS") is not None
    assert ctx.find_table("Users") is not None


def test_find_column_returns_column():
    ctx = SchemaContext(
        tables=[Table(name="users", columns=[Column(name="id", type="integer")])]
    )
    col = ctx.find_column("users", "id")
    assert col is not None
    assert col.name == "id"
    assert col.type == "integer"


def test_find_column_case_insensitive():
    ctx = SchemaContext(
        tables=[Table(name="users", columns=[Column(name="id", type="integer")])]
    )
    assert ctx.find_column("USERS", "ID") is not None
    assert ctx.find_column("users", "Id") is not None


def test_roundtrip_serialize_deserialize():
    ctx = SchemaContext(
        tables=[
            Table(
                name="users",
                columns=[
                    Column(name="id", type="integer", primary_key=True),
                    Column(name="email", type="text"),
                ],
            )
        ]
    )
    dumped = ctx.model_dump()
    restored = SchemaContext.model_validate(dumped)
    assert restored.find_table("users") is not None
    assert restored.find_column("users", "id") is not None
    assert restored.find_column("users", "id").primary_key is True
