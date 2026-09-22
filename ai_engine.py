from __future__ import annotations
import json, os, re, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SYSTEM_PROMPT=os.environ.get('AETHEL_SYSTEM_PROMPT', '''You are Aethel, a general-purpose local AI assistant. Answer in the user's language. You can help with mathematics, science, business, writing, programming, web development, data, documents and creative work. Do not claim you executed code or created files unless a tool actually did it. For software tasks, provide complete coherent implementations. Roblox/Luau is only one programming domain. When working on projects, think in terms of files, architecture, tests and deliverables.''')

class LocalLLM:
    def __init__(self):
        self.url=os.environ.get('AETHEL_OLLAMA_URL','http://127.0.0.1:11434').rstrip('/')
        self.requested_model=os.environ.get('AETHEL_OLLAMA_MODEL','').strip()
        self.model=self.requested_model
        self.vision_model=os.environ.get('AETHEL_VISION_MODEL','qwen2.5vl:3b').strip()
        self.timeout=float(os.environ.get('AETHEL_LLM_TIMEOUT','180'))
        self.last_error=''
        if not self.model: self.model=self._discover_model() or ''
    def _discover_model(self):
        try:
            req=urllib.request.Request(self.url+'/api/tags',headers={'Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=3) as r: data=json.loads(r.read().decode())
            names=[str(x.get('name','')).strip() for x in data.get('models',[]) if x.get('name')]
            prefs=('qwen','llama','gemma','mistral','deepseek','phi')
            for p in prefs:
                for n in names:
                    if p in n.lower(): return n
            return names[0] if names else None
        except Exception as e:
            self.last_error=str(e); return None
    @property
    def configured(self):
        # The environment variable only selects a model; it does not mean the
        # model is actually installed. Check Ollama so startup can happen before
        # the background pull finishes and the chat can recover automatically.
        installed=self.installed_models()
        if self.requested_model:
            if self.requested_model in installed:
                self.model=self.requested_model
                self.last_error=''
                return True
            # Ollama may expose a digest-qualified name. Accept the exact base
            # model name as a prefix only when it is clearly the same tag.
            for name in installed:
                if name.split('@',1)[0] == self.requested_model:
                    self.model=name
                    self.last_error=''
                    return True
            return False
        if self.model and self.model in installed:
            self.last_error=''
            return True
        discovered=self._discover_model()
        if discovered:
            self.model=discovered
            self.last_error=''
            return True
        return False

    def refresh(self):
        installed=self.installed_models()
        if self.requested_model:
            if self.requested_model in installed:
                self.model=self.requested_model; self.last_error=''; return True
            for name in installed:
                if name.split('@',1)[0] == self.requested_model:
                    self.model=name; self.last_error=''; return True
            return False
        discovered=self._discover_model()
        if discovered:
            self.model=discovered
            self.last_error=''
        return bool(discovered)

    def installed_models(self):
        try:
            req=urllib.request.Request(self.url+'/api/tags',headers={'Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=3) as r: data=json.loads(r.read().decode())
            return [str(x.get('name','')).strip() for x in data.get('models',[]) if x.get('name')]
        except Exception as e:
            self.last_error=str(e)
            return []
    def _messages(self,message,history=None,memory=None,temperature=.7,images=None):
        sys=SYSTEM_PROMPT
        if memory:
            sys += '\n\nRelevant persistent memory about this user/project:\n' + '\n'.join('- '+str(x) for x in memory[-12:])
        msgs=[{'role':'system','content':sys}]
        for item in (history or [])[-24:]:
            if item.get('role') in ('user','assistant'):
                msgs.append({'role':item['role'],'content':str(item.get('content',''))})
        user={'role':'user','content':message}
        if images:
            user['images']=images[:4]
        msgs.append(user)
        return msgs
    def stream(self,message,history=None,memory=None,temperature=.7,images=None,model=None):
        if not self.configured:
            detail=self.last_error or 'Ollama ainda não possui um modelo carregado.'
            raise RuntimeError('LLM local ainda não está pronto. '+detail)
        payload=json.dumps({'model':model or self.model,'messages':self._messages(message,history,memory,temperature,images),'stream':True,'options':{'temperature':max(.05,min(float(temperature),1.2))}}).encode()
        req=urllib.request.Request(self.url+'/api/chat',data=payload,headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as r:
                for raw in r:
                    line=raw.decode('utf-8','replace').strip()
                    if not line: continue
                    try:
                        obj=json.loads(line)
                        chunk=((obj.get('message') or {}).get('content')) or ''
                        if chunk: yield chunk
                        if obj.get('done'): break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            self.last_error=str(e); raise
    def chat(self,message,history=None,memory=None,temperature=.7,images=None,model=None):
        return ''.join(self.stream(message,history,memory,temperature,images,model)).strip()
    def json_task(self,prompt,history=None,memory=None):
        text=self.chat(prompt,history,memory,.15)
        m=re.search(r'\{.*\}',text,re.S)
        if not m: raise ValueError('O modelo não retornou JSON válido')
        return json.loads(m.group(0))

class AethelInference:
    def __init__(self): self.llm=LocalLLM()
    def stream(self,message,history=None,model='Aethel Reasoning',temperature=.7,memory=None,images=None,web_context=None):
        if self.llm.configured:
            prompt=message
            if web_context:
                prompt += '\n\n[WEB SEARCH CONTEXT — use as current source material; do not invent citations]\n' + web_context[:24000]
            chosen=self.llm.vision_model if images else self.llm.model
            yield from self.llm.stream(prompt,history,memory,temperature,images,chosen); return
        # Deterministic local specialists keep the assistant useful while Ollama starts.
        if re.fullmatch(r'\s*[\d\s\+\-\*\/%().]+\s*',message):
            try: yield str(eval(message,{'__builtins__':{}},{})); return
            except Exception: pass
        if re.search(r'\b(html|css|javascript|python|typescript|sql|site|website|código|codigo)\b',message,re.I):
            yield 'O modelo LLM local ainda está iniciando. Aethel reconheceu uma tarefa de programação; aguarde o Ollama carregar o modelo e envie novamente para geração completa.'; return
        yield 'O LLM local ainda não está disponível. O servidor Aethel está funcionando, mas o modelo precisa terminar de carregar.'
    def reply(self,message,history=None,model='Aethel Reasoning',temperature=.7,memory=None,images=None,web_context=None):
        return ''.join(self.stream(message,history,model,temperature,memory,images,web_context)).strip(), {'engine':'Aethel Local Vision' if images else ('Aethel Local LLM' if self.llm.configured else 'Aethel Local Specialists'),'local':True,'model':self.llm.vision_model if images else (self.llm.model or None)}
