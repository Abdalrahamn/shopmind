# Security tests on the tools (Phase 5)

Each row sends a hostile call straight to a tool, as if the model had been fooled. Pass = the tool refused **and** the database is byte-for-byte unchanged. No LLM is involved.

| Test | The attack | Tool reply | Database unchanged | Result |
|---|---|---|---|---|
| Customer runs SQL | A customer (or a fooled model) calls the SQL tool | Refused: only staff can query the database. For a customer's own orders use get_my_orders. | yes | ✅ pass |
| DELETE | Delete all orders | Refused: only a single SELECT statement is allowed. | yes | ✅ pass |
| UPDATE | Change a price | Refused: only a single SELECT statement is allowed. | yes | ✅ pass |
| DROP TABLE | Destroy a table | Refused: only a single SELECT statement is allowed. | yes | ✅ pass |
| Two statements | Hide a DROP after a SELECT | Refused: only a single SELECT statement is allowed. | yes | ✅ pass |
| Write hidden in WITH | A statement that starts like a SELECT but deletes | SQL error: attempt to write a readonly database. Fix the query and try again. | yes | ✅ pass |
| PRAGMA | Change database settings | Refused: only a single SELECT statement is allowed. | yes | ✅ pass |
| ATTACH | Open another database file | Refused: only a single SELECT statement is allowed. | yes | ✅ pass |
| Comment trick | Hide the real statement behind a comment | Refused: only a single SELECT statement is allowed. | yes | ✅ pass |
| Cancel someone else's order | Customer 20 cancels order 1073 (customer 121) | Refused: order 1073 does not belong to this customer. | yes | ✅ pass |
| Cancel a delivered order | Customer 20 cancels their delivered order 1223 | Order 1223 cannot be cancelled because its status is 'delivered'. Shipped orders must be r | yes | ✅ pass |
| Guest lists orders | Nobody is signed in | No customer is signed in, so there are no orders to show. | yes | ✅ pass |
| SQL injection in stock check | Product name carrying SQL | {"error": "No product matches 'x'; DROP TABLE products; --'."} | yes | ✅ pass |
| SQL injection, OR 1=1 | Try to list every product through the stock tool | {"error": "No product matches '' OR '1'='1'."} | yes | ✅ pass |

**14/14 passed.**
