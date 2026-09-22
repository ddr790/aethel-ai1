# Aethel V20 — conexão local corrigida

Esta versão corrige o comportamento do frontend quando o backend demora para responder e adiciona tentativas automáticas de reconexão. Também inclui instruções específicas para Android/Termux.

**Importante:** abrir `index.html` diretamente não inicia Python. Para o cérebro local funcionar, o servidor precisa estar rodando em `127.0.0.1:5000`.

O cérebro local incluído é um protótipo pequeno. Para respostas gerais de alta qualidade é necessário conectar um modelo LLM local compatível (por exemplo, através de um runtime local); a versão incluída não é equivalente a um modelo de fronteira.
