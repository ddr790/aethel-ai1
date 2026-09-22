# Aethel V18 — General Local AI

Esta versão remove o comportamento de chatbot pré-programado como resposta principal e deixa Roblox como apenas um domínio de programação.

## Cérebro local
O backend aceita um servidor de LLM local compatível com a API do Ollama. Defina `AETHEL_OLLAMA_MODEL` e deixe `AETHEL_OLLAMA_URL` apontando para o servidor local. Não é uma API de nuvem.

Sem um LLM grande instalado, o Aethel não finge que é uma IA geral: ele mantém ferramentas determinísticas para matemática simples e especialistas de código.

## Imagens
O antigo SVG de blocos foi removido do fluxo principal. O endpoint `/api/image` agora procura um servidor local compatível com Stable Diffusion WebUI em `AETHEL_IMAGE_URL`. Sem esse modelo, o frontend mostra que o gerador não está configurado em vez de apresentar um SVG como se fosse uma imagem gerada por IA.

## Importante
Esta arquitetura torna o software preparado para usar modelos locais reais, mas a qualidade da IA depende do modelo instalado e do hardware disponível. O pacote não contém um modelo generativo grande.
