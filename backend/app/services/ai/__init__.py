"""AI assistants (Blueprint section J).

- Seven agents: research, product, marketing, analytics, customer, inventory, seo.
- Providers: "rules" (built in, free, default), "ollama" (local, free), "api" (OpenAI-compatible).
- Every output line carries a label: FACT, ASSUMPTION, ESTIMATE or HYPOTHESIS.
- Nothing an assistant writes is ever applied automatically: it is a draft until a person
  approves it, and approval only records the decision; it never changes prices, stock or orders.
"""
