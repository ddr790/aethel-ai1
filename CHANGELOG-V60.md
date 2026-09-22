# Aethel V60+

## Plataforma avançada

V60 mantém a base operacional da V50 e adiciona uma camada de plataforma:

1. Agent com até 12 passos.
2. Histórico persistente de runs.
3. Registro persistente de projetos.
4. Validação automática de artefatos Python e HTML.
5. Limites de quantidade de arquivos e tamanho de projeto.
6. Catálogo de capacidades em `/api/capabilities`.
7. Observabilidade de ferramentas em `/api/tools`.
8. Auditoria de operações.
9. Health report ampliado.
10. Render + Docker + Ollama + armazenamento persistente.

## O que ainda depende do modelo/hardware

- Raciocínio e qualidade de código dependem do LLM Ollama instalado.
- Vision real não está ativada nesta build.
- Pesquisa web não está ativada nesta build.
- O gerador raster é um fallback visual e não substitui um modelo diffusion.
- `execute_python` é execução controlada, não um sandbox de segurança forte.
