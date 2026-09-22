# Aethel V18 — execução local corrigida

## 1. Iniciar o Aethel

Windows: execute `run_aethel.bat`.

Linux/macOS/Termux: `python3 start_aethel.py`.

Ou: `python app.py`.

Depois abra `http://127.0.0.1:5000/`.

## 2. Modelo de linguagem local

O Aethel tenta detectar automaticamente um modelo instalado no Ollama em `127.0.0.1:11434`.
Se quiser fixar um modelo:

`AETHEL_OLLAMA_MODEL=nome-do-modelo`

Sem um modelo LLM grande instalado, o backend ainda funciona para matemática, ferramentas e tarefas locais, mas não deve ser apresentado como equivalente a um LLM de fronteira.

## 3. Imagens

O endpoint `/api/image` agora **sempre devolve um PNG**. Se `AETHEL_IMAGE_URL` apontar para uma instalação compatível com Stable Diffusion WebUI, ela será usada. Se estiver indisponível, o Aethel usa um renderizador PNG local de fallback para que o recurso não quebre.

O fallback é um renderizador visual local, não um modelo generativo de difusão. Para geração fotorealista, instale/configure um modelo de imagem local e defina `AETHEL_IMAGE_URL`.
