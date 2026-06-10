"""
db_avaliacao.py — Camada de dados do Sistema de Avaliações SENAI

Modo LOCAL  (desenvolvimento): SQLite via libsql_client file://
Modo TURSO  (produção):        libsql_client com URL + token do Turso

Configuração em .streamlit/secrets.toml:
    [turso]
    url   = "libsql://avaliatec-<usuario>.turso.io"
    token = "eyJ..."

Se as secrets não existirem, usa SQLite local (avaliacao.db).
"""

import os
import threading
import libsql_client

# ─── CONEXÃO ──────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_client: libsql_client.ClientSync | None = None


def _get_client() -> libsql_client.ClientSync:
    global _client
    if _client is not None:
        return _client

    with _lock:
        if _client is not None:
            return _client

        # Tenta carregar secrets do Streamlit (produção)
        try:
            import streamlit as st
            url   = st.secrets["turso"]["url"]
            token = st.secrets["turso"]["token"]
            # libsql_client precisa de https:// não libsql://
            url = url.replace("libsql://", "https://")
            _client = libsql_client.create_client_sync(url=url, auth_token=token)
            return _client
        except Exception:
            pass

        # Fallback: SQLite local
        db_path = os.path.join(os.path.dirname(__file__), "avaliacao.db")
        _client = libsql_client.create_client_sync(url=f"file:{db_path}")
        return _client


def ex(sql: str, params=None):
    """Executa uma query e retorna ResultSet."""
    c = _get_client()
    with _lock:
        if params:
            return c.execute(sql, list(params))
        return c.execute(sql)


def ex_many(stmts: list):
    """Executa múltiplos statements em batch (DDL / migrations)."""
    c = _get_client()
    with _lock:
        c.batch(stmts)


def fetchone(sql: str, params=None):
    rs = ex(sql, params)
    return dict(zip(rs.columns, rs.rows[0])) if rs.rows else None


def fetchall(sql: str, params=None):
    rs = ex(sql, params)
    return [dict(zip(rs.columns, row)) for row in rs.rows]


def lastrowid(sql: str, params=None) -> int:
    """INSERT com RETURNING id — retorna o id inserido."""
    # Adiciona RETURNING id se não tiver
    sql_r = sql.rstrip().rstrip(';')
    if 'RETURNING' not in sql_r.upper():
        sql_r += ' RETURNING id'
    rs = ex(sql_r, params)
    return rs.rows[0][0] if rs.rows else 0


# ─── INIT ─────────────────────────────────────────────────────────────────────

def init_db():
    ex_many([
        """CREATE TABLE IF NOT EXISTS provas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT,
            tempo_minutos INTEGER DEFAULT 60,
            status TEXT DEFAULT 'configurando',
            ordem_aleatoria INTEGER DEFAULT 0,
            alternativas_aleatorias INTEGER DEFAULT 0,
            navegacao_livre INTEGER DEFAULT 0,
            jogo_espera TEXT DEFAULT 'none',
            senha_professor TEXT DEFAULT 'senai123',
            criada_em TEXT DEFAULT (datetime('now','localtime')),
            atualizada_em TEXT DEFAULT (datetime('now','localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS alunos_turma (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prova_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            matricula TEXT,
            UNIQUE(prova_id, nome)
        )""",
        """CREATE TABLE IF NOT EXISTS questoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prova_id INTEGER NOT NULL,
            numero_original INTEGER,
            tipo TEXT NOT NULL,
            enunciado TEXT NOT NULL,
            gabarito_dissertativa TEXT,
            peso REAL DEFAULT 1.0
        )""",
        """CREATE TABLE IF NOT EXISTS alternativas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            questao_id INTEGER NOT NULL,
            letra TEXT NOT NULL,
            texto TEXT NOT NULL,
            correta INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS afirmativas_vf (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            questao_id INTEGER NOT NULL,
            letra TEXT NOT NULL,
            texto TEXT NOT NULL,
            gabarito TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS sessoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prova_id INTEGER NOT NULL,
            nome_aluno TEXT NOT NULL,
            ordem_questoes TEXT,
            status TEXT DEFAULT 'em_andamento',
            motivo_envio TEXT,
            nota_final REAL,
            total_questoes INTEGER DEFAULT 0,
            total_respondidas INTEGER DEFAULT 0,
            iniciada_em TEXT DEFAULT (datetime('now','localtime')),
            enviada_em TEXT,
            UNIQUE(prova_id, nome_aluno)
        )""",
        """CREATE TABLE IF NOT EXISTS respostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sessao_id INTEGER NOT NULL,
            questao_id INTEGER NOT NULL,
            alternativa_id INTEGER,
            resposta_texto TEXT,
            marcada_revisao INTEGER DEFAULT 0,
            status_resposta TEXT DEFAULT 'rascunho',
            salva_em TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(sessao_id, questao_id)
        )""",
        """CREATE TABLE IF NOT EXISTS respostas_vf (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sessao_id INTEGER NOT NULL,
            questao_id INTEGER NOT NULL,
            afirmativa_id INTEGER NOT NULL,
            resposta TEXT,
            salva_em TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(sessao_id, afirmativa_id)
        )""",
    ])


# ─── PROVAS ───────────────────────────────────────────────────────────────────

def criar_prova(titulo, descricao, tempo_minutos, senha_professor, jogo_espera='none'):
    return lastrowid("""
        INSERT INTO provas (titulo, descricao, tempo_minutos, senha_professor, jogo_espera)
        VALUES (?, ?, ?, ?, ?)
    """, [titulo, descricao, tempo_minutos, senha_professor, jogo_espera])


def listar_provas():
    return fetchall("SELECT * FROM provas ORDER BY criada_em DESC")


def get_prova(prova_id):
    return fetchone("SELECT * FROM provas WHERE id=?", [prova_id])


# Cache leve para get_prova — evita rebuscar no Turso a cada rerun da sala de espera
_cache_prova: dict = {}
_cache_prova_ts: dict = {}

def get_prova_cached(prova_id, ttl_seg=6):
    """Versão cacheada de get_prova — usa cache por até ttl_seg segundos."""
    import time as _t
    agora = _t.time()
    if (prova_id in _cache_prova and
            agora - _cache_prova_ts.get(prova_id, 0) < ttl_seg):
        return _cache_prova[prova_id]
    prova = get_prova(prova_id)
    _cache_prova[prova_id] = prova
    _cache_prova_ts[prova_id] = agora
    return prova


def invalidar_cache_prova(prova_id):
    """Chama após mudança de status para forçar releitura."""
    _cache_prova.pop(prova_id, None)
    _cache_prova_ts.pop(prova_id, None)


def atualizar_config_prova(prova_id, ordem_aleatoria, alternativas_aleatorias,
                            navegacao_livre, jogo_espera='none'):
    ex("""UPDATE provas SET ordem_aleatoria=?, alternativas_aleatorias=?,
        navegacao_livre=?, jogo_espera=?,
        atualizada_em=datetime('now','localtime') WHERE id=?""",
       [int(ordem_aleatoria), int(alternativas_aleatorias),
        int(navegacao_livre), jogo_espera, prova_id])


def atualizar_status_prova(prova_id, status):
    ex("""UPDATE provas SET status=?,
        atualizada_em=datetime('now','localtime') WHERE id=?""",
       [status, prova_id])
    invalidar_cache_prova(prova_id)


def deletar_prova(prova_id):
    # Deleta manualmente em cascata (Turso não garante FK cascade)
    sessoes = fetchall("SELECT id FROM sessoes WHERE prova_id=?", [prova_id])
    for s in sessoes:
        ex("DELETE FROM respostas WHERE sessao_id=?", [s['id']])
        ex("DELETE FROM respostas_vf WHERE sessao_id=?", [s['id']])
    ex("DELETE FROM sessoes WHERE prova_id=?", [prova_id])
    questoes = fetchall("SELECT id FROM questoes WHERE prova_id=?", [prova_id])
    for q in questoes:
        ex("DELETE FROM alternativas WHERE questao_id=?", [q['id']])
        ex("DELETE FROM afirmativas_vf WHERE questao_id=?", [q['id']])
    ex("DELETE FROM questoes WHERE prova_id=?", [prova_id])
    ex("DELETE FROM alunos_turma WHERE prova_id=?", [prova_id])
    ex("DELETE FROM provas WHERE id=?", [prova_id])


# ─── ALUNOS DA TURMA ──────────────────────────────────────────────────────────

def importar_lista_alunos(prova_id: int, alunos: list):
    ex("DELETE FROM alunos_turma WHERE prova_id=?", [prova_id])
    for a in alunos:
        nome = str(a.get('nome', '')).strip().upper()
        mat  = str(a.get('matricula', '')).strip() if a.get('matricula') else None
        if nome:
            try:
                ex("INSERT INTO alunos_turma (prova_id, nome, matricula) VALUES (?,?,?)",
                   [prova_id, nome, mat])
            except Exception:
                pass


def listar_alunos_turma(prova_id: int) -> list:
    return [r['nome'] for r in
            fetchall("SELECT nome FROM alunos_turma WHERE prova_id=? ORDER BY nome",
                     [prova_id])]


def get_aluno_turma(prova_id: int, nome: str):
    return fetchone("SELECT * FROM alunos_turma WHERE prova_id=? AND nome=?",
                    [prova_id, nome.strip().upper()])


def buscar_alunos_turma(prova_id: int, fragmento: str) -> list:
    return fetchall(
        "SELECT nome, matricula FROM alunos_turma "
        "WHERE prova_id=? AND nome LIKE ? ORDER BY nome LIMIT 8",
        [prova_id, f"%{fragmento.upper()}%"]
    )


def aluno_sessao_ativa(prova_id: int, nome: str) -> bool:
    r = fetchone("""SELECT id FROM sessoes
        WHERE prova_id=? AND nome_aluno=? AND status='em_andamento'""",
        [prova_id, nome.strip().upper()])
    return r is not None


# ─── QUESTÕES ─────────────────────────────────────────────────────────────────

def inserir_questao(prova_id, numero_original, tipo, enunciado, peso,
                    gabarito_dissertativa=None):
    return lastrowid("""
        INSERT INTO questoes (prova_id, numero_original, tipo, enunciado,
                              peso, gabarito_dissertativa)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [prova_id, numero_original, tipo, enunciado, peso, gabarito_dissertativa])


def inserir_alternativa(questao_id, letra, texto, correta):
    ex("INSERT INTO alternativas (questao_id, letra, texto, correta) VALUES (?,?,?,?)",
       [questao_id, letra, texto, int(correta)])


def get_questoes_prova(prova_id):
    return fetchall("SELECT * FROM questoes WHERE prova_id=? ORDER BY numero_original",
                    [prova_id])


def get_alternativas_questao(questao_id):
    return fetchall("SELECT * FROM alternativas WHERE questao_id=? ORDER BY letra",
                    [questao_id])


def inserir_afirmativa_vf(questao_id, letra, texto, gabarito):
    return lastrowid(
        "INSERT INTO afirmativas_vf (questao_id, letra, texto, gabarito) VALUES (?,?,?,?)",
        [questao_id, letra, texto, gabarito]
    )


def get_afirmativas_questao(questao_id):
    return fetchall("""
        SELECT * FROM afirmativas_vf WHERE questao_id=?
        ORDER BY CASE letra
            WHEN 'I' THEN 1 WHEN 'II' THEN 2
            WHEN 'III' THEN 3 WHEN 'IV' THEN 4
            ELSE 5 END
    """, [questao_id])


def deletar_questoes_prova(prova_id):
    questoes = fetchall("SELECT id FROM questoes WHERE prova_id=?", [prova_id])
    for q in questoes:
        ex("DELETE FROM alternativas WHERE questao_id=?", [q['id']])
        ex("DELETE FROM afirmativas_vf WHERE questao_id=?", [q['id']])
    ex("DELETE FROM questoes WHERE prova_id=?", [prova_id])


# ─── SESSÕES ──────────────────────────────────────────────────────────────────

def criar_ou_recuperar_sessao(prova_id, nome_aluno, ordem_questoes_json, total_questoes):
    existing = get_sessao_por_aluno(prova_id, nome_aluno)
    if existing:
        return existing
    sid = lastrowid("""
        INSERT INTO sessoes (prova_id, nome_aluno, ordem_questoes, status,
                             total_questoes, iniciada_em)
        VALUES (?, ?, ?, 'em_andamento', ?, datetime('now','localtime'))
    """, [prova_id, nome_aluno, ordem_questoes_json, total_questoes])
    return get_sessao(sid)


def get_sessao(sessao_id):
    return fetchone("SELECT * FROM sessoes WHERE id=?", [sessao_id])


def get_sessao_por_aluno(prova_id, nome_aluno):
    return fetchone("SELECT * FROM sessoes WHERE prova_id=? AND nome_aluno=?",
                    [prova_id, nome_aluno])


def listar_sessoes_prova(prova_id):
    return fetchall("SELECT * FROM sessoes WHERE prova_id=? ORDER BY nome_aluno",
                    [prova_id])


def enviar_prova_aluno(sessao_id, motivo='manual'):
    obj = fetchone(
        "SELECT COUNT(*) AS n FROM respostas WHERE sessao_id=? AND "
        "(alternativa_id IS NOT NULL OR "
        "(resposta_texto IS NOT NULL AND resposta_texto != ''))",
        [sessao_id]
    )
    vf = fetchone("""
        SELECT COUNT(DISTINCT q.id) AS n
        FROM respostas_vf rv
        JOIN afirmativas_vf af ON af.id = rv.afirmativa_id
        JOIN questoes q ON q.id = af.questao_id
        WHERE rv.sessao_id=? AND rv.resposta IS NOT NULL
    """, [sessao_id])
    total = (obj['n'] if obj else 0) + (vf['n'] if vf else 0)
    ex("""UPDATE sessoes SET status='enviada', motivo_envio=?,
          enviada_em=datetime('now','localtime'), total_respondidas=?
          WHERE id=?""", [motivo, total, sessao_id])


def liberar_nota_aluno(sessao_id, nota_final):
    ex("UPDATE sessoes SET status='nota_liberada', nota_final=? WHERE id=?",
       [nota_final, sessao_id])


# ─── PAUSA / TEMPO EXTRA / RESET ──────────────────────────────────────────────

def pausar_sessao(sessao_id):
    """Registra o momento da pausa."""
    ex("""UPDATE sessoes SET pausado_em=datetime('now','localtime') WHERE id=?
          AND pausado_em IS NULL""", [sessao_id])


def retomar_sessao(sessao_id):
    """Calcula tempo pausado acumulado e limpa pausado_em."""
    s = fetchone("SELECT pausado_em, tempo_pausado_seg FROM sessoes WHERE id=?",
                 [sessao_id])
    if not s or not s.get('pausado_em'):
        return
    from datetime import datetime
    try:
        pausado = datetime.strptime(s['pausado_em'], '%Y-%m-%d %H:%M:%S')
        seg = int((datetime.now() - pausado).total_seconds())
        acumulado = (s.get('tempo_pausado_seg') or 0) + seg
        ex("""UPDATE sessoes SET pausado_em=NULL, tempo_pausado_seg=? WHERE id=?""",
           [acumulado, sessao_id])
    except Exception:
        ex("UPDATE sessoes SET pausado_em=NULL WHERE id=?", [sessao_id])


def pausar_todos(prova_id):
    sessoes = fetchall(
        "SELECT id FROM sessoes WHERE prova_id=? AND status='em_andamento'",
        [prova_id])
    for s in sessoes:
        pausar_sessao(s['id'])


def retomar_todos(prova_id):
    sessoes = fetchall(
        "SELECT id FROM sessoes WHERE prova_id=? AND status='em_andamento'",
        [prova_id])
    for s in sessoes:
        retomar_sessao(s['id'])


def adicionar_tempo_extra(sessao_id, minutos: int):
    s = fetchone("SELECT tempo_extra_min FROM sessoes WHERE id=?", [sessao_id])
    atual = (s.get('tempo_extra_min') or 0) if s else 0
    ex("UPDATE sessoes SET tempo_extra_min=? WHERE id=?",
       [atual + minutos, sessao_id])


def adicionar_tempo_todos(prova_id, minutos: int):
    sessoes = fetchall(
        "SELECT id FROM sessoes WHERE prova_id=? AND status='em_andamento'",
        [prova_id])
    for s in sessoes:
        adicionar_tempo_extra(s['id'], minutos)


def resetar_sessao(sessao_id):
    """Apaga respostas e volta a sessão para em_andamento do zero."""
    ex("DELETE FROM respostas WHERE sessao_id=?", [sessao_id])
    ex("DELETE FROM respostas_vf WHERE sessao_id=?", [sessao_id])

    # Reconstrói a ordem das questões
    s = fetchone("SELECT prova_id FROM sessoes WHERE id=?", [sessao_id])
    if s:
        import json as _json
        questoes = fetchall(
            "SELECT id FROM questoes WHERE prova_id=? ORDER BY numero_original",
            [s['prova_id']]
        )
        ids = [q['id'] for q in questoes]
        ordem_json = _json.dumps(ids)
    else:
        ordem_json = '[]'

    ex("""UPDATE sessoes SET
          status='em_andamento',
          enviada_em=NULL,
          nota_final=NULL,
          total_respondidas=0,
          motivo_envio=NULL,
          pausado_em=NULL,
          tempo_pausado_seg=0,
          tempo_extra_min=0,
          ordem_questoes=?,
          total_questoes=?,
          iniciada_em=datetime('now','localtime')
          WHERE id=?""",
       [ordem_json, len(ids) if s else 0, sessao_id])


# ─── RESPOSTAS ────────────────────────────────────────────────────────────────

def salvar_resposta(sessao_id, questao_id, alternativa_id=None, resposta_texto=None,
                    marcada_revisao=False, status_resposta='rascunho'):
    ex("""
        INSERT INTO respostas
            (sessao_id, questao_id, alternativa_id, resposta_texto,
             marcada_revisao, status_resposta, salva_em)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(sessao_id, questao_id) DO UPDATE SET
            alternativa_id=excluded.alternativa_id,
            resposta_texto=excluded.resposta_texto,
            marcada_revisao=excluded.marcada_revisao,
            status_resposta=excluded.status_resposta,
            salva_em=excluded.salva_em
    """, [sessao_id, questao_id, alternativa_id, resposta_texto,
          int(marcada_revisao), status_resposta])


def get_respostas_sessao(sessao_id):
    rows = fetchall("SELECT * FROM respostas WHERE sessao_id=?", [sessao_id])
    return {r['questao_id']: r for r in rows}


def salvar_resposta_vf(sessao_id, questao_id, afirmativa_id, resposta):
    ex("""
        INSERT INTO respostas_vf
            (sessao_id, questao_id, afirmativa_id, resposta, salva_em)
        VALUES (?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(sessao_id, afirmativa_id) DO UPDATE SET
            resposta=excluded.resposta,
            salva_em=excluded.salva_em
    """, [sessao_id, questao_id, afirmativa_id, resposta])


def get_respostas_vf_sessao(sessao_id):
    rows = fetchall(
        "SELECT afirmativa_id, resposta FROM respostas_vf WHERE sessao_id=?",
        [sessao_id]
    )
    return {r['afirmativa_id']: r['resposta'] for r in rows}


# ─── CORREÇÃO ─────────────────────────────────────────────────────────────────

def corrigir_objetivas(sessao_id):
    rows = fetchall("""
        SELECT r.questao_id, r.alternativa_id, q.peso, a.correta
        FROM respostas r
        JOIN questoes q ON q.id = r.questao_id
        LEFT JOIN alternativas a ON a.id = r.alternativa_id
        WHERE r.sessao_id=? AND q.tipo='objetiva'
    """, [sessao_id])
    acertos = total = 0.0
    detalhes = []
    for r in rows:
        total += r['peso']
        ok = bool(r['correta'])
        if ok: acertos += r['peso']
        detalhes.append({'questao_id': r['questao_id'], 'acertou': ok, 'peso': r['peso']})
    return acertos, total, detalhes


def corrigir_vf(sessao_id, prova_id):
    questoes = fetchall(
        "SELECT * FROM questoes WHERE prova_id=? AND tipo='vf'", [prova_id])
    acertos = total = 0.0
    for q in questoes:
        afs = get_afirmativas_questao(q['id'])
        if not afs: continue
        total += q['peso']
        ponto = q['peso'] / len(afs)
        for af in afs:
            resp = fetchone(
                "SELECT resposta FROM respostas_vf WHERE sessao_id=? AND afirmativa_id=?",
                [sessao_id, af['id']]
            )
            if resp and resp['resposta'] == af['gabarito']:
                acertos += ponto
    return acertos, total


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

def dashboard_prova(prova_id):
    total_questoes = fetchone(
        "SELECT COUNT(*) AS n FROM questoes WHERE prova_id=?", [prova_id])['n']

    sessoes_raw = fetchall("""
        SELECT id, nome_aluno, status, nota_final, enviada_em,
               total_questoes, motivo_envio
        FROM sessoes WHERE prova_id=? ORDER BY nome_aluno
    """, [prova_id])

    sessoes = []
    for s in sessoes_raw:
        obj = fetchone(
            "SELECT COUNT(*) AS n FROM respostas WHERE sessao_id=? AND "
            "(alternativa_id IS NOT NULL OR "
            "(resposta_texto IS NOT NULL AND resposta_texto != ''))",
            [s['id']]
        )
        vf = fetchone("""
            SELECT COUNT(DISTINCT q.id) AS n
            FROM respostas_vf rv
            JOIN afirmativas_vf af ON af.id = rv.afirmativa_id
            JOIN questoes q ON q.id = af.questao_id
            WHERE rv.sessao_id=? AND rv.resposta IS NOT NULL
        """, [s['id']])
        s['total_respondidas'] = (obj['n'] if obj else 0) + (vf['n'] if vf else 0)
        sessoes.append(s)

    alunos_turma = [r['nome'] for r in fetchall(
        "SELECT nome FROM alunos_turma WHERE prova_id=? ORDER BY nome", [prova_id])]

    acertos_por_questao = fetchall("""
        SELECT r.questao_id, q.numero_original, q.enunciado,
               COUNT(r.id) AS total_respostas,
               SUM(CASE WHEN a.correta=1 THEN 1 ELSE 0 END) AS acertos
        FROM respostas r
        JOIN questoes q ON q.id = r.questao_id
        JOIN sessoes s ON s.id = r.sessao_id
        LEFT JOIN alternativas a ON a.id = r.alternativa_id
        WHERE s.prova_id=? AND q.tipo='objetiva'
              AND s.status IN ('enviada','nota_liberada')
        GROUP BY r.questao_id ORDER BY q.numero_original
    """, [prova_id])

    return {
        'sessoes': sessoes,
        'total_questoes': total_questoes,
        'acertos_por_questao': acertos_por_questao,
        'alunos_turma': alunos_turma,
    }


def _corrigir_e_liberar_sessao(sessao_id, total_peso):
    acertos_obj, _, _ = corrigir_objetivas(sessao_id)
    acertos_vf, _    = corrigir_vf(sessao_id,
        fetchone("SELECT prova_id FROM sessoes WHERE id=?", [sessao_id])['prova_id'])
    nota = round(((acertos_obj + acertos_vf) / total_peso * 10)
                 if total_peso > 0 else 0, 1)
    liberar_nota_aluno(sessao_id, nota)
    return nota


# ─── ANÁLISE POR QUESTÃO (Excel) ──────────────────────────────────────────────

def gerar_analise_questoes(prova_id: int) -> list:
    questoes = get_questoes_prova(prova_id)
    sessoes_ids = [r['id'] for r in fetchall("""
        SELECT id FROM sessoes
        WHERE prova_id=? AND status IN ('enviada','nota_liberada')
    """, [prova_id])]
    total_alunos = len(sessoes_ids)
    analise = []

    for q in questoes:
        item = {
            'numero': q['numero_original'], 'enunciado': q['enunciado'],
            'tipo': q['tipo'], 'peso': q['peso'],
            'total_alunos': total_alunos,
            'acertos': 0, 'erros': 0, 'taxa_acerto': 0.0,
            'afirmativas': [],
        }

        if q['tipo'] == 'vf' and sessoes_ids:
            afs = get_afirmativas_questao(q['id'])
            for af in afs:
                ac = er = 0
                for sid in sessoes_ids:
                    r = fetchone(
                        "SELECT resposta FROM respostas_vf "
                        "WHERE sessao_id=? AND afirmativa_id=?",
                        [sid, af['id']]
                    )
                    if r:
                        if r['resposta'] == af['gabarito']: ac += 1
                        else: er += 1
                taxa = round(ac / total_alunos * 100, 1) if total_alunos else 0
                item['afirmativas'].append({
                    'letra': af['letra'], 'texto': af['texto'],
                    'gabarito': af['gabarito'],
                    'acertos': ac, 'erros': er, 'taxa': taxa,
                })
            if afs and total_alunos:
                completos = sum(
                    1 for sid in sessoes_ids
                    if all(
                        (fetchone("SELECT resposta FROM respostas_vf "
                                  "WHERE sessao_id=? AND afirmativa_id=?",
                                  [sid, af['id']]) or {}).get('resposta') == af['gabarito']
                        for af in afs
                    )
                )
                item['acertos'] = completos
                item['erros']   = total_alunos - completos
                item['taxa_acerto'] = round(completos / total_alunos * 100, 1)

        elif q['tipo'] == 'objetiva' and sessoes_ids:
            for sid in sessoes_ids:
                r = fetchone("""
                    SELECT a.correta FROM respostas r
                    JOIN alternativas a ON a.id = r.alternativa_id
                    WHERE r.sessao_id=? AND r.questao_id=?
                """, [sid, q['id']])
                if r:
                    if r['correta']: item['acertos'] += 1
                    else:            item['erros']   += 1
            if total_alunos:
                item['taxa_acerto'] = round(item['acertos'] / total_alunos * 100, 1)

        elif q['tipo'] == 'dissertativa' and sessoes_ids:
            ids_str = ','.join('?' * len(sessoes_ids))
            r = fetchone(
                f"SELECT COUNT(*) AS n FROM respostas "
                f"WHERE questao_id=? AND sessao_id IN ({ids_str}) "
                f"AND resposta_texto IS NOT NULL AND resposta_texto != ''",
                [q['id']] + sessoes_ids
            )
            resp = r['n'] if r else 0
            item['acertos'] = resp
            item['erros']   = total_alunos - resp
            item['taxa_acerto'] = round(resp / total_alunos * 100, 1) if total_alunos else 0

        analise.append(item)
    return analise


# ─── EXPORT EXCEL ─────────────────────────────────────────────────────────────

def gerar_dados_export(prova_id: int) -> list:
    questoes = get_questoes_prova(prova_id)
    alunos_turma = listar_alunos_turma(prova_id)
    sessoes_raw  = listar_sessoes_prova(prova_id)
    sessoes_map  = {s['nome_aluno']: s for s in sessoes_raw}

    respostas_obj = {}
    respostas_vf_map = {}
    for s in sessoes_raw:
        rows = fetchall("""
            SELECT r.*, q.numero_original, q.tipo, q.enunciado, q.peso,
                   a.texto AS alt_texto, a.correta
            FROM respostas r
            JOIN questoes q ON q.id=r.questao_id
            LEFT JOIN alternativas a ON a.id=r.alternativa_id
            WHERE r.sessao_id=?
        """, [s['id']])
        respostas_obj[s['id']] = {r['numero_original']: r for r in rows}

        vf = fetchall("""
            SELECT rv.afirmativa_id, rv.resposta, af.questao_id,
                   af.letra, af.gabarito, q.numero_original
            FROM respostas_vf rv
            JOIN afirmativas_vf af ON af.id = rv.afirmativa_id
            JOIN questoes q ON q.id = af.questao_id
            WHERE rv.sessao_id=?
        """, [s['id']])
        respostas_vf_map[s['id']] = vf

    fonte = alunos_turma if alunos_turma else sorted(sessoes_map.keys())
    linhas = []

    def _montar(nome, sessao):
        if sessao is None:
            return {'Nome': nome, 'Status': 'Não logou', 'Nota': '',
                    'Respondidas': '', 'Total Questões': len(questoes),
                    'Enviada em': '', 'Motivo Envio': ''}
        sm = {'em_andamento': 'Logou — não enviou', 'enviada': 'Enviada',
              'nota_liberada': 'Nota liberada'}
        sl = sm.get(sessao['status'], sessao['status'])
        if sessao.get('motivo_envio') == 'tempo_esgotado':
            sl += ' (tempo esgotado)'
        obj = respostas_obj.get(sessao['id'], {})
        vf  = respostas_vf_map.get(sessao['id'], [])
        resp = len(obj) + len(set(r['questao_id'] for r in vf))
        linha = {
            'Nome': nome, 'Status': sl,
            'Nota': sessao['nota_final'] if sessao['nota_final'] is not None else '',
            'Respondidas': f"{resp}/{len(questoes)}",
            'Total Questões': len(questoes),
            'Enviada em': sessao.get('enviada_em') or '',
            'Motivo Envio': sessao.get('motivo_envio') or 'manual',
        }
        for q in questoes:
            n = q['numero_original']
            col = f"Q{n} ({q['peso']}pt)"
            if q['tipo'] == 'objetiva':
                r = obj.get(n, {})
                ok = bool(r.get('correta')) if r else None
                linha[col] = ((r.get('alt_texto','—') or '—') +
                              (' ✓' if ok else ' ✗' if ok is False else '')) if r else '—'
            elif q['tipo'] == 'vf':
                afs = [r for r in vf if r['questao_id'] == q['id']]
                if afs:
                    linha[col] = ' '.join(
                        f"{r['letra']}:{r['resposta']}{'✓' if r['resposta']==r['gabarito'] else '✗'}"
                        for r in sorted(afs, key=lambda x: x['letra'])
                    )
                else:
                    linha[col] = '—'
            else:
                r = obj.get(n, {})
                linha[col] = r.get('resposta_texto','—') or '—'
        return linha

    for nome in fonte:
        linhas.append(_montar(nome, sessoes_map.get(nome)))
    for nome, s in sessoes_map.items():
        if nome not in fonte and nome != '[TESTE PROFESSOR]':
            l = _montar(nome, s)
            l['Nome'] += ' *'; l['Status'] += ' (fora da lista)'
            linhas.append(l)

    return sorted(linhas, key=lambda x: x['Nome'])


# Alias para compatibilidade com avaliacao_app.py
def get_conn():
    """Compatibilidade — retorna objeto com execute() para queries inline no app."""
    class _Compat:
        def execute(self, sql, params=None):
            return type('RS', (), {
                'fetchone': lambda s: fetchone(sql, params),
                'fetchall': lambda s: fetchall(sql, params),
            })()
        def commit(self): pass
        def close(self): pass
    return _Compat()