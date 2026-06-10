"""
jogos_espera.py — Jogos HTML5 para a sala de espera da avaliação
Cada função retorna uma string HTML completa pronta para st.components.v1.html()
"""

JOGOS_DISPONIVEIS = {
    "snake":   "🐍 Snake",
    "memoria": "🧩 Jogo da Memória",
    "quiz":    "💡 Quiz Tech",
    "forca":   "🔤 Forca Dev",
    "digitacao": "⌨️ Digitação Rápida",
}


def html_snake(nome_aluno: str) -> str:
    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  body {{ margin:0; background:#1a1a2e; display:flex; flex-direction:column;
         align-items:center; justify-content:center; height:520px;
         font-family:'Segoe UI',sans-serif; color:#eee; }}
  h2 {{ color:#E30613; margin:8px 0 4px; font-size:1.1rem; }}
  #info {{ font-size:.85rem; color:#aaa; margin-bottom:8px; }}
  canvas {{ border:2px solid #E30613; border-radius:6px; background:#0f0f23; }}
  #score {{ font-size:1.2rem; font-weight:700; color:#00ff88; margin:8px 0 4px; }}
  #msg {{ font-size:.9rem; color:#ffc107; min-height:1.2em; }}
  button {{ background:#E30613; color:#fff; border:none; border-radius:6px;
            padding:8px 24px; font-size:.95rem; cursor:pointer; margin-top:6px; }}
  button:hover {{ background:#c0000f; }}
</style></head><body>
<h2>🐍 Snake — {nome_aluno}</h2>
<div id="info">Use as setas do teclado ou WASD para mover</div>
<div id="score">Pontos: 0</div>
<canvas id="c" width="360" height="360"></canvas>
<div id="msg">Pressione qualquer tecla para começar</div>
<button onclick="reiniciar()">▶ Reiniciar</button>
<script>
const canvas=document.getElementById('c'),ctx=canvas.getContext('2d');
const SZ=18,COLS=20,ROWS=20;
let snake,dir,nextDir,food,score,loop,running=false,started=false;

function reiniciar(){{
  snake=[{{x:10,y:10}},{{x:9,y:10}},{{x:8,y:10}}];
  dir={{x:1,y:0}}; nextDir={{x:1,y:0}};
  score=0; running=true; started=true;
  document.getElementById('msg').textContent='';
  document.getElementById('score').textContent='Pontos: 0';
  spawnFood();
  clearInterval(loop);
  loop=setInterval(tick,120);
}}

function spawnFood(){{
  do{{ food={{x:Math.floor(Math.random()*COLS),y:Math.floor(Math.random()*ROWS)}}; }}
  while(snake.some(s=>s.x===food.x&&s.y===food.y));
}}

function tick(){{
  dir=nextDir;
  const head={{x:snake[0].x+dir.x,y:snake[0].y+dir.y}};
  if(head.x<0||head.x>=COLS||head.y<0||head.y>=ROWS||
     snake.some(s=>s.x===head.x&&s.y===head.y)){{
    running=false; clearInterval(loop);
    document.getElementById('msg').textContent=`💀 Game Over! Pontuação: ${{score}}`;
    return;
  }}
  snake.unshift(head);
  if(head.x===food.x&&head.y===food.y){{
    score+=10; document.getElementById('score').textContent='Pontos: '+score;
    spawnFood();
  }} else snake.pop();
  draw();
}}

function draw(){{
  ctx.fillStyle='#0f0f23'; ctx.fillRect(0,0,360,360);
  // grid sutil
  ctx.strokeStyle='#1a1a3e'; ctx.lineWidth=0.5;
  for(let i=0;i<=COLS;i++){{ctx.beginPath();ctx.moveTo(i*SZ,0);ctx.lineTo(i*SZ,360);ctx.stroke();}}
  for(let j=0;j<=ROWS;j++){{ctx.beginPath();ctx.moveTo(0,j*SZ);ctx.lineTo(360,j*SZ);ctx.stroke();}}
  // cobra
  snake.forEach((s,i)=>{{
    ctx.fillStyle= i===0?'#00ff88':'#00cc66';
    ctx.beginPath();
    ctx.roundRect(s.x*SZ+1,s.y*SZ+1,SZ-2,SZ-2,3);
    ctx.fill();
  }});
  // olho
  const h=snake[0];
  ctx.fillStyle='#000';
  ctx.beginPath(); ctx.arc(h.x*SZ+SZ*0.65,h.y*SZ+SZ*0.35,2,0,Math.PI*2); ctx.fill();
  // comida
  ctx.fillStyle='#E30613';
  ctx.beginPath(); ctx.arc(food.x*SZ+SZ/2,food.y*SZ+SZ/2,SZ/2-2,0,Math.PI*2); ctx.fill();
  ctx.fillStyle='#ff6b6b'; ctx.beginPath();
  ctx.arc(food.x*SZ+SZ/2-2,food.y*SZ+SZ/2-2,3,0,Math.PI*2); ctx.fill();
}}

// draw inicial
ctx.fillStyle='#0f0f23'; ctx.fillRect(0,0,360,360);
ctx.fillStyle='#555'; ctx.font='18px Segoe UI'; ctx.textAlign='center';
ctx.fillText('Pressione uma tecla para começar',180,185);

document.addEventListener('keydown',e=>{{
  const map={{ArrowUp:{{x:0,y:-1}},ArrowDown:{{x:0,y:1}},
              ArrowLeft:{{x:-1,y:0}},ArrowRight:{{x:1,y:0}},
              w:{{x:0,y:-1}},s:{{x:0,y:1}},a:{{x:-1,y:0}},d:{{x:1,y:0}},
              W:{{x:0,y:-1}},S:{{x:0,y:1}},A:{{x:-1,y:0}},D:{{x:1,y:0}}}};
  if(map[e.key]){{
    e.preventDefault();
    const nd=map[e.key];
    if(!(nd.x===-dir.x&&nd.y===-dir.y)) nextDir=nd;
    if(!started) reiniciar();
  }}
}});
</script></body></html>
"""


def html_memoria(nome_aluno: str) -> str:
    pares = [
        ("if/else","Condicional"),("for","Laço"),("while","Loop"),
        ("função","Bloco reutilizável"),("array","Vetor"),("classe","Molde de objeto"),
        ("variável","Espaço na memória"),("boolean","Verdadeiro/Falso"),
    ]
    import json as _json
    pares_json = _json.dumps(pares)
    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  body{{margin:0;background:#1a1a2e;display:flex;flex-direction:column;
       align-items:center;font-family:'Segoe UI',sans-serif;color:#eee;padding:12px;box-sizing:border-box;}}
  h2{{color:#E30613;margin:4px 0;font-size:1.1rem;}}
  #placar{{font-size:.9rem;color:#aaa;margin:4px 0 10px;}}
  #score{{font-weight:700;color:#00ff88;}}
  #grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;width:380px;}}
  .card{{height:80px;background:#16213e;border:2px solid #2a2a5e;border-radius:8px;
         cursor:pointer;display:flex;align-items:center;justify-content:center;
         font-size:.75rem;text-align:center;padding:4px;transition:all .2s;
         user-select:none;}}
  .card:hover{{border-color:#E30613;}}
  .card.virada{{background:#E30613;color:#fff;border-color:#E30613;font-weight:600;}}
  .card.par{{background:#198754;border-color:#198754;cursor:default;}}
  #msg{{margin-top:10px;font-size:.95rem;color:#ffc107;min-height:1.4em;text-align:center;}}
  button{{background:#E30613;color:#fff;border:none;border-radius:6px;
          padding:7px 22px;font-size:.9rem;cursor:pointer;margin-top:8px;}}
  button:hover{{background:#c0000f;}}
</style></head><body>
<h2>🧩 Memória Dev — {nome_aluno}</h2>
<div id="placar">Pares: <span id="score">0/8</span> &nbsp;|&nbsp; Tentativas: <span id="tent">0</span></div>
<div id="grid"></div>
<div id="msg">Encontre os pares: termo ↔ definição</div>
<button onclick="iniciar()">▶ Novo Jogo</button>
<script>
const pares={pares_json};
let cartas=[],viradas=[],pares_ok=0,tentativas=0,bloqueado=false;

function iniciar(){{
  pares_ok=0;tentativas=0;viradas=[];bloqueado=false;
  document.getElementById('score').textContent='0/8';
  document.getElementById('tent').textContent='0';
  document.getElementById('msg').textContent='Encontre os pares: termo ↔ definição';
  // monta deck
  let deck=[];
  pares.forEach((p,i)=>{{
    deck.push({{id:i*2,  par:i, texto:p[0], tipo:'termo'}});
    deck.push({{id:i*2+1,par:i, texto:p[1], tipo:'def'}});
  }});
  // embaralha
  for(let i=deck.length-1;i>0;i--){{
    const j=Math.floor(Math.random()*(i+1));[deck[i],deck[j]]=[deck[j],deck[i]];
  }}
  cartas=deck;
  const g=document.getElementById('grid');
  g.innerHTML='';
  deck.forEach((c,i)=>{{
    const el=document.createElement('div');
    el.className='card'; el.dataset.i=i;
    el.textContent='?';
    el.onclick=()=>virar(i,el);
    g.appendChild(el);
  }});
}}

function virar(i,el){{
  if(bloqueado||el.classList.contains('par')||el.classList.contains('virada')) return;
  el.classList.add('virada');
  el.textContent=cartas[i].texto;
  viradas.push({{i,el}});
  if(viradas.length===2){{
    tentativas++;
    document.getElementById('tent').textContent=tentativas;
    bloqueado=true;
    const [a,b]=viradas;
    if(cartas[a.i].par===cartas[b.i].par&&a.i!==b.i){{
      a.el.classList.replace('virada','par');
      b.el.classList.replace('virada','par');
      pares_ok++;
      document.getElementById('score').textContent=pares_ok+'/8';
      viradas=[];bloqueado=false;
      if(pares_ok===8) document.getElementById('msg').textContent=
        `🎉 Parabéns! Completou em ${{tentativas}} tentativas!`;
    }} else {{
      setTimeout(()=>{{
        a.el.classList.remove('virada'); a.el.textContent='?';
        b.el.classList.remove('virada'); b.el.textContent='?';
        viradas=[];bloqueado=false;
      }},900);
    }}
  }}
}}
iniciar();
</script></body></html>
"""


def html_quiz(nome_aluno: str) -> str:
    perguntas = [
        ("Qual linguagem é conhecida como 'a linguagem da web' no frontend?","JavaScript","Python","Java","C#",0),
        ("O que significa a sigla HTML?","HyperText Markup Language","High Tech Modern Language","HyperText Modern Layout","Hyper Transfer Markup Logic",0),
        ("Qual estrutura de dados funciona como uma pilha de pratos (LIFO)?","Stack","Queue","Array","Grafo",0),
        ("Em Python, como se cria uma lista vazia?","[]","{}","()","<>",0),
        ("O que é um bug em programação?","Erro no código","Comentário","Variável global","Tipo de dado",0),
        ("Qual protocolo é usado para navegar na web?","HTTP","FTP","SSH","SMTP",0),
        ("Git é uma ferramenta de:","Controle de versão","Design gráfico","Banco de dados","Rede",0),
        ("O que significa CPU?","Central Processing Unit","Computer Power Unit","Core Program Utility","Central Program Upload",0),
        ("Em lógica, AND retorna true quando:","Ambos são true","Pelo menos um é true","Nenhum é true","Qualquer valor",0),
        ("Qual das linguagens é usada para criar jogos com Unity?","C#","HTML","SQL","PHP",0),
        ("O que é um algoritmo?","Sequência de passos para resolver um problema","Tipo de vírus","Linguagem de programação","Hardware",0),
        ("RAM significa:","Random Access Memory","Read All Memory","Remote Access Module","Run Application Mode",0),
    ]
    import json as _json
    import random as _r
    _r.shuffle(perguntas)
    perguntas_json = _json.dumps(perguntas[:8])
    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  body{{margin:0;background:#1a1a2e;display:flex;flex-direction:column;
       align-items:center;font-family:'Segoe UI',sans-serif;color:#eee;
       padding:16px;box-sizing:border-box;min-height:500px;}}
  h2{{color:#E30613;margin:4px 0 2px;font-size:1.1rem;}}
  #prog{{font-size:.85rem;color:#aaa;margin:4px 0 12px;}}
  #pergunta{{background:#16213e;border-left:4px solid #E30613;border-radius:8px;
             padding:16px 18px;width:400px;max-width:95vw;font-size:1rem;
             line-height:1.5;margin-bottom:14px;}}
  .opt{{display:block;width:400px;max-width:95vw;background:#16213e;
        border:2px solid #2a2a5e;border-radius:8px;padding:10px 16px;
        margin:6px 0;cursor:pointer;text-align:left;color:#eee;
        font-size:.93rem;transition:all .15s;}}
  .opt:hover{{border-color:#E30613;background:#1e2a4e;}}
  .opt.certa{{background:#198754;border-color:#198754;}}
  .opt.errada{{background:#dc3545;border-color:#dc3545;}}
  #feedback{{min-height:1.4em;font-size:.9rem;color:#ffc107;margin:8px 0;text-align:center;}}
  #score-fin{{font-size:2rem;font-weight:700;color:#00ff88;text-align:center;margin:12px 0 4px;}}
  button{{background:#E30613;color:#fff;border:none;border-radius:6px;
          padding:8px 24px;font-size:.95rem;cursor:pointer;margin-top:8px;}}
  button:hover{{background:#c0000f;}}
</style></head><body>
<h2>💡 Quiz Tech — {nome_aluno}</h2>
<div id="prog"></div>
<div id="pergunta"></div>
<div id="opcoes"></div>
<div id="feedback"></div>
<button id="btn" style="display:none" onclick="avancar()">Próxima ➡️</button>
<script>
const qs={perguntas_json};
let idx=0,acertos=0,respondeu=false;

function mostrar(){{
  if(idx>=qs.length){{fim();return;}}
  respondeu=false;
  const q=qs[idx];
  document.getElementById('prog').textContent=`Questão ${{idx+1}} de ${{qs.length}} | ✅ ${{acertos}} acertos`;
  document.getElementById('pergunta').textContent=q[0];
  document.getElementById('feedback').textContent='';
  document.getElementById('btn').style.display='none';
  // embaralha opções mantendo rastreio da correta
  let opts=[{{t:q[1],c:true}},{{t:q[2],c:false}},{{t:q[3],c:false}},{{t:q[4],c:false}}];
  for(let i=opts.length-1;i>0;i--){{const j=Math.floor(Math.random()*(i+1));[opts[i],opts[j]]=[opts[j],opts[i]];}}
  const div=document.getElementById('opcoes');
  div.innerHTML='';
  opts.forEach((o,i)=>{{
    const b=document.createElement('button');
    b.className='opt'; b.textContent=`${{String.fromCharCode(65+i)}}. ${{o.t}}`;
    b.dataset.correta=o.c;
    b.onclick=()=>responder(b,o.c);
    div.appendChild(b);
  }});
}}

function responder(btn,correta){{
  if(respondeu) return;
  respondeu=true;
  document.querySelectorAll('.opt').forEach(b=>{{
    b.disabled=true;
    if(b.dataset.correta==='true') b.classList.add('certa');
    else if(b===btn&&!correta) b.classList.add('errada');
  }});
  if(correta){{acertos++;document.getElementById('feedback').textContent='✅ Correto!';}}
  else {{document.getElementById('feedback').textContent='❌ Errado! A certa está em verde.';}}
  document.getElementById('btn').style.display='inline-block';
}}

function avancar(){{idx++;mostrar();}}

function fim(){{
  document.getElementById('pergunta').textContent='';
  document.getElementById('opcoes').innerHTML='';
  document.getElementById('btn').style.display='none';
  document.getElementById('prog').textContent='';
  document.getElementById('score-fin')&&document.getElementById('score-fin').remove();
  const s=document.createElement('div'); s.id='score-fin';
  s.innerHTML=`<br>🏁 Fim do Quiz!<br><span style="font-size:2.5rem">${{acertos}}/${{qs.length}}</span><br>
  <span style="font-size:1rem;color:#aaa">${{acertos===qs.length?'🌟 Perfeito!':acertos>=6?'👏 Muito bom!':'📚 Continue estudando!'}}</span>`;
  document.getElementById('feedback').before(s);
  const r=document.createElement('button'); r.textContent='🔄 Jogar novamente';
  r.onclick=()=>{{idx=0;acertos=0;s.remove();r.remove();mostrar();}};
  document.getElementById('feedback').after(r);
}}
mostrar();
</script></body></html>
"""


def html_forca(nome_aluno: str) -> str:
    palavras = [
        ("VARIAVEL","Espaço na memória que armazena um valor"),
        ("FUNCAO","Bloco de código reutilizável"),
        ("ARRAY","Estrutura que guarda vários valores"),
        ("LOOP","Estrutura de repetição"),
        ("CLASSE","Molde para criar objetos"),
        ("OBJETO","Instância de uma classe"),
        ("BOOLEANO","Tipo de dado verdadeiro ou falso"),
        ("ALGORITMO","Sequência de passos para resolver um problema"),
        ("COMPILADOR","Programa que traduz código para binário"),
        ("DEBUGAR","Processo de encontrar e corrigir erros"),
        ("RECURSAO","Função que chama a si mesma"),
        ("HERANCA","Mecanismo de reutilização em POO"),
        ("FRAMEWORK","Conjunto de ferramentas prontas para desenvolver"),
        ("INTERFACE","Contrato que define métodos a implementar"),
        ("ENCAPSULAMENTO","Ocultar detalhes internos de uma classe"),
    ]
    import json as _json, random as _r
    palavras_json = _json.dumps(palavras)
    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  body{{margin:0;background:#1a1a2e;display:flex;flex-direction:column;
       align-items:center;font-family:'Segoe UI',sans-serif;color:#eee;
       padding:12px;box-sizing:border-box;}}
  h2{{color:#E30613;margin:4px 0;font-size:1.1rem;}}
  #dica{{font-size:.83rem;color:#aaa;background:#16213e;border-radius:6px;
         padding:6px 14px;margin:6px 0 10px;max-width:400px;text-align:center;}}
  #palavra{{font-size:1.8rem;letter-spacing:10px;font-weight:700;
            font-family:monospace;color:#00ff88;margin:8px 0;min-height:2.2rem;}}
  #forca{{font-family:monospace;font-size:.75rem;line-height:1.3;color:#aaa;margin:4px 0;}}
  #letras{{display:flex;flex-wrap:wrap;gap:5px;justify-content:center;
           max-width:380px;margin:10px 0;}}
  .letra{{width:36px;height:36px;background:#16213e;border:2px solid #2a2a5e;
          border-radius:6px;cursor:pointer;font-size:1rem;font-weight:700;
          color:#eee;display:flex;align-items:center;justify-content:center;
          transition:all .15s;}}
  .letra:hover:not(.usada){{border-color:#E30613;background:#1e2a4e;}}
  .letra.acerto{{background:#198754;border-color:#198754;cursor:default;}}
  .letra.erro{{background:#444;border-color:#333;color:#666;cursor:default;}}
  #msg{{font-size:1rem;color:#ffc107;min-height:1.3em;margin:4px 0;text-align:center;}}
  #erros-vis{{font-size:.85rem;color:#dc3545;margin:2px 0;}}
  button{{background:#E30613;color:#fff;border:none;border-radius:6px;
          padding:7px 22px;font-size:.9rem;cursor:pointer;margin-top:6px;}}
  button:hover{{background:#c0000f;}}
</style></head><body>
<h2>🔤 Forca Dev — {nome_aluno}</h2>
<div id="dica"></div>
<div id="palavra"></div>
<div id="erros-vis"></div>
<pre id="forca"></pre>
<div id="letras"></div>
<div id="msg"></div>
<button onclick="novaRodada()">🔄 Nova Palavra</button>
<script>
const banco={palavras_json};
const forcaEtapas=[
`  +---+
  |   |
      |
      |
      |
      |
=========`,
`  +---+
  |   |
  O   |
      |
      |
      |
=========`,
`  +---+
  |   |
  O   |
  |   |
      |
      |
=========`,
`  +---+
  |   |
  O   |
 /|   |
      |
      |
=========`,
`  +---+
  |   |
  O   |
 /|\\  |
      |
      |
=========`,
`  +---+
  |   |
  O   |
 /|\\  |
 /    |
      |
=========`,
`  +---+
  |   |
  O   |
 /|\\  |
 / \\  |
      |
=========`];

let palavra,dica,reveladas,erros,terminado;

function novaRodada(){{
  const p=banco[Math.floor(Math.random()*banco.length)];
  palavra=p[0]; dica=p[1];
  reveladas=new Set(); erros=0; terminado=false;
  document.getElementById('dica').textContent='💡 Dica: '+dica;
  document.getElementById('msg').textContent='';
  document.getElementById('erros-vis').textContent='';
  document.getElementById('forca').textContent=forcaEtapas[0];
  renderPalavra();
  renderLetras();
}}

function renderPalavra(){{
  document.getElementById('palavra').textContent=
    palavra.split('').map(l=>reveladas.has(l)?l:'_').join(' ');
}}

function renderLetras(){{
  const div=document.getElementById('letras'); div.innerHTML='';
  'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').forEach(l=>{{
    const b=document.createElement('div'); b.className='letra';
    b.textContent=l;
    const acertou=reveladas.has(l)&&palavra.includes(l);
    const errou=reveladas.has(l)&&!palavra.includes(l);
    if(acertou) b.classList.add('acerto','usada');
    else if(errou) b.classList.add('erro','usada');
    else b.onclick=()=>chutar(l);
    div.appendChild(b);
  }});
}}

function chutar(l){{
  if(terminado||reveladas.has(l)) return;
  reveladas.add(l);
  if(!palavra.includes(l)){{
    erros++;
    document.getElementById('erros-vis').textContent=`Erros: ${{erros}}/6`;
    document.getElementById('forca').textContent=forcaEtapas[erros];
  }}
  renderPalavra(); renderLetras();
  const ganhou=palavra.split('').every(l=>reveladas.has(l));
  if(ganhou){{terminado=true;document.getElementById('msg').textContent='🎉 Acertou! Parabéns!';}}
  else if(erros>=6){{
    terminado=true;
    document.getElementById('msg').textContent=`💀 Era: ${{palavra}}`;
    document.getElementById('palavra').textContent=palavra.split('').join(' ');
  }}
}}

novaRodada();
</script></body></html>
"""


def html_digitacao(nome_aluno: str) -> str:
    frases = [
        "variavel recebe valor inteiro",
        "se condicao entao execute bloco",
        "para cada elemento no array faca",
        "funcao retorna resultado calculado",
        "enquanto loop nao terminar repita",
        "classe herda propriedades da pai",
        "objeto instancia metodo publico",
        "algoritmo resolve problema eficiente",
        "compilador traduz codigo para binario",
        "debugar encontrar e corrigir erros",
        "array armazena varios valores juntos",
        "booleano verdadeiro ou falso apenas",
    ]
    import json as _json
    frases_json = _json.dumps(frases)
    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  body{{margin:0;background:#1a1a2e;display:flex;flex-direction:column;
       align-items:center;font-family:'Segoe UI',sans-serif;color:#eee;
       padding:16px;box-sizing:border-box;min-height:500px;}}
  h2{{color:#E30613;margin:4px 0 2px;font-size:1.1rem;}}
  #stats{{font-size:.85rem;color:#aaa;margin:4px 0 12px;display:flex;gap:20px;}}
  .stat{{text-align:center;}} .stat span{{display:block;font-size:1.3rem;
  font-weight:700;color:#00ff88;}}
  #frase-box{{background:#16213e;border-radius:10px;padding:16px 20px;
              width:420px;max-width:95vw;font-size:1.1rem;line-height:1.8;
              letter-spacing:.03em;margin-bottom:14px;min-height:3.5rem;}}
  .l-ok{{color:#00ff88;}} .l-err{{color:#E30613;background:#2a0000;border-radius:2px;}}
  .l-cur{{border-bottom:2px solid #ffc107;}} .l-pend{{color:#555;}}
  #input{{width:420px;max-width:95vw;padding:10px 14px;background:#0f0f23;
          border:2px solid #2a2a5e;border-radius:8px;color:#eee;
          font-size:1rem;outline:none;box-sizing:border-box;}}
  #input:focus{{border-color:#E30613;}}
  #msg{{font-size:.9rem;color:#ffc107;min-height:1.3em;margin:8px 0;text-align:center;}}
  button{{background:#E30613;color:#fff;border:none;border-radius:6px;
          padding:8px 24px;font-size:.95rem;cursor:pointer;margin-top:8px;}}
  button:hover{{background:#c0000f;}}
</style></head><body>
<h2>⌨️ Digitação Rápida — {nome_aluno}</h2>
<div id="stats">
  <div class="stat"><span id="wpm">—</span>WPM</div>
  <div class="stat"><span id="acc">—</span>Precisão</div>
  <div class="stat"><span id="rec">—</span>Recorde</div>
</div>
<div id="frase-box"></div>
<input id="input" placeholder="Aguardando..." autocomplete="off" spellcheck="false">
<div id="msg">Digite a frase acima para começar</div>
<button onclick="novaFrase()">🔄 Nova Frase</button>
<script>
const frases={frases_json};
let frase,inicio,terminado,recorde=0,errosTotal;

function novaFrase(){{
  frase=frases[Math.floor(Math.random()*frases.length)];
  inicio=null; terminado=false; errosTotal=0;
  document.getElementById('input').value='';
  document.getElementById('input').disabled=false;
  document.getElementById('input').focus();
  document.getElementById('msg').textContent='Digite a frase acima para começar';
  document.getElementById('wpm').textContent='—';
  document.getElementById('acc').textContent='—';
  render('');
}}

function render(digitado){{
  const box=document.getElementById('frase-box');
  box.innerHTML=frase.split('').map((c,i)=>{{
    if(i<digitado.length){{
      return digitado[i]===c
        ?`<span class="l-ok">${{c}}</span>`
        :`<span class="l-err">${{c==' '?'·':c}}</span>`;
    }}
    if(i===digitado.length) return `<span class="l-cur">${{c}}</span>`;
    return `<span class="l-pend">${{c}}</span>`;
  }}).join('');
}}

document.getElementById('input').addEventListener('input',e=>{{
  if(terminado) return;
  const v=e.target.value;
  if(!inicio&&v.length>0) inicio=Date.now();
  render(v);

  // conta erros cumulativos
  let err=0;
  for(let i=0;i<v.length;i++) if(v[i]!==frase[i]) err++;
  errosTotal=err;

  if(v===frase){{
    terminado=true;
    const seg=(Date.now()-inicio)/1000;
    const palavras=frase.trim().split(' ').length;
    const wpm=Math.round(palavras/(seg/60));
    const acc=Math.round((1-errosTotal/frase.length)*100);
    if(wpm>recorde) recorde=wpm;
    document.getElementById('wpm').textContent=wpm;
    document.getElementById('acc').textContent=acc+'%';
    document.getElementById('rec').textContent=recorde;
    document.getElementById('msg').textContent=
      `✅ ${{seg.toFixed(1)}}s — ${{wpm>=50?'🔥 Incrível!':wpm>=30?'👏 Bom!':'💪 Continue praticando!'}}`;
    document.getElementById('input').disabled=true;
  }}
}});

document.getElementById('input').addEventListener('keydown',e=>{{
  if(e.key==='Enter'&&terminado) novaFrase();
}});

novaFrase();
</script></body></html>
"""


def render_jogo(jogo_key: str, nome_aluno: str, altura: int = 560):
    """Renderiza o jogo na tela do Streamlit."""
    import streamlit.components.v1 as components
    geradores = {
        "snake":     html_snake,
        "memoria":   html_memoria,
        "quiz":      html_quiz,
        "forca":     html_forca,
        "digitacao": html_digitacao,
    }
    fn = geradores.get(jogo_key)
    if fn:
        components.html(fn(nome_aluno), height=altura, scrolling=False)
