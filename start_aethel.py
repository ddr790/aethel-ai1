from __future__ import annotations
import os, subprocess, sys, time, webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
print('=== AETHEL LOCAL ===')
print('Diretório:', ROOT)
print('1) Servidor: http://127.0.0.1:5000')
print('2) O navegador deve abrir automaticamente.')
print('3) Para respostas gerais avançadas, o Aethel detecta automaticamente um modelo instalado no Ollama.')
print()
try:
    import app
    app.init_db()
    from http.server import ThreadingHTTPServer
    server=ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT','5000'))), app.Handler)
    try:
        webbrowser.open('http://127.0.0.1:5000/')
    except Exception:
        pass
    print('Aethel online. Pressione Ctrl+C para parar.')
    server.serve_forever()
except KeyboardInterrupt:
    print('\nAethel encerrado.')
