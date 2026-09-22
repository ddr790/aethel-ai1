# Aethel V63 — Render Stable Fix

The previous container blocked Render startup while `ollama pull` downloaded the main and vision models. That can cause the web service to be killed before the health check succeeds.

This version starts the HTTP server immediately after Ollama becomes reachable. Model downloads happen in the background on the persistent `/data` disk.

## Render
- Runtime: Docker
- Health check: `/health`
- Persistent disk: `/data` (20 GB recommended minimum for the configured models)
- Main model: `qwen2.5:3b-instruct-q4_K_M`
- Vision model: `qwen2.5vl:3b`

The site can become healthy before the models finish downloading. Until a model is available, general LLM responses may report that the local model is still being prepared.
