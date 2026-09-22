# Aethel V60+ — Plataforma Avançada

V60 é a evolução da V50 para uma plataforma local orientada a tarefas, projetos e operações auditáveis.

## Núcleo
- Ollama/local LLM, sem API externa de IA.
- Streaming SSE no chat.
- SQLite para contas, conversas e memória persistente.
- Agent iterativo com até 12 passos configuráveis.
- Ferramentas locais: calculator, Python controlado, list/read/write de arquivos.
- Workspace isolado por usuário e proteção contra path traversal.
- Auditoria JSONL das operações do Agent.
- Registro persistente de execuções e projetos.
- Validação automática de projetos Python/HTML e limites de arquivos/tamanho.
- ZIP final de projetos.
- Gerador de imagem local raster como fallback; isso não é diffusion.

## Novas APIs
- `GET /api/capabilities` — capacidades e limites da instalação.
- `GET /api/projects` — projetos do usuário.
- `GET /api/agent/runs` — histórico de execuções do Agent.
- `GET /api/tools` — catálogo e política das ferramentas.

## Limites padrão
- Agent: 12 passos.
- Projeto: 80 arquivos.
- Projeto: 8 MiB.
- Execução Python controlada: 8 s.

Esses limites são controles de segurança e não constituem um sandbox de segurança forte. Para execução não confiável em produção, use isolamento real (container/VM dedicado, seccomp/AppArmor ou serviço sandbox separado).

## Render
O `render.yaml` usa Docker + volume persistente em `/data`. O `start.sh` inicia Ollama, garante o modelo configurado e depois inicia o backend Aethel.

## Importante sobre capacidade
V60 é uma plataforma avançada em torno de um modelo local; ela não transforma automaticamente um modelo de 3B em um modelo de fronteira. Qualidade de raciocínio, código e multimodalidade continuam limitadas pelo modelo instalado e pelo hardware disponível.
