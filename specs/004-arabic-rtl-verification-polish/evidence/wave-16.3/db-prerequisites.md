# Wave 16.3 — Database Prerequisites Verification

This document verifies that all three source database containers (PostgreSQL, MySQL, and Microsoft SQL Server) are running, healthy, and successfully registered and introspected in the QueryCraft Admin UI.

## Database Containers Status

All three database containers are running healthy on the QueryCraft Docker network:

| Container Name | Port | Database Name | Username | Health Status |
|---|---|---|---|---|
| `postgres-source` | 5432 | `source_analytics` | `pagila_user` | Healthy |
| `mysql-source` | 3306 | `sakila` | `sakila_user` | Healthy |
| `mssql-source` | 1433 | `AdventureWorksLT` | `adventureworks_user` | Healthy |

## Admin UI Verification

All connections have been successfully verified in the Admin UI at `http://localhost:3000/admin/connections`:

- **PostgreSQL Pagila**: Active/Healthy, Schema Introspection Status: `Success`
- **MySQL Sakila**: Active/Healthy, Schema Introspection Status: `Success`
- **MSSQL AdventureWorks**: Active/Healthy, Schema Introspection Status: `Success`

![Admin Connections List](connections_list.png)
