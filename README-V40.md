# Aethel V40 — Assistente realmente operacional

V40 transforma o Aethel de uma interface + backend em uma plataforma local com:
- LLM local via Ollama, inicializado automaticamente;
- streaming real por SSE;
- memória persistente em SQLite;
- ferramenta de execução controlada de Python com timeout e bloqueios básicos;
- Agent ponta a ponta para planejar, criar arquivos, testar Python e gerar ZIP;
- workspace persistente em `/data` quando usado com disco persistente;
- Docker + Render.

## Modelo padrão
`qwen2.5:3b-instruct-q4_K_M`.
Altere `AETHEL_OLLAMA_MODEL` para outro modelo instalado/compatível.

## Local
```bash
python app.py
```
Para usar Ollama localmente:
```bash
ollama serve
ollama pull qwen2.5:3b-instruct-q4_K_M
AETHEL_OLLAMA_MODEL=qwen2.5:3b-instruct-q4_K_M python app.py
```

## Render
O `Dockerfile` instala Ollama dentro do mesmo container e o `start.sh` inicia o Ollama, espera o endpoint, baixa o modelo se necessário e só então inicia o Aethel.

O modelo local é grande para planos pequenos. O `render.yaml` usa um disco persistente de 10 GB e plano Starter como ponto de partida. Se mudar de plano, ajuste recursos de RAM/CPU conforme o modelo escolhido.

## API principal
- `GET /health`
- `POST /api/chat` — resposta JSON compatível com o frontend legado
- `POST /api/chat/stream` — streaming real SSE
- `POST /api/memory` — memória persistente
- `POST /api/tools/execute` — execução controlada de Python
- `POST /api/agent` — cria projeto, testa e gera ZIP
- `GET /api/projects/download?name=...` — download autenticado do ZIP

### Limites importantes
A execução de código é deliberadamente restrita e não deve ser tratada como sandbox de segurança forte para código hostil. Para produção multiusuário, substitua por isolamento real (container/VM por execução, limites de CPU/RAM, seccomp/AppArmor e rede desabilitada).
