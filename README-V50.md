# Aethel V50 — Autonomous Local Agent

V50 evolui a V40 para uma arquitetura de agente local orientada a ferramentas.

## Novidades
- registry real de ferramentas: calculator, execute_python, list_files, read_file, write_file;
- Agent iterativo com até `AETHEL_AGENT_MAX_STEPS` passos;
- cada passo retorna JSON estruturado e executa uma única ferramenta;
- workspace com proteção contra path traversal;
- auditoria JSONL das ações do Agent;
- validação automática de Python e geração de ZIP;
- `/api/tools` expõe as ferramentas e a política de execução;
- `/health` informa ferramentas e limite do Agent;
- mantém Ollama + streaming SSE + memória persistente da V40.

## Segurança
A execução Python continua sendo uma sandbox limitada, não uma sandbox de segurança forte. Para código hostil/multi-tenant, use isolamento por container/VM, seccomp/AppArmor, limites de CPU/RAM e rede desabilitada.

## Render
Use Docker + disco persistente. O Ollama baixa o modelo configurado no primeiro boot. O modelo padrão continua `qwen2.5:3b-instruct-q4_K_M`.
