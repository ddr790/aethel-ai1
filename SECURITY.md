# Segurança — Aethel V17

A versão inclui:

- PBKDF2-HMAC-SHA256 com salt aleatório para senhas
- Tokens de sessão aleatórios armazenados somente como SHA-256 no banco
- Cookies `HttpOnly` e `SameSite=Lax` quando usados no mesmo domínio
- Token de compatibilidade para execução via `file://`
- Consultas SQLite parametrizadas
- Limite de payload e limite de tamanho da mensagem
- Throttle simples em login/registro
- Cabeçalhos básicos de proteção HTTP

Ainda é necessário adicionar HTTPS, proteção CSRF específica para a política de deploy, recuperação de senha, verificação de email, rotação/revogação global de sessões, MFA/passkeys e observabilidade de segurança para uma operação comercial mais madura.
