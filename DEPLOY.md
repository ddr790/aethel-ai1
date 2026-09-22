# Deploy Aethel V17

## Docker

```bash
docker build -t aethel-v17 .
docker run --rm -p 5000:5000 -v aethel_data:/app/data aethel-v17
```

O volume é importante para não perder o SQLite.

## Variáveis

- `PORT` — porta HTTP
- `AETHEL_DB_PATH` — caminho do SQLite
- `AETHEL_SESSION_DAYS` — duração das sessões
- `AETHEL_COOKIE_SECURE=1` — habilite quando o deploy usar HTTPS
- `AETHEL_CHECKOUT_BASIC` — URL de checkout do Basic
- `AETHEL_CHECKOUT_PRO` — URL de checkout do Pro
- `AETHEL_ENTERPRISE_EMAIL` — contato Enterprise

Para uma frota de múltiplas instâncias, substitua o SQLite por um banco servidor e centralize sessões/cache.
