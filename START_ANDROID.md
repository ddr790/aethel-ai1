# Aethel no Android / Termux

O arquivo `index.html` sozinho **não inicia o Python**. No Android, use o Termux para iniciar o backend.

## Primeira vez

```bash
pkg update -y
pkg install python -y
cd /caminho/da/pasta/aethel
python start_aethel.py
```

Se a pasta estiver em Downloads e o Termux ainda não tiver acesso ao armazenamento:

```bash
termux-setup-storage
cd ~/storage/downloads/aethel
python start_aethel.py
```

Depois abra no Chrome:

`http://127.0.0.1:5000/`

## Próximas vezes

```bash
cd ~/storage/downloads/aethel
python start_aethel.py
```

Não abra `index.html` como arquivo para usar o cérebro local. O Chrome não consegue executar `app.py` sozinho.
