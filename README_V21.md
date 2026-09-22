# Aethel V21 — Image Generator Fix

O endpoint `/api/image` não depende mais de `AETHEL_IMAGE_URL`.

- Sem Stable Diffusion: usa `Aethel Local Raster` e retorna PNG válido.
- Com `AETHEL_IMAGE_URL`: tenta Stable Diffusion WebUI e usa raster como fallback.
- A interface não exibe mais “Modelo de imagem local não configurado” por ausência de configuração.
- O frontend faz uma segunda tentativa automática se o servidor acabou de iniciar.

Inicie com `python start_aethel.py` e abra `http://127.0.0.1:5000/`.
