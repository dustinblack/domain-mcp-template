# AI Agent Guidelines

This file provides context and rules for AI Agents (like Gemini, Claude, Cursor) working on this codebase.

## 🧠 Project Context

**This is a Domain MCP (Model Context Protocol) Server.**
It acts as a translation layer between an AI Client (User) and a raw Data Source.

*   **Primary Goal:** Allow users to ask domain-specific natural language questions ("How does network performance compare to the last week?") and get structured data back. The idea is to encapsulate domain expertise into this MCP server so that the user can communicate with the LLM using the same terminology and "shortcuts" they may use with their peers.
*   **Key Tool:** `get_key_metrics`. The agent orchestrates fetching data and applying domain logic.

## 🛠️ Development Rules

1.  **Follow the Plan:** If `IMPLEMENTATION_PLAN.md` exists, it is your primary directive. Keep it updated.
2.  **Shared Utilities:** Use `src/domain/utils/` for timestamp parsing, validation, and statistics. Do not reinvent the wheel.
3.  **Tests:** Run tests (`pytest`) after every significant change.
4.  **Conventions:**
    *   Python: `snake_case`
    *   JSON/API: `camelCase` (Use Pydantic aliases to bridge them).

## 🔌 Adapters

The project uses **Adapters** to talk to data sources.
*   `src/adapters/elasticsearch.py`: Connection to Elasticsearch.
*   `src/adapters/horreum.py`: Connection to Horreum.

**Do not modify the `mcp_bridge.py` core logic unless necessary.** It handles the stdio communication with the upstream source.

## 📦 Plugins

Domain logic lives in `src/domain/plugins/`.
*   A Plugin defines `extract(json_body, ...)` -> `List[MetricPoint]`.
*   Keep plugins pure. They should transform data, not fetch it.
*   **Start here:** `src/domain/plugins/plugin_scaffold.py` - Copy and fill in TODOs for your domain.
*   **Reference:** `docs/plugins/plugin-template.py` - Complete examples with best practices.

## 📝 Commit Messages

Format: `Type: Description (AI-assisted-by: ModelName)`
Example: `Feat: Add payment_gateway dimension to extraction logic (AI-assisted-by: Gemini)`

---

## 📚 Documentation Navigation Guide (For AI Agents)

When helping users, reference the right documentation for each task:

### Always Start Here
- **`IMPLEMENTATION_PLAN.md`** - Your primary directive. Follow this workflow for all implementations.

### Phase-Specific Deep Dives
- **Phase 1-2 (Setup):** Use `README.md` sections on Connection Mode, Troubleshooting
- **Phase 3.1 (Glossary):** Use `IMPLEMENTATION_PLAN.md` Phase 3.1.4 for assessment scoring
- **Phase 3.4 (Test Fixtures):** Use `tests/fixtures/template/README.md` for scenario requirements
- **Phase 3.5 (Custom Filters):** Use `IMPLEMENTATION_PLAN.md` Phase 3.5.3 for step-by-step walkthrough
- **Phase 5 (Query Testing):** 
  - Setup: Use `docs/testing-with-claude-desktop.md`
  - Debugging: Use `IMPLEMENTATION_PLAN.md` Phase 5.3.3 (decision tree)
  - Documentation: Use `docs/example_queries_template.md`

### Reference Materials
- **Concepts:** `README.md` "Key Concepts" section (plugins, glossary, aggregations)
- **Examples:** `src/domain/examples/` and `docs/EXAMPLE_DOMAIN.md`
- **End-to-End Scenario:** `docs/EXAMPLE_SCENARIO.md` (realistic implementation walkthrough)
- **Code Templates:** `src/domain/plugins/plugin_scaffold.py`
- **Source MCP Contract:** `docs/SOURCE_MCP_QUICKSTART.md`

### What NOT to Reference During Implementation
- ❌ Historical/legacy documentation files (if any exist in the repo)

### Quick Decision Tree
```
User asks: "How do I start?" 
→ IMPLEMENTATION_PLAN.md Phase 1

User asks: "What does the implementation process look like?"
→ docs/EXAMPLE_SCENARIO.md (full walkthrough)

User asks: "How do I create test fixtures?"
→ tests/fixtures/template/README.md

User asks: "How do I add a filter?"
→ IMPLEMENTATION_PLAN.md Phase 3.5.3

User asks: "My query doesn't work"
→ IMPLEMENTATION_PLAN.md Phase 5.3.3

User asks: "How do I connect to Claude?"
→ docs/testing-with-claude-desktop.md

User asks: "What's a plugin?"
→ README.md "Key Concepts" section
```