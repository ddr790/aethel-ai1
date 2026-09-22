# Aethel V64 — Stable LLM + Apple UI

## Correções principais
- Ollama pode iniciar antes do download do modelo; o backend reconsulta `/api/tags` e passa a reconhecer o modelo sem reiniciar.
- `/health`, `/api/model` e `/api/llm/status` distinguem servidor Ollama online de modelo realmente instalado.
- O chat mostra erro técnico útil em vez de esconder a causa atrás de uma mensagem genérica.
- A interface de entrada é Apple-inspired: tipografia limpa, superfícies translúcidas, hierarquia discreta e responsividade mobile/tablet.
- Abrir Aethel permanece na mesma página; não cria uma aba externa.
- Render continua usando `0.0.0.0:$PORT` e health check barato em `/health`.

## Importante
Na primeira inicialização, o site pode ficar online enquanto o Ollama ainda baixa `qwen2.5:3b-instruct-q4_K_M`. O chat geral fica pronto assim que o modelo aparecer em `/api/llm/status` como `ready: true`.
