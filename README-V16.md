# Aethel V17 — Core + Auth + Database

Esta versão transforma o protótipo em um backend próprio com três blocos locais: banco SQLite, autenticação/sessões e Aethel Core.

## O que foi implementado

- SQLite próprio em `data/aethel.db`
- Registro e login por email + senha
- Senhas derivadas com PBKDF2-HMAC-SHA256 + salt aleatório
- Sessões persistentes com tokens aleatórios armazenados como hash
- Cookies HttpOnly no mesmo domínio e token de compatibilidade para `file://`
- Conversas e mensagens persistidas por usuário
- Renomear e apagar conversas no banco
- Aethel Core treinado do zero no próprio projeto, distribuído no pacote como `models/aethel-core-v1.npz`
- Roteador local de matemática/fatos + recuperação local do corpus + modelo neural para geração
- Nenhuma API de IA externa é necessária para o chat
- Aethel Vision continua local/procedural e não é um modelo de difusão

## Treinamento

O comando abaixo recria o modelo neural local usando o corpus de treinamento do projeto:

```bash
python train_model.py --steps 1200 --batch 32 --lr 0.12 --samples 12000
```

O arquivo final fica em `models/aethel-core-v1.npz`. O modelo incluído no pacote foi realmente treinado antes da publicação deste build.

## Executar

```bash
pip install -r requirements.txt
python app.py
```

Abra `http://127.0.0.1:5000`. Para abrir o HTML diretamente como arquivo, o frontend também entende `http://127.0.0.1:5000` como backend local.

## Produção

SQLite é excelente para um único processo/instância e para uma publicação simples. Para escalar horizontalmente, o banco deve ser migrado para PostgreSQL ou outro banco servidor e as sessões/cache devem ser externalizadas. O `Aethel Core v1` também é um modelo compacto; não é comparável em escala, conhecimento ou capacidade a grandes LLMs comerciais.

Antes de cobrar usuários, configure checkout real, limites por plano, webhooks de pagamento, recuperação de senha, verificação de email, observabilidade e uma política de privacidade/termos adequada ao negócio.
