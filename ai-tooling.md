# AI Tooling Documentation

## Overview

This project was built by Zeliha Ungun and Fahrettin Ungun as their Quantic MSAIE project. **Claude Code** (Anthropic's CLI AI agent, `claude-sonnet-4-6`) was used as an AI coding assistant throughout development — similar to how developers use GitHub Copilot — to accelerate implementation while all design decisions, integration choices, and validation remained with the team.

---

## Tools Used

### Claude Code (AI Coding Assistant)
- **Version**: claude-sonnet-4-6 via Claude Code CLI
- **Role**: Code drafting assistant, not primary author
- **How we used it**:
  - We defined the architecture and requirements; Claude Code helped translate them into code
  - We reviewed, tested, and revised all generated code before integration
  - We provided the policy content direction; Claude Code helped format it as structured documents
  - We designed the evaluation rubric; Claude Code helped implement the scoring logic
  - All final decisions on design, tooling, and deployment were made by the team

### Google Gemini API (Runtime LLM)
- **Model**: `gemini-flash-latest` (routes to Gemini 3.6 Flash on our API key)
- **Usage**: Agent reasoning, tool selection, response synthesis at runtime
- **Why Gemini**: OpenAI-compatible API endpoint; paid tier with 15 RPM / 1M TPM / 1500 RPD limits

---

## What Worked Well

1. **Rapid prototyping**: Using Claude Code to draft boilerplate (FastAPI routes, MCP tool schemas, pytest fixtures) let us focus on the harder architectural decisions — RAG chunking strategy, confirmation gate design, evaluation metric selection.

2. **MCP server structure**: We designed the 8-tool schema and confirmation gate pattern (`requester_confirmed` flag); Claude Code helped implement the JSON Schema definitions consistently.

3. **Test coverage**: We specified what needed testing (action safety, tool discovery, smoke tests); Claude Code helped write the pytest cases to cover those requirements.

4. **Debugging**: Claude Code was especially useful for diagnosing runtime errors like the `mcp` package naming conflict and the numpy version constraint.

5. **Gemini thought_signature handling**: Gemini thinking models embed an opaque `thought_signature` per tool call in the API response. This must be echoed back verbatim in the next request or the API returns a 400 error. We diagnosed this by inspecting raw HTTP responses and switched from the OpenAI Python client (which strips unknown fields) to direct `httpx` calls so the `extra_content` field is round-tripped exactly as received.

---

## What Was Challenging

1. **MCP SDK version compatibility**: The `mcp` Python SDK changed its API between v1.0 and v1.2. We had to identify the correct API version and guide Claude Code to generate compatible code.

2. **Package naming conflict**: A local `mcp/` directory shadowed the installed `mcp` PyPI package. We diagnosed this from the error logs and directed Claude Code to rename the directory to `mcp_server/`.

3. **Deployment platform decisions**: We evaluated HF Spaces (Docker tier was paid), Koyeb (being acquired), and Railway (free starter credit, Docker support). These decisions required our own research.

4. **fastembed vs sentence-transformers**: We chose `fastembed` over `sentence-transformers` to avoid the ~1GB PyTorch dependency. Claude Code implemented the switch after we made this decision.

5. **Evaluation design**: The groundedness and citation accuracy metrics required our judgment about what "correct" looks like for HR policy answers. Claude Code implemented the scoring logic we specified.

6. **Gemini `thought_signature` in multi-turn tool use**: The most significant integration challenge. Gemini 3.x thinking models return an opaque `thought_signature` blob with each tool call that must be sent back in the next request. The OpenAI Python client strips non-standard fields, so the signature was silently lost, causing 400 errors on every multi-turn chat. We resolved this by calling the Gemini REST endpoint directly with `httpx`, preserving the raw `extra_content` structure in both directions. We also hit a `google-genai` ↔ `mcp==1.2.0` pydantic conflict when attempting the native client; removing `google-genai` entirely and using `httpx` resolved both issues.

7. **Package dependency conflicts**: `google-genai>=1.0.0` installs pydantic 2.10+, which removed `eval_type_backport` — an internal API that `mcp==1.2.0` depends on. This crashed the deployment. We resolved it by removing `google-genai` from requirements entirely and calling the Gemini OpenAI-compatible REST endpoint directly.

---

## Commit Attribution

Commits are split between Zeliha and Fahrettin to reflect their respective contributions:
- **Zeliha**: Corpus documents, MCP server, web app + UI, documentation
- **Fahrettin**: RAG pipeline, agent orchestrator, CI/CD + deployment, evaluation

---

## Academic Integrity Note

All code was reviewed, tested, and understood by both team members before submission. The team is responsible for the correctness, security, and design decisions in the submitted work. Claude Code assisted with implementation speed, not with understanding or decision-making.
