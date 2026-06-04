"""PolicyEnforcementService — central policy enforcement for query pipeline.

T-699: Schema filtering. Applies RoleConnectionPolicy.allowed_tables to a
SchemaContext, returning a new SchemaContext that contains only role-permitted
tables and columns. Used to restrict the LLM prompt to role-permitted schema
per S-006 / FR-128 / FR-129 / SC-050.
"""

from __future__ import annotations

from app.evaluator.schema_context import Column, SchemaContext, Table


class PolicyEnforcementService:
    """Stateless service that applies role policy to evaluator schema inputs.

    The service is intentionally a plain class with no constructor arguments
    so it can be instantiated freely and called from any query pipeline stage.
    """

    @staticmethod
    def filter_schema(
        schema: SchemaContext,
        allowed_tables: list[dict] | None,
    ) -> SchemaContext:
        """Return a new SchemaContext containing only role-allowed tables/columns.

        Args:
            schema: The full SchemaContext (e.g., from connection introspection).
            allowed_tables: Role policy in the shape
                ``[{"table": "t", "columns": ["c1", "c2"]}, ...]``. ``None`` or
                an empty list is treated as a deny-all policy (fail-closed).

        Returns:
            A new ``SchemaContext``. The input is never mutated. Tables and
            columns not present in the policy are silently excluded.
            ``schema_name`` and column metadata are preserved verbatim.
        """
        if not allowed_tables:
            return SchemaContext(tables=[])

        # Index policy by lowercased table name for case-insensitive lookup.
        # Unknown policy entries (tables/columns not in schema) are dropped
        # silently — no leak, no exception.
        policy_by_table: dict[str, set[str]] = {}
        for entry in allowed_tables:
            table_name = entry.get("table")
            if not isinstance(table_name, str) or not table_name:
                continue
            columns = entry.get("columns") or []
            if not isinstance(columns, list):
                continue
            normalized_cols = {c.lower() for c in columns if isinstance(c, str)}
            policy_by_table[table_name.lower()] = normalized_cols

        filtered_tables: list[Table] = []
        for table in schema.tables:
            allowed_cols = policy_by_table.get(table.name.lower())
            if allowed_cols is None:
                continue

            kept_columns: list[Column] = [
                column
                for column in table.columns
                if column.name.lower() in allowed_cols
            ]
            filtered_tables.append(
                Table(
                    name=table.name,
                    schema_name=table.schema_name,
                    columns=kept_columns,
                )
            )

        return SchemaContext(tables=filtered_tables)
