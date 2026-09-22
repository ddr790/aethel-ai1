# Aethel V17 — Public Edition

Aethel V17 is the next backend milestone of the local Aethel project. It now has its own SQLite database, its own account/session system and a compact neural model trained from scratch and served directly by the Python backend.

## Core architecture

`index.html` → `/api/chat` → `AethelInference` → local router/retriever → `Aethel Core v1`

No external AI API is required for the chat path.

## Data and authentication

The backend creates `data/aethel.db` automatically. It stores users, sessions, conversations and messages. Passwords are not stored in plain text; the backend derives a verifier with PBKDF2-HMAC-SHA256 and a per-user salt. Session tokens are random and only their SHA-256 hashes are stored.

## The trained model

`models/aethel-core-v1.npz` is a compact neural byte-level language model trained from scratch on `training_corpus.jsonl`. The server loads those learned weights at startup. The package also uses a local retrieval layer over the same corpus so common learned topics remain coherent on a small model.

This is a real trained model, but it is intentionally tiny. It is not a large transformer and is not comparable in knowledge or reasoning capacity to ChatGPT-class models. Scaling it materially would require a much larger corpus, tokenizer, transformer architecture, training compute, evaluation and serving infrastructure.

## Run

```bash
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` or keep opening the HTML file directly while the backend runs locally.
