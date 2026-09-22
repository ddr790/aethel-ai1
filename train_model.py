from __future__ import annotations
import argparse, json, random
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
MODEL_PATH=ROOT/'models'/'aethel-core-v1.npz'; CORPUS_PATH=ROOT/'training_corpus.jsonl'
BOS=256; EOT=257; VOCAB=258; CONTEXT=6; HIDDEN=64

def build_examples():
    base=[
    ("olá","Olá! Eu sou o Aethel. Posso ajudar com explicações, escrita, lógica, programação e ideias."),
    ("oi","Oi! Pode mandar a sua pergunta."),
    ("quem é você?","Eu sou o Aethel, um assistente com um modelo neural local treinado e servido pelo backend do próprio projeto."),
    ("o que é inteligência artificial?","Inteligência artificial é um conjunto de técnicas para construir sistemas capazes de aprender padrões, analisar dados, gerar conteúdo e executar tarefas."),
    ("o que é machine learning?","Machine learning é uma área da inteligência artificial em que modelos aprendem padrões a partir de dados para fazer previsões, classificações ou gerar respostas."),
    ("o que é banco de dados?","Um banco de dados é um sistema organizado para armazenar, consultar, atualizar e proteger informações de forma estruturada."),
    ("o que é autenticação?","Autenticação é o processo de verificar a identidade de uma pessoa, por exemplo usando senha, passkey, biometria ou outro fator."),
    ("o que é backend?","Backend é a parte do sistema que roda no servidor ou processo principal e cuida de dados, regras de negócio, autenticação e APIs."),
    ("o que é frontend?","Frontend é a parte da aplicação com a qual a pessoa interage diretamente, normalmente em um navegador ou aplicativo."),
    ("o que é um modelo de linguagem?","Um modelo de linguagem é uma rede neural treinada para prever ou gerar sequências de tokens a partir de padrões aprendidos em dados."),
    ("o que é SQLite?","SQLite é um banco de dados relacional embutido que armazena os dados em um arquivo e não exige um servidor de banco separado."),
    ("o que é JSON?","JSON é um formato textual estruturado usado para representar dados com objetos, listas, strings, números, booleanos e nulo."),
    ("o que é criptografia?","Criptografia usa técnicas matemáticas para proteger informação e limitar quem consegue interpretá-la."),
    ("o que é uma API?","Uma API é uma interface que define como um software pode solicitar dados ou executar operações em outro software."),
    ("escreva uma apresentação curta de uma startup de IA","A Aethel é uma plataforma de inteligência artificial criada para reunir conversa, criação e automação em uma experiência simples."),
    ("escreva um email profissional curto","Assunto: Atualização do projeto\n\nOlá, tudo bem?\n\nEstou enviando uma atualização sobre o projeto e os próximos passos.\n\nAtenciosamente,"),
    ("como faço um servidor HTTP simples em Python?","Você pode usar o módulo padrão http.server para criar um servidor básico sem depender de um framework externo."),
    ]
    facts={"segurança digital":"Segurança digital é o conjunto de práticas usadas para proteger contas, dispositivos, aplicações e dados contra acesso ou uso não autorizado.","cache":"Cache é uma cópia temporária de dados usada para reduzir trabalho repetido e acelerar acessos futuros.","latência":"Latência é o tempo entre uma solicitação e a resposta de um sistema.","rede neural":"Uma rede neural é um modelo computacional formado por camadas parametrizadas que aprendem representações a partir de dados.","tokenização":"Tokenização é a divisão de um texto em unidades menores chamadas tokens.","treinamento":"Treinamento é o processo de ajustar os parâmetros de um modelo para reduzir um erro em exemplos de dados.","inferência":"Inferência é a etapa em que um modelo treinado recebe uma entrada e produz uma saída."}
    for topic,a in facts.items():
        for q in [f"explique {topic}",f"o que é {topic}?",f"dê uma definição curta de {topic}"]: base.append((q,a))
    arithmetic=[("quanto é 2 + 2?","2 + 2 = 4."),("quanto é 15 * 7?","15 × 7 = 105."),("quanto é 100 / 4?","100 ÷ 4 = 25."),("quanto é 12% de 250?","12% de 250 = 30."),("qual é a raiz quadrada de 144?","A raiz quadrada principal de 144 é 12.")]
    base += arithmetic
    random.seed(42); out=[]
    for _ in range(40):
        chunk=base[:];random.shuffle(chunk);out += [f"Usuário: {q}\nAethel: {a}" for q,a in chunk]
    return out

def dataset(texts, samples, seed):
    raw=[]
    for t in texts: raw += [BOS]+list(t.encode('utf-8',errors='replace'))+[EOT]
    raw=np.asarray(raw,dtype=np.int16); rng=np.random.default_rng(seed); n=len(raw)-CONTEXT-1
    idx=rng.integers(0,n,size=samples)
    X=np.zeros((samples,CONTEXT*VOCAB),dtype=np.float32); y=raw[idx+CONTEXT].astype(np.int16)
    for r,i in enumerate(idx):
        win=raw[i:i+CONTEXT]
        X[r,np.arange(CONTEXT)*VOCAB+win]=1.0
    return X,y,raw

def softmax(z):
    z=z-z.max(axis=1,keepdims=True); e=np.exp(z); return e/e.sum(axis=1,keepdims=True)

def train(steps,batch,lr,seed,samples):
    rng=np.random.default_rng(seed); texts=build_examples();
    CORPUS_PATH.write_text('\n'.join(json.dumps({'text':t},ensure_ascii=False) for t in texts),encoding='utf-8')
    X,y,raw=dataset(texts,samples,seed)
    in_dim=CONTEXT*VOCAB
    W1=rng.normal(0,0.03,(in_dim,HIDDEN)).astype(np.float32);b1=np.zeros(HIDDEN,np.float32)
    W2=rng.normal(0,0.03,(HIDDEN,VOCAB)).astype(np.float32);b2=np.zeros(VOCAB,np.float32)
    print(f'[AETHEL] dataset={len(X):,} corpus={len(raw):,} tokens')
    for step in range(1,steps+1):
        ix=rng.integers(0,len(X),size=batch); xb=X[ix]; yb=y[ix]
        h0=xb@W1+b1;h=np.tanh(h0);logits=h@W2+b2;p=softmax(logits);p[np.arange(batch),yb]-=1;p/=batch
        gW2=h.T@p;gb2=p.sum(0);gh=(p@W2.T)*(1-h*h);gW1=xb.T@gh;gb1=gh.sum(0)
        W1-=lr*gW1; b1-=lr*gb1; W2-=lr*gW2; b2-=lr*gb2
        if step%100==0 or step==1 or step==steps:
            loss=-np.log(np.maximum(1e-9,softmax(h@W2+b2)[np.arange(batch),yb])).mean();print(f'[AETHEL] step {step}/{steps} loss={loss:.4f}')
    np.savez_compressed(MODEL_PATH,W1=W1,b1=b1,W2=W2,b2=b2,context=CONTEXT,hidden=HIDDEN,vocab=VOCAB,version='1.0.0',train_steps=steps,train_samples=samples)
    print('[AETHEL] modelo salvo em',MODEL_PATH)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--steps',type=int,default=1200);ap.add_argument('--batch',type=int,default=32);ap.add_argument('--lr',type=float,default=0.12);ap.add_argument('--samples',type=int,default=12000);ap.add_argument('--seed',type=int,default=42);a=ap.parse_args();train(a.steps,a.batch,a.lr,a.seed,a.samples)
