# Aethel V17 — Brain Upgrade

Esta versão corrige o principal problema do V16: o cérebro não deve responder com texto aleatório quando recebe perguntas simples.

## O que mudou
- Chat de visitante funciona sem cadastro.
- `oi`, saudações e matemática são respondidos imediatamente.
- Novo roteador especialista para código.
- Especialista de Roblox Studio/Luau com templates funcionais para Sprint/Shift, leaderstats/Coins, Kill Brick e DataStore.
- Especialistas para Python, JavaScript/TypeScript, HTML, CSS e SQL.
- O pequeno modelo neural continua treinado e servido localmente, mas gerações de baixa qualidade são descartadas em vez de exibidas.
- Usuários autenticados continuam tendo conversas persistidas no SQLite.
- Fallback no navegador também ganhou os mesmos comportamentos essenciais.

## Limitação importante
O modelo neural compacto incluído não é um LLM de escala ChatGPT. Ele é um componente neural local real, enquanto o sistema especialista fornece comportamento determinístico e útil para tarefas conhecidas. Para chegar a um modelo de linguagem grande, seria necessário um treinamento e uma infraestrutura muito maiores.
