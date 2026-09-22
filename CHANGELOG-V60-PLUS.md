# Aethel V60.1+

## Green upgrades
- 👁️ Real local Vision through Ollama multimodal model (`AETHEL_VISION_MODEL`, default `qwen2.5vl:3b`).
- 🔎 Server-side web search through a server-side DuckDuckGo HTML search adapter; no AI API key.
- 🔒 Stronger Python sandbox using bubblewrap when available: isolated network namespace, read-only system mounts, temporary filesystem, CPU/address-space/file-size/process limits and timeout.
- Chat image attachments are converted to data URLs and sent to the local multimodal model.
- `/api/vision` provides direct image analysis.
- `/api/search` provides server-side search.
- `/api/capabilities` and `/health` expose the new capabilities.

The sandbox is substantially isolated but is not a formal security guarantee; hostile multi-tenant workloads should still use a dedicated VM/container runtime.
