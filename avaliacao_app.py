"""
avaliacao_app.py — Módulo de Aplicação de Avaliações
Sistema Pedagógico SENAI

Execute com:  streamlit run avaliacao_app.py
"""

import streamlit as st
import json
import random
import time
import io
from datetime import datetime, timedelta

import db_avaliacao as db
from importador_docx import importar_docx, validar_questoes
from jogos_espera import render_jogo, JOGOS_DISPONIVEIS
from exportar import gerar_excel

# ─── CONFIG ───────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Avaliações SENAI",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="collapsed",
)

db.init_db()

# ─── CSS ──────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Cartão de questão */
.questao-card {
    background: #f8f9fa;
    border-left: 5px solid #E30613;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.questao-numero {
    color: #E30613;
    font-size: 0.85rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.questao-enunciado {
    font-size: 1.05rem;
    line-height: 1.6;
    color: #1a1a1a;
    margin-top: 8px;
}
/* Barra de progresso custom */
.barra-progresso {
    background: #e9ecef;
    border-radius: 20px;
    height: 10px;
    overflow: hidden;
    margin: 8px 0;
}
.barra-fill {
    background: linear-gradient(90deg, #E30613, #ff6b35);
    height: 100%;
    border-radius: 20px;
    transition: width 0.3s ease;
}
/* Cronômetro */
.cronometro {
    font-size: 1.8rem;
    font-weight: 700;
    text-align: center;
    font-family: monospace;
    color: #1a1a1a;
}
.cronometro.aviso {
    color: #E30613;
    animation: pulsar 1s ease-in-out infinite;
}
@keyframes pulsar {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
/* Badge revisão */
.badge-revisao {
    background: #fff3cd;
    color: #856404;
    border: 1px solid #ffc107;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 0.78rem;
    font-weight: 600;
}
/* Status aluno no dash */
.status-aguardando { color: #6c757d; }
.status-em_andamento { color: #0d6efd; }
.status-enviada { color: #198754; }
.status-nota_liberada { color: #6f42c1; }
</style>
""", unsafe_allow_html=True)


# ─── UTILITÁRIOS ──────────────────────────────────────────────────────────────

def fmt_status(status):
    mapa = {
        'aguardando': '⏳ Aguardando',
        'em_andamento': '✏️ Respondendo',
        'enviada': '✅ Enviada',
        'nota_liberada': '🏆 Nota liberada',
        'configurando': '⚙️ Configurando',
        'ativa': '🟢 Ativa',
        'encerrada': '🔴 Encerrada',
        'notas_liberadas': '🏆 Notas liberadas',
    }
    return mapa.get(status, status)


def segundos_para_hms(segundos):
    segundos = max(0, int(segundos))
    h = segundos // 3600
    m = (segundos % 3600) // 60
    s = segundos % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


# ─── HELPERS DE LOGIN DO ALUNO ────────────────────────────────────────────────

def _validar_entrada_aluno(prova_id: int, nome: str, tem_lista: bool) -> list[str]:
    """Retorna lista de erros. Vazio = pode prosseguir."""
    erros = []

    if not nome:
        erros.append("Informe seu nome.")
        return erros

    # Verifica se está na lista oficial
    if tem_lista:
        aluno = db.get_aluno_turma(prova_id, nome)
        if not aluno:
            erros.append(
                f"❌ **{nome}** não está na lista desta prova. "
                "Verifique a escrita ou fale com o professor."
            )
            return erros

    # Sessão ativa — reconexão legítima, entra direto
    if db.aluno_sessao_ativa(prova_id, nome):
        return erros

    # Já entregou — só bloqueia se a prova NÃO estiver mais ativa
    # (se estiver ativa, professor pode ter resetado para o aluno refazer)
    sessao_existente = db.get_sessao_por_aluno(prova_id, nome)
    if sessao_existente and sessao_existente['status'] in ('enviada', 'nota_liberada'):
        prova = db.get_prova(prova_id)
        if prova and prova['status'] == 'ativa':
            # Professor pode ter resetado — deixa tentar entrar
            return erros
        erros.append(
            f"✅ **{nome}** já entregou esta prova. "
            "Aguarde o professor liberar o resultado."
        )
        return erros

    return erros


def _finalizar_login_aluno(nome: str, prova_id: int):
    """Limpa estado de confirmação e entra na prova."""
    st.session_state.pop('aluno_confirmando', None)
    st.session_state.pop('prova_id_confirmando', None)
    st.session_state.pop('_prova_btn_sel', None)
    st.session_state.pop('_sugestao_selecionada', None)
    st.session_state.pop('_digitado_anterior', None)
    st.session_state['perfil'] = 'aluno'
    st.session_state['nome_aluno'] = nome
    st.session_state['prova_id'] = prova_id
    st.rerun()


# ─── TELA INICIAL ─────────────────────────────────────────────────────────────

def tela_inicial():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Logo SENAI em texto (evita dependência de URL externa)
        st.markdown("""
        <div style="text-align:center; margin-bottom:8px;">
            <span style="font-size:2rem; font-weight:900; color:#E30613;
                         letter-spacing:2px; font-family:Arial,sans-serif;">SENAI</span>
            <span style="font-size:.85rem; color:#666; display:block;
                         letter-spacing:1px;">FATESG — Sistema de Avaliações</span>
        </div>
        """, unsafe_allow_html=True)
        st.title("📝 Sistema de Avaliações")
        st.divider()

        perfil = st.radio("Como deseja entrar?", ["👤 Sou Aluno", "🔐 Sou Professor"],
                          horizontal=True, label_visibility="collapsed")

        if perfil == "👤 Sou Aluno":
            st.subheader("Identificação do Aluno")

            # Mostra provas disponíveis para entrada (configurando ou ativa)
            todas_provas = [p for p in db.listar_provas()
                           if p['status'] in ('configurando', 'ativa')]
            if not todas_provas:
                st.info("Nenhuma prova disponível no momento. Aguarde o professor.")
                return

            # Botões com ícone por prova
            st.markdown("**Selecione sua prova:**")
            prova_id = st.session_state.get('_prova_btn_sel')

            cols = st.columns(min(len(todas_provas), 3))
            for ci, p in enumerate(todas_provas):
                ativo      = p['status'] == 'ativa'
                selecionado = prova_id == p['id']
                ico        = "🟢" if ativo else "⏳"
                label_st   = "EM ANDAMENTO" if ativo else "AGUARDANDO"
                borda_cor  = "#198754" if ativo else "#6c757d"
                bg_cor     = "#d4edda" if ativo else "#f8f9fa"
                txt_cor    = "#155724" if ativo else "#495057"
                sel_style  = "outline:3px solid #E30613;" if selecionado else ""

                with cols[ci % 3]:
                    html_card = (
                        f'<div style="border:2px solid {borda_cor}; border-radius:10px;'
                        f' padding:14px; text-align:center; background:{bg_cor};'
                        f' {sel_style} margin-bottom:4px;">'
                        f'<div style="font-size:1.8rem">{ico}</div>'
                        f'<div style="font-weight:700; font-size:.95rem; color:{txt_cor}">'
                        f'{p["titulo"]}</div>'
                        f'<div style="font-size:.75rem; color:{txt_cor}; margin-top:4px">'
                        f'{label_st}</div>'
                        f'</div>'
                    )
                    st.markdown(html_card, unsafe_allow_html=True)
                    btn_label = f"{'✅ ' if selecionado else ''}Entrar nesta prova"
                    if st.button(btn_label, key=f"prova_btn_{p['id']}",
                                 use_container_width=True,
                                 type="primary" if selecionado else "secondary"):
                        st.session_state['_prova_btn_sel'] = p['id']
                        st.rerun()

            if not prova_id:
                st.caption("Clique em uma prova para selecioná-la.")
                return

            prova_id = st.session_state['_prova_btn_sel']
            alunos_lista = db.listar_alunos_turma(prova_id)
            tem_lista = len(alunos_lista) > 0

            # ── Etapa 1: digitar nome ──────────────────────────────────────────
            if 'aluno_confirmando' not in st.session_state:

                digitado = st.text_input(
                    "Digite seu nome",
                    placeholder="Ex: João da Silva",
                    key="input_nome_aluno"
                ).strip().upper()

                # Se o digitado mudou, limpa a sugestão salva
                if digitado != st.session_state.get('_digitado_anterior', ''):
                    st.session_state.pop('_sugestao_selecionada', None)
                st.session_state['_digitado_anterior'] = digitado

                # Autocomplete se há lista cadastrada
                if tem_lista and digitado and len(digitado) >= 2:
                    sugestoes = db.buscar_alunos_turma(prova_id, digitado)
                    if sugestoes:
                        nomes_sug = [s['nome'] for s in sugestoes]
                        if digitado in nomes_sug:
                            nomes_sug = [digitado] + [n for n in nomes_sug if n != digitado]
                        st.caption("💡 Sugestões — clique no seu nome:")
                        cols = st.columns(min(len(nomes_sug), 2))
                        for ci, nome_sug in enumerate(nomes_sug):
                            with cols[ci % 2]:
                                selecionado = st.session_state.get('_sugestao_selecionada') == nome_sug
                                if st.button(
                                    f"{'✅ ' if selecionado else ''}{nome_sug}",
                                    key=f"sug_{ci}",
                                    use_container_width=True,
                                    type="primary" if selecionado else "secondary"
                                ):
                                    st.session_state['_sugestao_selecionada'] = nome_sug
                                    st.rerun()

                # Nome final: sugestão salva tem prioridade sobre o digitado
                nome_para_confirmar = (
                    st.session_state.get('_sugestao_selecionada') or
                    (digitado if digitado else None)
                )

                # Mostra qual nome será confirmado
                if st.session_state.get('_sugestao_selecionada'):
                    st.info(f"✅ Selecionado: **{st.session_state['_sugestao_selecionada']}**")

                if nome_para_confirmar:
                    if st.button("▶️ Confirmar Nome", type="primary",
                                 use_container_width=True, key="btn_confirmar_nome"):
                        erros = _validar_entrada_aluno(prova_id, nome_para_confirmar, tem_lista)
                        if erros:
                            for e in erros:
                                st.error(e)
                        else:
                            # Se já tem sessão em_andamento → reconexão direta sem matrícula
                            sessao_existente = db.get_sessao_por_aluno(
                                prova_id, nome_para_confirmar)
                            if sessao_existente and sessao_existente['status'] == 'em_andamento':
                                st.info("🔄 Reconectando à sua prova...")
                                _finalizar_login_aluno(nome_para_confirmar, prova_id)
                            else:
                                st.session_state['aluno_confirmando'] = nome_para_confirmar
                                st.session_state['prova_id_confirmando'] = prova_id
                                st.session_state.pop('_sugestao_selecionada', None)
                                st.session_state.pop('_digitado_anterior', None)
                                st.rerun()

                if not tem_lista:
                    st.caption("ℹ️ Lista oficial não cadastrada — qualquer nome é aceito.")

            # ── Etapa 2: confirmar identidade com matrícula ───────────────────
            else:
                nome_conf = st.session_state['aluno_confirmando']
                prova_id_conf = st.session_state['prova_id_confirmando']
                aluno_reg = db.get_aluno_turma(prova_id_conf, nome_conf)

                st.success(f"👤 Você é **{nome_conf}**?")

                if aluno_reg and aluno_reg.get('matricula'):
                    st.markdown("Para confirmar, informe sua **matrícula**:")
                    matricula_digitada = st.text_input(
                        "Matrícula", placeholder="Digite sua matrícula",
                        key="input_matricula"
                    ).strip()

                    col_ok, col_voltar = st.columns(2)
                    with col_ok:
                        if st.button("✅ Confirmar e Entrar", type="primary",
                                     use_container_width=True):
                            if matricula_digitada == aluno_reg['matricula']:
                                _finalizar_login_aluno(nome_conf, prova_id_conf)
                            else:
                                st.error("❌ Matrícula incorreta. Verifique e tente novamente.")
                    with col_voltar:
                        if st.button("↩️ Não sou eu", use_container_width=True):
                            st.session_state.pop('aluno_confirmando', None)
                            st.session_state.pop('prova_id_confirmando', None)
                            st.rerun()

                else:
                    # Sem matrícula cadastrada: só confirmação de nome
                    st.info("Confirme que este é o seu nome para entrar na prova.")
                    col_ok, col_voltar = st.columns(2)
                    with col_ok:
                        if st.button("✅ Sim, sou eu! Entrar", type="primary",
                                     use_container_width=True):
                            _finalizar_login_aluno(nome_conf, prova_id_conf)
                    with col_voltar:
                        if st.button("↩️ Não sou eu", use_container_width=True):
                            st.session_state.pop('aluno_confirmando', None)
                            st.session_state.pop('prova_id_confirmando', None)
                            st.rerun()

        else:
            st.subheader("Acesso do Professor")
            senha = st.text_input("Senha", type="password")
            provas = db.listar_provas()

            if provas:
                opcoes = {f"{p['titulo']} ({fmt_status(p['status'])})": p['id'] for p in provas}
                opcoes["➕ Nova prova"] = -1
                prova_sel_label = st.selectbox("Selecione uma prova", list(opcoes.keys()))
                prova_id_sel = opcoes[prova_sel_label]
            else:
                prova_id_sel = -1
                st.info("Nenhuma prova cadastrada. Crie uma nova.")

            if st.button("🔐 Entrar como Professor", type="primary", use_container_width=True):
                if not senha:
                    st.error("Informe a senha.")
                    return

                # Sem provas: qualquer senha padrão entra
                if prova_id_sel == -1:
                    senha_correta = "senai123"
                else:
                    prova = db.get_prova(prova_id_sel)
                    senha_correta = prova['senha_professor'] if prova else "senai123"

                if senha != senha_correta:
                    st.error("❌ Senha incorreta. (padrão: senai123)")
                    return

                st.session_state['perfil'] = 'professor'
                st.session_state['prova_id'] = prova_id_sel
                st.rerun()


# ─── PAINEL PROFESSOR ─────────────────────────────────────────────────────────

def painel_professor():
    prova_id = st.session_state.get('prova_id', -1)

    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding:8px 0 4px;">
            <span style="font-size:1.4rem; font-weight:900; color:#E30613;
                         letter-spacing:2px;">SENAI</span><br>
            <span style="font-size:.72rem; color:#888; letter-spacing:1px;">FATESG</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Painel do Professor")
        st.divider()
        pagina = st.radio("Navegação", [
            "📋 Provas",
            "➕ Nova Prova",
            "📊 Dashboard",
            "✏️ Corrigir Dissertativas",
            "📥 Exportar Excel",
        ], label_visibility="collapsed")
        st.divider()
        if st.button("🚪 Sair", use_container_width=True):
            for k in ['perfil', 'prova_id', 'nome_aluno']:
                st.session_state.pop(k, None)
            st.rerun()

    if pagina == "📋 Provas":
        _professor_provas()
    elif pagina == "➕ Nova Prova":
        _professor_nova_prova()
    elif pagina == "📊 Dashboard":
        _professor_dashboard()
    elif pagina == "✏️ Corrigir Dissertativas":
        _professor_corrigir_dissertativas()
    elif pagina == "📥 Exportar Excel":
        _professor_exportar()


def _professor_provas():
    """Lista de provas com acesso rápido às ações e à configuração."""
    st.header("📋 Provas")

    provas = db.listar_provas()
    if not provas:
        st.info("Nenhuma prova cadastrada. Use **➕ Nova Prova** para começar.")
        return

    for prova in provas:
        questoes = db.get_questoes_prova(prova['id'])
        alunos   = db.listar_alunos_turma(prova['id'])
        sessoes  = db.listar_sessoes_prova(prova['id'])
        enviadas = sum(1 for s in sessoes if s['status'] in ('enviada','nota_liberada'))
        status   = prova['status']

        # Linha de card
        cor_status = {
            'configurando':   '#6c757d',
            'ativa':          '#198754',
            'encerrada':      '#dc3545',
            'notas_liberadas':'#6f42c1',
        }.get(status, '#333')

        st.markdown(f"""
        <div style="border:1px solid #dee2e6; border-left:5px solid {cor_status};
                    border-radius:8px; padding:14px 18px; margin-bottom:10px;
                    background:#fafafa;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-size:1.05rem; font-weight:700;">{prova['titulo']}</span>
                    &nbsp;<span style="font-size:.8rem; color:{cor_status}; font-weight:600;
                    border:1px solid {cor_status}; border-radius:10px; padding:1px 8px;">
                    {fmt_status(status)}</span>
                </div>
                <div style="font-size:.85rem; color:#666;">
                    ⏱️ {prova['tempo_minutos']} min &nbsp;|&nbsp;
                    📌 {len(questoes)} questões &nbsp;|&nbsp;
                    👥 {len(alunos)} alunos &nbsp;|&nbsp;
                    ✅ {enviadas} entregas
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_cfg, col_at, col_enc, col_nota, col_del = st.columns([2, 1, 1, 1, 1])

        with col_cfg:
            if status == 'configurando':
                if st.button("⚙️ Configurar", key=f"cfg_btn_{prova['id']}",
                             use_container_width=True):
                    st.session_state['configurando_prova_id'] = prova['id']
                    st.rerun()
            else:
                st.caption(f"Criada em {prova['criada_em'][:10]}")

        with col_at:
            if status == 'configurando':
                if st.button("🟢 Ativar", key=f"at_{prova['id']}", use_container_width=True):
                    if not questoes:
                        st.error("Adicione questões antes de ativar.")
                    else:
                        db.atualizar_status_prova(prova['id'], 'ativa')
                        st.rerun()

        with col_enc:
            if status == 'ativa':
                if st.button("🔴 Encerrar", key=f"enc_{prova['id']}", use_container_width=True):
                    db.atualizar_status_prova(prova['id'], 'encerrada')
                    st.rerun()

        with col_nota:
            if status == 'encerrada':
                if st.button("🏆 Liberar notas", key=f"lib_{prova['id']}", use_container_width=True):
                    _corrigir_e_liberar_todos(prova['id'])
                    db.atualizar_status_prova(prova['id'], 'notas_liberadas')
                    st.rerun()

        with col_del:
            if status == 'configurando':
                if st.button("🗑️", key=f"del_{prova['id']}", use_container_width=True,
                             help="Excluir prova"):
                    db.deletar_prova(prova['id'])
                    st.rerun()

        st.markdown("<div style='margin-bottom:4px'></div>", unsafe_allow_html=True)

    # Redireciona para tela de configuração se solicitado
    if 'configurando_prova_id' in st.session_state:
        _tela_configuracao_prova(st.session_state['configurando_prova_id'])


def _tela_configuracao_prova(prova_id: int):
    """Tela dedicada e completa de configuração de uma prova."""
    prova = db.get_prova(prova_id)
    if not prova:
        st.session_state.pop('configurando_prova_id', None)
        st.rerun()
        return

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    col_titulo, col_fechar = st.columns([5, 1])
    with col_titulo:
        st.markdown(f"## ⚙️ Configurar — *{prova['titulo']}*")
    with col_fechar:
        if st.button("✖ Fechar", use_container_width=True):
            st.session_state.pop('configurando_prova_id', None)
            st.rerun()

    st.caption("Configure todos os detalhes antes de ativar a prova para os alunos.")

    # Botão de teste rápido — disponível quando há questões
    questoes_check = db.get_questoes_prova(prova_id)
    if questoes_check:
        st.info("💡 **Modo Teste disponível** — você pode simular a prova como aluno antes de ativar.")
        if st.button("🧪 Testar prova agora (modo professor)", use_container_width=True):
            # Limpa sessão de teste anterior
            conn = db.get_conn()
            sessao_teste = conn.execute(
                "SELECT id FROM sessoes WHERE prova_id=? AND nome_aluno='[TESTE PROFESSOR]'",
                (prova_id,)
            ).fetchone()
            if sessao_teste:
                conn.execute("DELETE FROM respostas WHERE sessao_id=?", (sessao_teste['id'],))
                conn.execute("DELETE FROM respostas_vf WHERE sessao_id=?", (sessao_teste['id'],))
                conn.execute("DELETE FROM sessoes WHERE id=?", (sessao_teste['id'],))
                conn.commit()
            conn.close()
            st.session_state['modo_teste'] = True
            st.session_state['perfil'] = 'aluno'
            st.session_state['nome_aluno'] = '[TESTE PROFESSOR]'
            st.session_state['prova_id'] = prova_id
            st.session_state['prova_id_retorno_cfg'] = prova_id
            st.rerun()

    st.divider()

    # ══ SEÇÃO 1 — INFORMAÇÕES GERAIS ═════════════════════════════════════════
    st.markdown("### 📝 1. Informações Gerais")

    with st.form("form_info_geral"):
        col1, col2 = st.columns([3, 1])
        with col1:
            novo_titulo = st.text_input("Título da prova", value=prova['titulo'])
            nova_desc   = st.text_area("Descrição / Observações",
                                       value=prova.get('descricao') or '',
                                       height=80, placeholder="Opcional")
        with col2:
            novo_tempo = st.number_input("Tempo (minutos)", min_value=10,
                                         max_value=240, value=prova['tempo_minutos'], step=5)
            nova_senha = st.text_input("Senha do professor",
                                       value=prova['senha_professor'])

        if st.form_submit_button("💾 Salvar informações", use_container_width=True):
            conn = db.get_conn()
            conn.execute("""UPDATE provas SET titulo=?, descricao=?, tempo_minutos=?,
                senha_professor=?, atualizada_em=datetime('now','localtime') WHERE id=?""",
                (novo_titulo.strip(), nova_desc.strip(), novo_tempo, nova_senha, prova_id))
            conn.commit(); conn.close()
            st.success("✅ Informações salvas.")
            st.rerun()

    st.divider()

    # ══ SEÇÃO 2 — QUESTÕES ═══════════════════════════════════════════════════
    st.markdown("### 📌 2. Questões")

    questoes = db.get_questoes_prova(prova_id)
    if questoes:
        total_pts = sum(q['peso'] for q in questoes)
        col_qa, col_qb, col_qc = st.columns(3)
        col_qa.metric("Questões", len(questoes))
        col_qb.metric("Total de pontos", f"{total_pts:.1f}")
        col_qc.metric("Objetivas / Dissertativas",
                       f"{sum(1 for q in questoes if q['tipo']=='objetiva')} / "
                       f"{sum(1 for q in questoes if q['tipo']=='dissertativa')}")

        with st.expander("Ver questões cadastradas"):
            for q in questoes:
                ico = "🔵" if q['tipo'] == 'objetiva' else "📝"
                st.markdown(f"{ico} **Q{q['numero_original']}** &nbsp; "
                            f"`{q['peso']} pt` — {q['enunciado'][:90]}{'...' if len(q['enunciado'])>90 else ''}")
    else:
        st.warning("Nenhuma questão cadastrada. Importe um arquivo .docx abaixo.")

    col_up1, col_up2 = st.columns(2)
    with col_up1:
        arquivo_docx = st.file_uploader(
            "📄 Arquivo da prova (.docx)",
            type=['docx'],
            key=f"docx_cfg_{prova_id}",
            help="Questões objetivas, VF ou dissertativas"
        )
    with col_up2:
        arquivo_gabarito = st.file_uploader(
            "🗝️ Gabarito (.docx) — para questões V/F",
            type=['docx'],
            key=f"gab_cfg_{prova_id}",
            help="Opcional para objetivas (use * na alternativa). Obrigatório para V/F separado."
        )

    if arquivo_docx:
        if st.button("📥 Importar questões", type="primary", use_container_width=True,
                     key=f"imp_docx_{prova_id}"):
            _importar_questoes(prova_id, arquivo_docx, arquivo_gabarito)

    if questoes:
        if st.button("🗑️ Remover todas as questões", key=f"rem_q_{prova_id}"):
            db.deletar_questoes_prova(prova_id)
            st.success("Questões removidas.")
            st.rerun()

    st.divider()

    # ══ SEÇÃO 3 — LISTA DE ALUNOS ════════════════════════════════════════════
    st.markdown("### 👥 3. Lista de Alunos da Turma")

    alunos = db.listar_alunos_turma(prova_id)

    col_al1, col_al2 = st.columns([1, 1])
    with col_al1:
        if alunos:
            com_mat = sum(1 for a in alunos
                          if db.get_aluno_turma(prova_id, a) and
                          db.get_aluno_turma(prova_id, a).get('matricula'))
            st.success(f"✅ {len(alunos)} aluno(s) cadastrado(s) — "
                       f"{com_mat} com matrícula")
        else:
            st.info("Nenhuma lista importada. Sem lista, qualquer nome é aceito.")

    with col_al2:
        # Modelo para download
        modelo_bytes = _gerar_modelo_lista_xlsx()
        st.download_button(
            "⬇️ Baixar modelo .xlsx",
            data=modelo_bytes,
            file_name="modelo_lista_alunos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Baixe, preencha e importe aqui"
        )

    col_imp1, col_imp2 = st.columns([3, 1])
    with col_imp1:
        lista_file = st.file_uploader(
            "Importar lista (.xlsx ou .csv) — colunas: Nome Completo | Matrícula",
            type=['xlsx', 'xls', 'csv'],
            key=f"lista_cfg_{prova_id}"
        )
    with col_imp2:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if lista_file:
            if st.button("📥 Importar lista", type="primary", use_container_width=True,
                         key=f"imp_lista_{prova_id}"):
                _importar_lista_alunos(prova_id, lista_file)

    if alunos:
        with st.expander(f"Ver lista ({len(alunos)} alunos)"):
            conn = db.get_conn()
            rows = conn.execute(
                "SELECT nome, matricula FROM alunos_turma WHERE prova_id=? ORDER BY nome",
                (prova_id,)
            ).fetchall()
            conn.close()
            for i, r in enumerate(rows, 1):
                mat = r['matricula'] or '—'
                st.write(f"{i:02d}. **{r['nome']}** &nbsp; | &nbsp; Matrícula: `{mat}`")
        if st.button("🗑️ Remover lista", key=f"rem_lista_{prova_id}"):
            conn = db.get_conn()
            conn.execute("DELETE FROM alunos_turma WHERE prova_id=?", (prova_id,))
            conn.commit(); conn.close()
            st.success("Lista removida.")
            st.rerun()

    st.divider()

    # ══ SEÇÃO 4 — CONFIGURAÇÕES DA PROVA ════════════════════════════════════
    st.markdown("### ⚙️ 4. Configurações da Prova")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.markdown("**Ordem das questões**")
        ordem_al = st.checkbox(
            "Questões em ordem aleatória",
            value=bool(prova['ordem_aleatoria']),
            key=f"ord_{prova_id}",
            help="Cada aluno recebe as questões em ordem diferente"
        )
        alt_al = st.checkbox(
            "Alternativas em ordem aleatória",
            value=bool(prova['alternativas_aleatorias']),
            key=f"alt_{prova_id}",
            help="As opções A/B/C/D são embaralhadas por aluno"
        )
        nav_livre = st.checkbox(
            "Permitir navegação livre entre questões",
            value=bool(prova['navegacao_livre']),
            key=f"nav_{prova_id}",
            help="Se desmarcado, o aluno só pode avançar e voltar a questões marcadas para revisão"
        )

    with col_f2:
        st.markdown("**🎮 Jogos na sala de espera**")
        st.caption("O aluno poderá escolher entre os jogos marcados.")

        # Lê jogos já selecionados (suporta formato antigo string e novo JSON)
        jogo_raw = prova.get('jogo_espera', 'none') or 'none'
        try:
            jogos_ativos = json.loads(jogo_raw) if jogo_raw.startswith('[') else (
                [] if jogo_raw == 'none' else [jogo_raw]
            )
        except Exception:
            jogos_ativos = []

        jogos_sel = []
        for key, label in JOGOS_DISPONIVEIS.items():
            checked = st.checkbox(label, value=(key in jogos_ativos),
                                  key=f"jogo_{prova_id}_{key}")
            if checked:
                jogos_sel.append(key)

        jogo_val = json.dumps(jogos_sel) if jogos_sel else 'none'

    if st.button("💾 Salvar configurações", type="primary", use_container_width=True,
                 key=f"salvar_cfg_{prova_id}"):
        db.atualizar_config_prova(prova_id, ordem_al, alt_al, nav_livre, jogo_val)
        st.success("✅ Configurações salvas!")
        st.rerun()

    st.divider()

    # ══ SEÇÃO 5 — REVISAR E ATIVAR ═══════════════════════════════════════════
    st.markdown("### 🚀 5. Revisar e Ativar")

    # Checklist
    checks = [
        ("📌 Questões cadastradas",        len(questoes) > 0,       f"{len(questoes)} questão(ões)"),
        ("👥 Lista de alunos importada",   len(alunos) > 0,         f"{len(alunos)} aluno(s)" if alunos else "Opcional — sem lista qualquer nome é aceito"),
        ("⏱️ Tempo configurado",           prova['tempo_minutos'] > 0, f"{prova['tempo_minutos']} minutos"),
        ("🔐 Senha do professor definida", bool(prova['senha_professor']), "OK"),
    ]

    tudo_ok = True
    for label, ok, detalhe in checks:
        ico  = "✅" if ok else "⚠️"
        cor  = "#198754" if ok else "#856404"
        bg   = "#d4edda" if ok else "#fff3cd"
        if label == "👥 Lista de alunos importada" and not ok:
            pass  # lista é opcional, não bloqueia
        elif not ok and label != "👥 Lista de alunos importada":
            tudo_ok = False
        st.markdown(f"""
        <div style="background:{bg}; border-radius:6px; padding:8px 14px;
                    margin:4px 0; color:{cor}; font-size:.92rem;">
            {ico} <strong>{label}</strong> &nbsp;—&nbsp; {detalhe}
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    if tudo_ok:
        if st.button("🟢 ATIVAR PROVA AGORA", type="primary", use_container_width=True,
                     key=f"ativar_cfg_{prova_id}"):
            db.atualizar_status_prova(prova_id, 'ativa')
            st.session_state.pop('configurando_prova_id', None)
            st.success(f"✅ Prova **{prova['titulo']}** ativada! Os alunos já podem entrar.")
            st.rerun()
    else:
        st.button("🟢 ATIVAR PROVA AGORA", disabled=True, use_container_width=True,
                  key=f"ativar_cfg_dis_{prova_id}",
                  help="Corrija os itens ⚠️ antes de ativar")
        st.caption("Adicione questões para liberar o botão de ativação.")


def _gerar_modelo_lista_xlsx() -> bytes:
    """Gera o modelo .xlsx de lista de alunos em memória."""
    import io as _io
    from openpyxl import Workbook as _WB
    from openpyxl.styles import Font as _F, PatternFill as _P, Alignment as _A, Border as _B, Side as _S

    wb = _WB()
    ws = wb.active
    ws.title = 'Lista de Alunos'
    borda = _B(left=_S(style='thin',color='CCCCCC'), right=_S(style='thin',color='CCCCCC'),
               top=_S(style='thin',color='CCCCCC'), bottom=_S(style='thin',color='CCCCCC'))

    ws.merge_cells('A1:C1')
    ws['A1'] = 'SENAI — Lista de Alunos da Turma'
    ws['A1'].font = _F(bold=True, color='FFFFFF', name='Arial', size=13)
    ws['A1'].fill = _P('solid', fgColor='C0000F')
    ws['A1'].alignment = _A(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 26

    ws.merge_cells('A2:C2')
    ws['A2'] = 'Preencha os dados abaixo. A coluna Matricula e opcional mas recomendada.'
    ws['A2'].font = _F(italic=True, color='555555', name='Arial', size=9)
    ws['A2'].alignment = _A(horizontal='left', vertical='center', wrap_text=True)
    ws.row_dimensions[2].height = 22

    for ci, h in enumerate(['Nome Completo', 'Matricula', 'Observacao'], 1):
        c = ws.cell(row=3, column=ci, value=h)
        c.font = _F(bold=True, color='FFFFFF', name='Arial', size=11)
        c.fill = _P('solid', fgColor='444444')
        c.alignment = _A(horizontal='center', vertical='center')
        c.border = borda
    ws.row_dimensions[3].height = 18

    for ri, (nome, mat, obs) in enumerate([
        ('ANA CAROLINA SOUZA','2024001',''),
        ('BRUNO HENRIQUE LIMA','2024002',''),
        ('CARLA MELO SANTOS','2024003',''),
        ('DIEGO FERREIRA COSTA','','Sem matricula'),
        ('EVA OLIVEIRA SILVA','2024005',''),
    ], start=4):
        fill = _P('solid', fgColor='FFF5F5' if ri%2==0 else 'FFFFFF')
        for ci, val in enumerate([nome, mat, obs], 1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.font = _F(name='Arial', size=10, color='333333')
            c.fill = fill; c.border = borda
            c.alignment = _A(vertical='center')
        ws.row_dimensions[ri].height = 16

    ws.column_dimensions['A'].width = 36
    ws.column_dimensions['B'].width = 16
    ws.column_dimensions['C'].width = 24

    buf = _io.BytesIO()
    wb.save(buf); buf.seek(0)
    return buf.getvalue()


def _professor_nova_prova():
    st.header("➕ Nova Prova")
    st.caption("Crie a prova e configure questões, lista de alunos e opções na tela de configuração.")

    with st.form("form_nova_prova"):
        titulo = st.text_input("Título da prova*",
                               placeholder="Ex: Avaliação Bimestral — Lógica de Programação")
        col1, col2 = st.columns(2)
        with col1:
            tempo = st.number_input("Tempo (minutos)*", min_value=10,
                                    max_value=240, value=60, step=5)
        with col2:
            senha = st.text_input("Senha do professor*", value="senai123")
        descricao = st.text_area("Descrição / Observações", placeholder="Opcional")
        submitted = st.form_submit_button("✅ Criar e ir para Configuração",
                                          type="primary", use_container_width=True)

    if submitted:
        if not titulo.strip():
            st.error("Informe o título da prova.")
            return
        pid = db.criar_prova(titulo.strip(), descricao.strip(), tempo, senha)
        st.session_state['configurando_prova_id'] = pid
        st.rerun()


def _importar_questoes(prova_id, arquivo, arquivo_gabarito=None):
    import tempfile, os
    tmp_prova = tmp_gab = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
            tmp.write(arquivo.read())
            tmp_prova = tmp.name

        tmp_gab = None
        if arquivo_gabarito:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
                tmp.write(arquivo_gabarito.read())
                tmp_gab = tmp.name

        questoes = importar_docx(tmp_prova, tmp_gab)
        erros = validar_questoes(questoes)
        if erros:
            for e in erros:
                st.error(e)
            return

        db.deletar_questoes_prova(prova_id)
        for i, q in enumerate(questoes, start=1):
            qid = db.inserir_questao(prova_id, i, q['tipo'], q['enunciado'],
                                     q['peso'], q.get('gabarito_dissertativa'))
            # Objetiva: alternativas
            for alt in q.get('alternativas', []):
                db.inserir_alternativa(qid, alt['letra'], alt['texto'], alt['correta'])
            # VF: afirmativas
            for af in q.get('afirmativas', []):
                db.inserir_afirmativa_vf(qid, af['letra'], af['texto'], af.get('gabarito'))

        tipos = [q['tipo'] for q in questoes]
        resumo = f"{tipos.count('vf')} VF, {tipos.count('objetiva')} objetiva(s), {tipos.count('dissertativa')} dissertativa(s)"
        st.success(f"✅ {len(questoes)} questão(ões) importada(s) — {resumo}")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao importar: {e}")
    finally:
        for p in [tmp_prova, tmp_gab]:
            if p and os.path.exists(p):
                try: os.unlink(p)
                except: pass

    with st.form("form_nova_prova"):
        titulo = st.text_input("Título da prova*",
                               placeholder="Ex: Avaliação Bimestral — Lógica de Programação")
        col1, col2 = st.columns(2)
        with col1:
            tempo = st.number_input("Tempo (minutos)*", min_value=10,
                                    max_value=240, value=60, step=5)
        with col2:
            senha = st.text_input("Senha do professor*", value="senai123")
        descricao = st.text_area("Descrição / Observações", placeholder="Opcional")
        submitted = st.form_submit_button("✅ Criar e ir para Configuração",
                                          type="primary", use_container_width=True)

    if submitted:
        if not titulo.strip():
            st.error("Informe o título da prova.")
            return
        pid = db.criar_prova(titulo.strip(), descricao.strip(), tempo, senha)
        st.session_state['configurando_prova_id'] = pid
        st.rerun()


def _professor_dashboard():
    st.header("📊 Dashboard da Prova")

    provas = db.listar_provas()
    if not provas:
        st.info("Nenhuma prova cadastrada.")
        return

    # Usa ID salvo no session_state para não perder seleção após mudança de status
    ids_disponiveis = [p['id'] for p in provas]
    id_salvo = st.session_state.get('_dash_prova_id')
    idx_default = ids_disponiveis.index(id_salvo) if id_salvo in ids_disponiveis else 0

    opcoes = {f"{p['titulo']} ({fmt_status(p['status'])})": p['id'] for p in provas}
    sel = st.selectbox("Selecione a prova", list(opcoes.keys()), index=idx_default)
    prova_id = opcoes[sel]
    st.session_state['_dash_prova_id'] = prova_id

    prova = db.get_prova(prova_id)

    # Auto-refresh quando ativa
    col_refresh, col_status = st.columns([3, 1])
    with col_refresh:
        auto = st.checkbox("🔄 Atualizar automaticamente (3s)", value=prova['status'] == 'ativa')
    with col_status:
        st.write(f"Status: {fmt_status(prova['status'])}")

    dados = db.dashboard_prova(prova_id)
    sessoes = dados['sessoes']
    total_q = dados['total_questoes']
    alunos_turma = dados.get('alunos_turma', [])

    # ── Controle da Prova ──
    st.markdown("### 🎛️ Controle da Prova")

    status_prova = prova['status']

    # Badge de status
    cores_status = {
        'configurando':   ('#6c757d', '⚙️ Configurando'),
        'ativa':          ('#198754', '🟢 Ativa — em andamento'),
        'encerrada':      ('#dc3545', '🔴 Encerrada'),
        'notas_liberadas':('#6f42c1', '🏆 Notas liberadas'),
    }
    cor_s, label_s = cores_status.get(status_prova, ('#333', status_prova))
    st.markdown(
        f'<div style="display:inline-block;background:{cor_s};color:#fff;'
        f'border-radius:20px;padding:4px 16px;font-size:.85rem;font-weight:600;'
        f'margin-bottom:12px">{label_s}</div>',
        unsafe_allow_html=True
    )

    col_a1, col_a2, col_a3, col_a4 = st.columns(4)
    with col_a1:
        if status_prova == 'configurando':
            if st.button("🟢 Ativar Prova", use_container_width=True, type="primary"):
                if not db.get_questoes_prova(prova_id):
                    st.error("Adicione questões antes de ativar.")
                else:
                    db.atualizar_status_prova(prova_id, 'ativa')
                    st.rerun()
        elif status_prova == 'ativa':
            if st.button("🔴 Encerrar Prova", use_container_width=True):
                db.atualizar_status_prova(prova_id, 'encerrada')
                st.rerun()
        elif status_prova == 'encerrada':
            if st.button("🔄 Reabrir (ativa)", use_container_width=True):
                db.atualizar_status_prova(prova_id, 'ativa')
                st.rerun()

    with col_a2:
        if status_prova in ('ativa', 'encerrada'):
            enviadas_count = sum(1 for s in sessoes if s['status'] == 'enviada')
            btn_type = "primary" if status_prova == 'encerrada' else "secondary"
            if st.button(f"🏆 Liberar Notas ({enviadas_count})",
                         use_container_width=True, type=btn_type):
                _corrigir_e_liberar_todos(prova_id)
                db.atualizar_status_prova(prova_id, 'notas_liberadas')
                st.success("✅ Notas liberadas!")
                st.rerun()

    with col_a3:
        if status_prova == 'notas_liberadas':
            if st.button("🔄 Reabrir correção", use_container_width=True):
                db.atualizar_status_prova(prova_id, 'encerrada')
                st.rerun()

    with col_a4:
        if status_prova == 'ativa':
            st.caption("Prova liberada para os alunos")

    st.divider()

    # ── Barra geral da turma ──────────────────────────────────────────────────
    nomes_logados   = {s['nome_aluno'] for s in sessoes}
    enviadas_s      = [s for s in sessoes if s['status'] in ('enviada','nota_liberada')]
    respondendo_s   = [s for s in sessoes if s['status'] == 'em_andamento']
    nao_logou_s     = [n for n in alunos_turma if n not in nomes_logados]

    total_turma = len(alunos_turma) if alunos_turma else len(sessoes)
    pct_entregue = int(len(enviadas_s) / total_turma * 100) if total_turma > 0 else 0
    pct_respond  = int(len(respondendo_s) / total_turma * 100) if total_turma > 0 else 0
    pct_ausente  = 100 - pct_entregue - pct_respond

    st.markdown("### 👥 Situação da Turma")

    # Valores para a barra
    n_entregues  = len(enviadas_s)
    n_respond    = len(respondendo_s)
    n_ausentes   = len(nao_logou_s)
    lbl_e  = f"✅ {n_entregues}"  if pct_entregue > 8  else ""
    lbl_r  = f"✏️ {n_respond}"   if pct_respond  > 8  else ""
    lbl_a  = f"⏳ {n_ausentes}"  if pct_ausente  > 8  else ""
    mw_e   = 2 if pct_entregue > 0 else 0
    mw_r   = 2 if pct_respond  > 0 else 0
    mw_a   = 2 if pct_ausente  > 0 else 0

    barra_html = (
        '<div style="border-radius:8px;overflow:hidden;height:28px;display:flex;'
        'font-size:.8rem;font-weight:600;margin-bottom:6px;">'
        f'<div style="width:{pct_entregue}%;background:#198754;color:#fff;'
        f'display:flex;align-items:center;justify-content:center;min-width:{mw_e}%">'
        f'{lbl_e}</div>'
        f'<div style="width:{pct_respond}%;background:#0d6efd;color:#fff;'
        f'display:flex;align-items:center;justify-content:center;min-width:{mw_r}%">'
        f'{lbl_r}</div>'
        f'<div style="width:{pct_ausente}%;background:#dee2e6;color:#666;'
        f'display:flex;align-items:center;justify-content:center;min-width:{mw_a}%">'
        f'{lbl_a}</div>'
        '</div>'
        '<div style="display:flex;gap:16px;font-size:.82rem;margin-bottom:4px;">'
        f'<span>🟢 Entregues: <b>{n_entregues}</b></span>'
        f'<span>🔵 Respondendo: <b>{n_respond}</b></span>'
        f'<span>⚪ Não logou: <b>{n_ausentes}</b></span>'
        f'<span style="color:#888">Total: {total_turma}</span>'
        '</div>'
    )
    st.markdown(barra_html, unsafe_allow_html=True)

    # Pendentes (quem ainda não entregou)
    pendentes = [s['nome_aluno'] for s in respondendo_s]
    if nao_logou_s or pendentes:
        with st.expander(f"⏳ Pendentes ({len(pendentes) + len(nao_logou_s)})"):
            if pendentes:
                st.markdown("**✏️ Respondendo (ainda não enviou):**")
                for n in pendentes:
                    st.markdown(f"• {n}")
            if nao_logou_s:
                st.markdown("**⚪ Não logou:**")
                for n in nao_logou_s:
                    st.markdown(f"• {n}")

    st.divider()

    # ── Métricas gerais ──
    total_alunos = len(sessoes)
    aguardando = sum(1 for s in sessoes if s['status'] == 'aguardando')
    respondendo = sum(1 for s in sessoes if s['status'] == 'em_andamento')
    enviadas = sum(1 for s in sessoes if s['status'] in ('enviada', 'nota_liberada'))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Alunos conectados", total_alunos)
    c2.metric("⏳ Aguardando", aguardando)
    c3.metric("✏️ Respondendo", respondendo)
    c4.metric("✅ Enviadas", enviadas)

    st.divider()

    # ── Progresso por aluno ──
    st.subheader("Progresso por Aluno")

    # Controles globais da turma
    col_g1, col_g2, col_g3, col_g4 = st.columns(4)
    with col_g1:
        tem_pausados = any(s.get('pausado_em') for s in sessoes)
        if not tem_pausados:
            if st.button("⏸️ Pausar todos", use_container_width=True):
                db.pausar_todos(prova_id)
                st.rerun()
        else:
            if st.button("▶️ Retomar todos", use_container_width=True, type="primary"):
                db.retomar_todos(prova_id)
                st.rerun()
    with col_g2:
        if st.button("⏱️ +5 min para todos", use_container_width=True):
            db.adicionar_tempo_todos(prova_id, 5)
            st.success("+5 min adicionados!")
            st.rerun()
    with col_g3:
        if st.button("⏱️ +10 min para todos", use_container_width=True):
            db.adicionar_tempo_todos(prova_id, 10)
            st.success("+10 min adicionados!")
            st.rerun()
    with col_g4:
        st.caption("⬆️ Aplicado a alunos em andamento")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if not sessoes:
        st.info("Nenhum aluno conectado ainda.")
    else:
        for s in sessoes:
            progresso = (s['total_respondidas'] / total_q) if total_q > 0 else 0
            esta_pausado = bool(s.get('pausado_em'))
            col_nome, col_barra, col_status_s, col_nota, col_acoes = st.columns([3, 3, 2, 1, 2])

            with col_nome:
                icone = "⏸️ " if esta_pausado else ""
                st.write(f"**{icone}{s['nome_aluno']}**")
                if s.get('tempo_extra_min'):
                    st.caption(f"⏱️ +{s['tempo_extra_min']} min extra")
            with col_barra:
                pct = int(progresso * 100)
                cor_barra = "#ffc107" if esta_pausado else "#E30613"
                st.markdown(f"""
                <div class="barra-progresso">
                  <div class="barra-fill" style="width:{pct}%;background:{cor_barra}"></div>
                </div>
                <small>{s['total_respondidas']}/{total_q} questões ({pct}%)</small>
                """, unsafe_allow_html=True)
            with col_status_s:
                st.write(fmt_status(s['status']))
            with col_nota:
                if s['nota_final'] is not None:
                    st.write(f"**{s['nota_final']:.1f}**")
                else:
                    st.write("—")
            with col_acoes:
                if s['status'] == 'em_andamento':
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        tip = "▶️" if esta_pausado else "⏸️"
                        if st.button(tip, key=f"pause_{s['id']}",
                                     use_container_width=True,
                                     help="Pausar/Retomar"):
                            if esta_pausado:
                                db.retomar_sessao(s['id'])
                            else:
                                db.pausar_sessao(s['id'])
                            st.rerun()
                    with c2:
                        if st.button("⏱️", key=f"tempo_{s['id']}",
                                     use_container_width=True,
                                     help="+5 min"):
                            db.adicionar_tempo_extra(s['id'], 5)
                            st.rerun()
                    with c3:
                        if st.button("🔄", key=f"reset_{s['id']}",
                                     use_container_width=True,
                                     help="Resetar prova"):
                            db.resetar_sessao(s['id'])
                            st.success(f"Prova de {s['nome_aluno']} resetada.")
                            st.rerun()

    st.divider()

    # ── Taxa de acertos por questão ──
    if dados['acertos_por_questao']:
        st.subheader("Taxa de Acertos por Questão (Objetivas)")
        try:
            import plotly.graph_objects as go
            labels = [f"Q{a['numero_original']}" for a in dados['acertos_por_questao']]
            taxas = [
                round(a['acertos'] / a['total_respostas'] * 100, 1) if a['total_respostas'] > 0 else 0
                for a in dados['acertos_por_questao']
            ]
            cores = ['#198754' if t >= 60 else '#ffc107' if t >= 40 else '#dc3545' for t in taxas]
            fig = go.Figure(go.Bar(x=labels, y=taxas, marker_color=cores,
                                   text=[f"{t}%" for t in taxas], textposition='auto'))
            fig.update_layout(
                yaxis_title="% de acertos", yaxis_range=[0, 100],
                height=280, margin=dict(l=0, r=0, t=20, b=0),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            # Fallback sem plotly
            for a in dados['acertos_por_questao']:
                taxa = round(a['acertos'] / a['total_respostas'] * 100, 1) if a['total_respostas'] > 0 else 0
                st.write(f"Q{a['numero_original']}: {taxa}% de acertos ({a['acertos']}/{a['total_respostas']})")

    if auto:
        time.sleep(3)
        st.rerun()


def _corrigir_e_liberar_todos(prova_id):
    sessoes = db.listar_sessoes_prova(prova_id)
    questoes = db.get_questoes_prova(prova_id)
    total_peso = sum(q['peso'] for q in questoes)

    for s in sessoes:
        if s['status'] != 'enviada':
            continue
        acertos_obj, _, _ = db.corrigir_objetivas(s['id'])
        acertos_vf, _ = db.corrigir_vf(s['id'], prova_id)
        nota = round(((acertos_obj + acertos_vf) / total_peso * 10)
                     if total_peso > 0 else 0, 1)
        db.liberar_nota_aluno(s['id'], nota)


def _professor_corrigir_dissertativas():
    st.header("✏️ Corrigir Dissertativas")

    provas = [p for p in db.listar_provas() if p['status'] in ('encerrada', 'notas_liberadas')]
    if not provas:
        st.info("Nenhuma prova encerrada com dissertativas para corrigir.")
        return

    opcoes = {p['titulo']: p['id'] for p in provas}
    sel = st.selectbox("Prova", list(opcoes.keys()))
    prova_id = opcoes[sel]

    questoes_dis = [q for q in db.get_questoes_prova(prova_id) if q['tipo'] == 'dissertativa']
    if not questoes_dis:
        st.info("Esta prova não tem questões dissertativas.")
        return

    sessoes = [s for s in db.listar_sessoes_prova(prova_id)
               if s['status'] in ('enviada', 'nota_liberada')]

    questoes_todas = db.get_questoes_prova(prova_id)
    total_peso = sum(q['peso'] for q in questoes_todas)

    for s in sessoes:
        with st.expander(f"👤 {s['nome_aluno']} — nota atual: {s['nota_final'] or '—'}"):
            respostas = db.get_respostas_sessao(s['id'])
            pontos_dissertativa = 0.0

            for q in questoes_dis:
                resp = respostas.get(q['id'])
                st.markdown(f"**Q{q['numero_original']} ({q['peso']} pt):** {q['enunciado']}")
                if q['gabarito_dissertativa']:
                    with st.expander("📖 Gabarito de referência"):
                        st.write(q['gabarito_dissertativa'])

                texto_aluno = resp['resposta_texto'] if resp else '*(sem resposta)*'
                st.text_area("Resposta do aluno", value=texto_aluno, disabled=True,
                             key=f"txt_{s['id']}_{q['id']}")

                nota_q = st.number_input(
                    f"Nota desta questão (máx {q['peso']})",
                    min_value=0.0, max_value=float(q['peso']),
                    value=0.0, step=0.25,
                    key=f"nota_q_{s['id']}_{q['id']}"
                )
                pontos_dissertativa += nota_q
                st.divider()

            # Recalcula nota total
            acertos_obj, _, _ = db.corrigir_objetivas(s['id'])
            nota_total = round(((acertos_obj + pontos_dissertativa) / total_peso * 10)
                               if total_peso > 0 else 0, 1)
            st.info(f"📊 Nota calculada: **{nota_total:.1f} / 10**")

            if st.button(f"💾 Salvar nota de {s['nome_aluno']}", key=f"sv_{s['id']}",
                         use_container_width=True):
                db.liberar_nota_aluno(s['id'], nota_total)
                st.success("Nota salva!")
                st.rerun()


# ─── TELA DO ALUNO ────────────────────────────────────────────────────────────

def tela_aluno():
    prova_id = st.session_state['prova_id']
    nome_aluno = st.session_state['nome_aluno']
    prova = db.get_prova(prova_id)
    modo_teste = st.session_state.get('modo_teste', False)

    # Modo teste: banner + botão sair
    if modo_teste:
        col_banner, col_sair = st.columns([5, 1])
        with col_banner:
            st.warning("🧪 **MODO TESTE** — Você está simulando a prova como aluno. "
                       "Respostas serão descartadas ao sair.")
        with col_sair:
            if st.button("✖ Sair do teste", use_container_width=True, type="primary"):
                # Limpa sessão de teste
                sessao_t = db.get_sessao_por_aluno(prova_id, nome_aluno)
                if sessao_t:
                    conn = db.get_conn()
                    conn.execute("DELETE FROM respostas WHERE sessao_id=?", (sessao_t['id'],))
                    conn.execute("DELETE FROM respostas_vf WHERE sessao_id=?", (sessao_t['id'],))
                    conn.execute("DELETE FROM sessoes WHERE id=?", (sessao_t['id'],))
                    conn.commit(); conn.close()
                pid_ret = st.session_state.pop('prova_id_retorno_cfg', None)
                st.session_state.pop('modo_teste', None)
                st.session_state.pop('questao_idx', None)
                st.session_state['perfil'] = 'professor'
                st.session_state['prova_id'] = pid_ret or prova_id
                if pid_ret:
                    st.session_state['configurando_prova_id'] = pid_ret
                st.rerun()

    # Verifica status da prova (ignora se modo teste)
    if not modo_teste and prova['status'] == 'configurando':
        # Cria sessão imediatamente para o aluno ficar registrado na fila
        sessao = db.get_sessao_por_aluno(prova_id, nome_aluno)
        if sessao is None:
            questoes = db.get_questoes_prova(prova_id)
            ids = [q['id'] for q in questoes]
            if prova['ordem_aleatoria'] and ids:
                random.shuffle(ids)
            # Cria sessão mesmo sem questões — será reconstruída ao entrar na prova
            sessao = db.criar_ou_recuperar_sessao(
                prova_id, nome_aluno, json.dumps(ids), len(ids)
            )
        _sala_espera(nome_aluno, prova)
        return

    # Recupera ou cria sessão (prova já ativa ou modo teste)
    sessao = db.get_sessao_por_aluno(prova_id, nome_aluno)
    if sessao is None:
        questoes = db.get_questoes_prova(prova_id)
        ids = [q['id'] for q in questoes]
        if prova['ordem_aleatoria']:
            random.shuffle(ids)
        sessao = db.criar_ou_recuperar_sessao(
            prova_id, nome_aluno, json.dumps(ids), len(ids)
        )

    status = sessao['status']

    # Tempo esgotado — enviou automaticamente
    if st.session_state.get('tempo_esgotado') and status == 'enviada':
        st.error("⏰ **Tempo esgotado!** Sua prova foi enviada automaticamente.")
        st.session_state.pop('tempo_esgotado', None)
        time.sleep(2)
        st.rerun()

    if status == 'nota_liberada':
        _tela_resultado(sessao, prova)
        return

    if status == 'enviada':
        # Se prova ainda ativa, professor pode ter resetado — relê sessão
        if prova['status'] == 'ativa':
            sessao = db.get_sessao_por_aluno(prova_id, nome_aluno)
            if sessao and sessao['status'] == 'em_andamento':
                _tela_prova(sessao, prova)
                return
        _aguardar_nota(nome_aluno, prova_id)
        return

    # Se prova ainda não ativa (aluno que entrou direto sem sala de espera)
    if not modo_teste and prova['status'] not in ('ativa',):
        _sala_espera(nome_aluno, prova)
        return

    # ── Prova em andamento ──
    _tela_prova(sessao, prova)


def _sala_espera(nome_aluno, prova):
    """Sala de espera — aluno já está registrado, aguarda ativação."""
    prova_atual = db.get_prova(prova['id'])

    # Prova foi ativada enquanto jogava — redireciona automaticamente
    if prova_atual['status'] == 'ativa':
        st.success("🟢 A prova foi liberada! Entrando agora...")
        time.sleep(1)
        st.rerun()
        return

    col_nome, col_status = st.columns([3, 1])
    with col_nome:
        st.markdown(f"## 👋 Olá, **{nome_aluno}**!")
    with col_status:
        st.markdown("""
        <div style="background:#fff3cd; border:1px solid #ffc107; border-radius:8px;
                    padding:8px 12px; text-align:center; margin-top:8px;">
            <span style="font-size:.8rem; color:#856404; font-weight:600;">
            ⏳ Aguardando professor</span>
        </div>
        """, unsafe_allow_html=True)

    st.info(f"**{prova['titulo']}** — você já está registrado(a). "
            "Quando o professor liberar, a prova abrirá automaticamente.")

    # Lê lista de jogos disponíveis
    jogo_raw = prova_atual.get('jogo_espera', 'none') or 'none'
    try:
        jogos_lista = json.loads(jogo_raw) if jogo_raw.startswith('[') else (
            [] if jogo_raw == 'none' else [jogo_raw]
        )
    except Exception:
        jogos_lista = []

    jogos_lista = [j for j in jogos_lista if j in JOGOS_DISPONIVEIS]

    if not jogos_lista:
        st.markdown("""
        <div style="text-align:center; padding:60px 20px; color:#888;">
            <div style="font-size:3rem">☕</div>
            <div style="font-size:1.1rem; margin-top:12px;">
                Relaxe e aguarde o professor liberar a prova.
            </div>
        </div>
        """, unsafe_allow_html=True)
    elif len(jogos_lista) == 1:
        # Só um jogo — exibe direto
        nome_jogo = JOGOS_DISPONIVEIS[jogos_lista[0]]
        st.markdown(f"### {nome_jogo} 🎮")
        st.caption("Aproveite enquanto aguarda — suas respostas não serão perdidas.")
        render_jogo(jogos_lista[0], nome_aluno, altura=560)
    else:
        # Múltiplos jogos — aluno escolhe via abas
        st.markdown("### 🎮 Escolha um jogo para jogar enquanto aguarda:")

        # Botões de seleção de jogo
        jogo_key = f'jogo_sala_{nome_aluno}'
        if jogo_key not in st.session_state:
            st.session_state[jogo_key] = jogos_lista[0]

        cols = st.columns(len(jogos_lista))
        for ci, jkey in enumerate(jogos_lista):
            nome_j = JOGOS_DISPONIVEIS[jkey]
            selecionado = st.session_state[jogo_key] == jkey
            with cols[ci]:
                if st.button(
                    f"{'▶️ ' if selecionado else ''}{nome_j}",
                    key=f"sel_jogo_{jkey}_{nome_aluno}",
                    use_container_width=True,
                    type="primary" if selecionado else "secondary"
                ):
                    st.session_state[jogo_key] = jkey
                    st.rerun()

        jogo_ativo = st.session_state[jogo_key]
        st.caption(f"Jogando: **{JOGOS_DISPONIVEIS[jogo_ativo]}** — "
                   "seus dados na prova estão salvos.")
        render_jogo(jogo_ativo, nome_aluno, altura=560)

    # Verifica a cada 4s se a prova foi ativada
    time.sleep(4)
    st.rerun()


def _aguardar_nota(nome_aluno, prova_id):
    st.markdown(f"## ✅ Prova enviada!")
    st.success(f"Olá **{nome_aluno}**, sua prova foi entregue com sucesso.")
    st.info("Aguarde o professor liberar sua nota...")

    prova = db.get_prova(prova_id)
    sessao = db.get_sessao_por_aluno(prova_id, nome_aluno)

    if sessao and sessao['status'] == 'nota_liberada':
        st.rerun()

    if prova['status'] == 'notas_liberadas':
        if sessao:
            db.liberar_nota_aluno(sessao['id'], sessao['nota_final'])
        st.rerun()

    time.sleep(4)
    st.rerun()


def _tela_resultado(sessao, prova):
    st.markdown(f"## 🏆 Resultado — {prova['titulo']}")
    nota = sessao['nota_final']
    conceito = "Excelente!" if nota >= 9 else "Bom!" if nota >= 7 else "Regular" if nota >= 5 else "Insuficiente"
    cor = "#198754" if nota >= 7 else "#ffc107" if nota >= 5 else "#dc3545"

    st.markdown(f"""
    <div style="text-align:center; padding: 40px; background: #f8f9fa; border-radius: 12px;">
        <p style="font-size:1.1rem; color:#666;">Sua nota</p>
        <p style="font-size:4rem; font-weight:700; color:{cor}; margin:0">{nota:.1f}</p>
        <p style="font-size:1.3rem; color:{cor}; font-weight:600">{conceito}</p>
        <p style="color:#888; margin-top: 16px;">Aluno: {sessao['nome_aluno']}</p>
    </div>
    """, unsafe_allow_html=True)


def _tela_prova(sessao, prova):
    sessao_id = sessao['id']
    prova_id = prova['id']
    _rerun_delay = 5  # padrão — atualizado após calcular tempo restante

    # Questões atuais da prova
    questoes_dict = {q['id']: q for q in db.get_questoes_prova(prova_id)}

    # Ordem das questões desta sessão
    try:
        ordem_ids = json.loads(sessao['ordem_questoes'] or '[]')
    except Exception:
        ordem_ids = []

    # Reconstrói se vazia ou com IDs que não existem mais
    ids_validos = [qid for qid in ordem_ids if qid in questoes_dict]
    if not ids_validos:
        ids_validos = list(questoes_dict.keys())
        if prova['ordem_aleatoria']:
            random.shuffle(ids_validos)
        # Atualiza sessão no banco
        db.ex("UPDATE sessoes SET ordem_questoes=?, total_questoes=? WHERE id=?",
              [json.dumps(ids_validos), len(ids_validos), sessao_id])
        ordem_ids = ids_validos

    questoes_ordenadas = [questoes_dict[qid] for qid in ids_validos]
    total_q = len(questoes_ordenadas)

    # Respostas salvas (objetivas/dissertativas)
    respostas = db.get_respostas_sessao(sessao_id)
    # Respostas VF — agrupa por questao_id: questão VF está respondida se TODAS afirmativas têm resposta
    respostas_vf_raw = db.get_respostas_vf_sessao(sessao_id)
    # Monta set de questao_ids VF completamente respondidas
    qids_vf_completas = set()
    for q in questoes_ordenadas:
        if q['tipo'] == 'vf':
            afs = db.get_afirmativas_questao(q['id'])
            if afs and all(respostas_vf_raw.get(af['id']) in ('V','F') for af in afs):
                qids_vf_completas.add(q['id'])

    # Índice da questão atual
    if 'questao_idx' not in st.session_state:
        st.session_state['questao_idx'] = 0
    idx = st.session_state['questao_idx']
    idx = max(0, min(idx, total_q - 1))

    # ─── HEADER ───────────────────────────────────────────────────────────────
    col_nome, col_timer_ph, col_ocultar = st.columns([4, 2, 1])
    with col_nome:
        st.markdown(f"**{nome_aluno_display(sessao['nome_aluno'])}** — {prova['titulo']}")
        st.markdown("""
        <div style="font-size:.72rem; color:#198754; margin-top:-6px;">
            💾 Respostas salvas automaticamente
        </div>""", unsafe_allow_html=True)

    with col_ocultar:
        ocultar = st.checkbox("Ocultar ⏱️", value=st.session_state.get('ocultar_timer', False),
                              key='ocultar_timer')

    # Cronômetro em fragment isolado — rerun não afeta o resto da página
    with col_timer_ph:
        _intervalo = 1 if _rerun_delay == 1 else 2 if _rerun_delay == 2 else 5
        try:
            @st.fragment(run_every=_intervalo)
            def _frag_timer():
                s_atual = db.get_sessao(sessao_id)
                p_atual = db.get_prova(prova_id)
                if s_atual and p_atual:
                    _cronometro(s_atual, p_atual)
            _frag_timer()
        except (AttributeError, TypeError):
            # Streamlit < 1.37 — usa o cronômetro normal sem fragment
            restante = _cronometro(sessao, prova)
            st.session_state['_rerun_delay'] = (
                1 if restante <= 35 else 2 if restante <= 65 else 5)

    # ─── BARRA DE PROGRESSO ───────────────────────────────────────────────────
    def _questao_respondida(qid):
        q = questoes_dict.get(qid, {})
        if q.get('tipo') == 'vf':
            return qid in qids_vf_completas
        r = respostas.get(qid, {})
        return bool(r.get('alternativa_id') or r.get('resposta_texto'))

    respondidas = sum(1 for qid in ordem_ids if _questao_respondida(qid))
    pct = int(respondidas / total_q * 100) if total_q > 0 else 0
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px">
        <div class="barra-progresso" style="flex:1">
          <div class="barra-fill" style="width:{pct}%"></div>
        </div>
        <span style="font-size:0.85rem; white-space:nowrap">{respondidas}/{total_q} respondidas</span>
    </div>
    """, unsafe_allow_html=True)

    # ─── ÍNDICE DE QUESTÕES (navegação rápida) ────────────────────────────────
    if prova['navegacao_livre']:
        _indices_questoes(questoes_ordenadas, ordem_ids, respostas, idx,
                          qids_vf_completas)

    st.divider()

    # ─── QUESTÃO ATUAL ────────────────────────────────────────────────────────
    questao = questoes_ordenadas[idx]
    resp_atual = respostas.get(questao['id'], {})
    marcada = bool(resp_atual.get('marcada_revisao', False))

    # Alternativas (possivelmente embaralhadas por sessão)
    alternativas = _get_alternativas_ordenadas(questao, prova, sessao)

    # Badge revisão
    revisao_badge = '<span class="badge-revisao">📌 Marcada p/ revisão</span>' if marcada else ''

    st.markdown(f"""
    <div class="questao-card">
        <div class="questao-numero">Questão {idx+1} de {total_q} &nbsp;|&nbsp;
        {questao['tipo'].capitalize()} &nbsp;|&nbsp; {questao['peso']} pt &nbsp; {revisao_badge}</div>
        <div class="questao-enunciado">{questao['enunciado']}</div>
    </div>
    """, unsafe_allow_html=True)

    # ─── RESPOSTA ─────────────────────────────────────────────────────────────
    if questao['tipo'] == 'objetiva':
        _resposta_objetiva(sessao_id, questao, alternativas, resp_atual)
    elif questao['tipo'] == 'vf':
        _resposta_vf(sessao_id, questao)
    else:
        _resposta_dissertativa(sessao_id, questao, resp_atual)

    # ─── MARCAR REVISÃO ───────────────────────────────────────────────────────
    col_rev, col_nav_ant, col_nav_prox = st.columns([2, 1, 1])
    with col_rev:
        nova_marcacao = st.checkbox("📌 Marcar para revisão", value=marcada,
                                    key=f"rev_{questao['id']}")
        if nova_marcacao != marcada:
            resp = respostas.get(questao['id'], {})
            db.salvar_resposta(
                sessao_id, questao['id'],
                alternativa_id=resp.get('alternativa_id'),
                resposta_texto=resp.get('resposta_texto'),
                marcada_revisao=nova_marcacao,
                status_resposta='revisao' if nova_marcacao else 'rascunho'
            )
            st.rerun()

    # ─── NAVEGAÇÃO ────────────────────────────────────────────────────────────
    with col_nav_ant:
        pode_voltar = idx > 0 and (prova['navegacao_livre'] or _tem_questoes_revisao(ordem_ids, respostas, idx))
        if st.button("⬅️ Anterior", disabled=not pode_voltar, use_container_width=True):
            st.session_state['questao_idx'] = idx - 1
            st.rerun()

    with col_nav_prox:
        if idx < total_q - 1:
            if st.button("Próxima ➡️", use_container_width=True):
                st.session_state['questao_idx'] = idx + 1
                st.rerun()
        else:
            # Última questão: botão Enviar
            if st.button("📤 Enviar Prova", type="primary", use_container_width=True):
                _confirmar_envio(sessao_id, ordem_ids, respostas, total_q,
                                 questoes_dict, qids_vf_completas)

    # ─── LISTA DE REVISÕES ────────────────────────────────────────────────────
    revisoes = [i for i, qid in enumerate(ordem_ids)
                if respostas.get(qid, {}).get('marcada_revisao')]
    if revisoes:
        st.divider()
        st.write("**📌 Questões marcadas para revisão:**")
        cols = st.columns(min(len(revisoes), 8))
        for ci, ri in enumerate(revisoes):
            with cols[ci % len(cols)]:
                if st.button(f"Q{ri+1}", key=f"ir_rev_{ri}", use_container_width=True):
                    st.session_state['questao_idx'] = ri
                    st.rerun()

    # Fallback rerun para Streamlit < 1.37 (sem fragment)
    if st.session_state.get('_rerun_delay'):
        delay = st.session_state.pop('_rerun_delay')
        time.sleep(delay)
        st.rerun()


def _resposta_vf(sessao_id, questao):
    """Renderiza questão V/F com botões V e F por afirmativa."""
    afirmativas = db.get_afirmativas_questao(questao['id'])
    respostas_vf = db.get_respostas_vf_sessao(sessao_id)

    st.markdown("**Marque V (Verdadeiro) ou F (Falso) para cada afirmativa:**")

    for af in afirmativas:
        resp_atual = respostas_vf.get(af['id'])
        v_sel = resp_atual == 'V'
        f_sel = resp_atual == 'F'

        # Cor de fundo dos botões conforme seleção
        bg_v = "#E30613" if v_sel else "#f0f0f0"
        fg_v = "#fff"    if v_sel else "#333"
        bg_f = "#E30613" if f_sel else "#f0f0f0"
        fg_f = "#fff"    if f_sel else "#333"

        col_conteudo, col_v, col_f = st.columns([10, 0.7, 0.7])

        with col_conteudo:
            st.markdown(
                f"<div style='padding:6px 0; font-size:.95rem; line-height:1.5'>"
                f"<span style='font-weight:700; color:#E30613; margin-right:8px'>{af['letra']}.</span>"
                f"{af['texto']}</div>",
                unsafe_allow_html=True
            )
        with col_v:
            if st.button("V", key=f"vf_V_{sessao_id}_{af['id']}",
                         use_container_width=True,
                         type="primary" if v_sel else "secondary"):
                db.salvar_resposta_vf(sessao_id, questao['id'], af['id'], 'V')
                st.rerun()
        with col_f:
            if st.button("F", key=f"vf_F_{sessao_id}_{af['id']}",
                         use_container_width=True,
                         type="primary" if f_sel else "secondary"):
                db.salvar_resposta_vf(sessao_id, questao['id'], af['id'], 'F')
                st.rerun()

        st.markdown("<hr style='margin:2px 0; border-color:#eee'>", unsafe_allow_html=True)


def _resposta_objetiva(sessao_id, questao, alternativas, resp_atual):
    alt_selecionada = resp_atual.get('alternativa_id')
    opcoes = {f"{a['letra'].upper()}) {a['texto']}": a['id'] for a in alternativas}
    idx_sel = None
    if alt_selecionada:
        for i, aid in enumerate(opcoes.values()):
            if aid == alt_selecionada:
                idx_sel = i
                break

    escolha = st.radio(
        "Selecione uma alternativa:",
        list(opcoes.keys()),
        index=idx_sel,
        key=f"obj_{questao['id']}",
        label_visibility="collapsed"
    )

    if escolha:
        novo_id = opcoes[escolha]
        if novo_id != alt_selecionada:
            db.salvar_resposta(sessao_id, questao['id'], alternativa_id=novo_id,
                               status_resposta='rascunho')


def _resposta_dissertativa(sessao_id, questao, resp_atual):
    texto_atual = resp_atual.get('resposta_texto', '') or ''
    novo_texto = st.text_area(
        "Sua resposta:",
        value=texto_atual,
        height=180,
        key=f"dis_{questao['id']}",
        placeholder="Digite sua resposta aqui...",
        label_visibility="collapsed"
    )
    if novo_texto != texto_atual:
        db.salvar_resposta(sessao_id, questao['id'], resposta_texto=novo_texto,
                           status_resposta='rascunho')


def _confirmar_envio(sessao_id, ordem_ids, respostas, total_q,
                     questoes_dict=None, qids_vf_completas=None):
    qids_vf_completas = qids_vf_completas or set()

    def respondida(qid):
        q = (questoes_dict or {}).get(qid, {})
        if q.get('tipo') == 'vf':
            return qid in qids_vf_completas
        r = respostas.get(qid, {})
        return bool(r.get('alternativa_id') or r.get('resposta_texto'))

    sem_resposta = sum(1 for qid in ordem_ids if not respondida(qid))

    if sem_resposta > 0:
        st.warning(f"⚠️ Você tem **{sem_resposta}** questão(ões) sem resposta completa. Confirma o envio mesmo assim?")
        if st.button("✅ Sim, enviar assim mesmo", type="primary"):
            _injetar_localStorage_limpeza()
            db.enviar_prova_aluno(sessao_id)
            st.session_state.pop('questao_idx', None)
            st.rerun()
    else:
        _injetar_localStorage_limpeza()
        db.enviar_prova_aluno(sessao_id)
        st.session_state.pop('questao_idx', None)
        st.rerun()


def _cronometro(sessao, prova):
    iniciada_em_str = sessao.get('iniciada_em')
    if not iniciada_em_str:
        return 999999

    try:
        iniciada_em = datetime.strptime(iniciada_em_str, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return 999999

    tempo_total = (prova['tempo_minutos'] + (sessao.get('tempo_extra_min') or 0)) * 60
    decorrido   = (datetime.now() - iniciada_em).total_seconds()

    # Desconta tempo pausado acumulado
    decorrido -= (sessao.get('tempo_pausado_seg') or 0)

    # Se pausado agora, desconta tempo desde a pausa
    pausado_em_str = sessao.get('pausado_em')
    esta_pausado = bool(pausado_em_str)
    if esta_pausado:
        try:
            pausado_em = datetime.strptime(pausado_em_str, '%Y-%m-%d %H:%M:%S')
            decorrido -= (datetime.now() - pausado_em).total_seconds()
        except Exception:
            pass

    restante = tempo_total - decorrido

    # Mostra badge de pausa
    if esta_pausado:
        st.markdown("""
        <div style="background:#ffc107; color:#000; border-radius:8px;
                    padding:6px 14px; text-align:center; font-weight:700;
                    font-size:.9rem; animation:pulsar 1s infinite;">
            ⏸️ PROVA PAUSADA
        </div>""", unsafe_allow_html=True)
        return max(0, int(restante))

    # ── Envio automático por tempo esgotado ───────────────────────────────────
    if restante <= 0:
        if sessao['status'] == 'em_andamento':
            db.enviar_prova_aluno(sessao['id'], motivo='tempo_esgotado')
        st.session_state['tempo_esgotado'] = True
        st.rerun()
        return 0

    # ── Alertas ───────────────────────────────────────────────────────────────
    if restante <= 30 and not st.session_state.get('aviso_30_confirmado'):
        st.session_state['aviso_30'] = True
    elif restante <= 60 and not st.session_state.get('aviso_1min_confirmado'):
        st.session_state['aviso_1min'] = True
    elif restante <= 300 and not st.session_state.get('aviso_5_confirmado'):
        st.session_state['aviso_5'] = True
    elif restante <= 600 and not st.session_state.get('aviso_10_confirmado'):
        st.session_state['aviso_10'] = True

    if not st.session_state.get('ocultar_timer'):
        if st.session_state.get('aviso_30') and not st.session_state.get('aviso_30_confirmado'):
            st.error("🚨 **ATENÇÃO: 30 SEGUNDOS!** A prova será enviada automaticamente!")
            if st.button("⚠️ Entendido — 30 segundos!", key="ok30", type="primary"):
                st.session_state['aviso_30_confirmado'] = True
                st.rerun()
        elif st.session_state.get('aviso_1min') and not st.session_state.get('aviso_1min_confirmado'):
            st.error("🚨 **Falta 1 MINUTO!** Revise e envie sua prova!")
            if st.button("⚠️ Entendido — 1 minuto!", key="ok1min", type="primary"):
                st.session_state['aviso_1min_confirmado'] = True
                st.rerun()
        elif st.session_state.get('aviso_5') and not st.session_state.get('aviso_5_confirmado'):
            st.warning("⚠️ Faltam **5 minutos** para o fim da prova!")
            if st.button("Ok, entendi (5 min)", key="ok5"):
                st.session_state['aviso_5_confirmado'] = True
                st.rerun()
        elif st.session_state.get('aviso_10') and not st.session_state.get('aviso_10_confirmado'):
            st.info("ℹ️ Faltam **10 minutos** para o fim da prova.")
            if st.button("Ok, entendi (10 min)", key="ok10"):
                st.session_state['aviso_10_confirmado'] = True
                st.rerun()

    if not st.session_state.get('ocultar_timer'):
        cls = "cronometro aviso" if restante <= 300 else "cronometro"
        st.markdown(f'<div class="{cls}">⏱️ {segundos_para_hms(restante)}</div>',
                    unsafe_allow_html=True)

    return max(0, int(restante))


def _get_alternativas_ordenadas(questao, prova, sessao):
    alts = db.get_alternativas_questao(questao['id'])
    if prova['alternativas_aleatorias']:
        # Usa sessao_id + questao_id como semente para consistência
        rng = random.Random(sessao['id'] * 1000 + questao['id'])
        rng.shuffle(alts)
    return alts


def _indices_questoes(questoes_ordenadas, ordem_ids, respostas, idx_atual,
                      qids_vf_completas=None):
    """Mini-mapa de questões para navegação livre."""
    qids_vf_completas = qids_vf_completas or set()
    st.write("**Questões:**")
    cols = st.columns(min(len(questoes_ordenadas), 10))
    for i, q in enumerate(questoes_ordenadas):
        if q['tipo'] == 'vf':
            respondida = q['id'] in qids_vf_completas
        else:
            resp = respostas.get(q['id'], {})
            respondida = bool(resp.get('alternativa_id') or resp.get('resposta_texto'))
        revisao = bool(respostas.get(q['id'], {}).get('marcada_revisao'))

        cor = "🟡" if revisao else "🟢" if respondida else "⚪"
        atual = " ◀" if i == idx_atual else ""

        with cols[i % len(cols)]:
            if st.button(f"{cor}{i+1}{atual}", key=f"nav_{i}", use_container_width=True):
                st.session_state['questao_idx'] = i
                st.rerun()


def _tem_questoes_revisao(ordem_ids, respostas, idx_atual):
    """Permite voltar apenas para questões de revisão se navegação não for livre."""
    for i in range(idx_atual - 1, -1, -1):
        if respostas.get(ordem_ids[i], {}).get('marcada_revisao'):
            return True
    return False


def nome_aluno_display(nome):
    partes = nome.split()
    if len(partes) >= 2:
        return f"{partes[0]} {partes[-1]}"
    return nome


def _importar_lista_alunos(prova_id, arquivo):
    """Lê Excel ou CSV com colunas Nome e Matrícula (opcional) e importa."""
    try:
        nome_arquivo = arquivo.name.lower()
        alunos = []

        if nome_arquivo.endswith('.csv'):
            import csv as _csv, io as _io
            conteudo = arquivo.read().decode('utf-8-sig', errors='replace')
            reader = _csv.DictReader(_io.StringIO(conteudo))
            if reader.fieldnames:
                # Detecta colunas de nome e matrícula
                col_nome = next((c for c in reader.fieldnames
                                 if 'nome' in c.lower() or 'aluno' in c.lower()), None)
                col_mat  = next((c for c in reader.fieldnames
                                 if 'matr' in c.lower() or 'ra' == c.lower().strip()), None)
                if not col_nome:
                    col_nome = reader.fieldnames[0]
                for row in reader:
                    nome = str(row.get(col_nome, '')).strip()
                    mat  = str(row.get(col_mat, '')).strip() if col_mat else None
                    if nome:
                        alunos.append({'nome': nome, 'matricula': mat or None})
            else:
                # Sem cabeçalho — 1ª coluna = nome
                conteudo = arquivo.read().decode('utf-8-sig', errors='replace')
                for linha in _io.StringIO(conteudo):
                    nome = linha.strip()
                    if nome:
                        alunos.append({'nome': nome, 'matricula': None})
        else:
            from openpyxl import load_workbook
            wb = load_workbook(arquivo, read_only=True, data_only=True)
            ws = wb.active
            cabecalho = None
            col_nome_idx = 0
            col_mat_idx  = None

            for ri, row in enumerate(ws.iter_rows(values_only=True)):
                if not row or row[0] is None:
                    continue
                vals = [str(v).strip() if v is not None else '' for v in row]

                if cabecalho is None:
                    # Tenta detectar linha de cabeçalho
                    baixo = [v.lower() for v in vals]
                    if any('nome' in v or 'aluno' in v for v in baixo):
                        cabecalho = baixo
                        col_nome_idx = next(
                            (i for i, v in enumerate(baixo)
                             if 'nome' in v or 'aluno' in v), 0
                        )
                        col_mat_idx = next(
                            (i for i, v in enumerate(baixo)
                             if 'matr' in v or v.strip() == 'ra'), None
                        )
                        continue
                    else:
                        # Sem cabeçalho — trata 1ª linha como dado
                        cabecalho = []

                nome = vals[col_nome_idx] if col_nome_idx < len(vals) else ''
                mat  = vals[col_mat_idx] if col_mat_idx is not None and col_mat_idx < len(vals) else None
                if nome:
                    alunos.append({'nome': nome, 'matricula': mat or None})

        alunos = [a for a in alunos if a['nome']]
        if not alunos:
            st.error("Nenhum nome encontrado no arquivo.")
            return

        db.importar_lista_alunos(prova_id, alunos)

        com_mat = sum(1 for a in alunos if a['matricula'])
        st.success(f"✅ {len(alunos)} aluno(s) importado(s) — "
                   f"{com_mat} com matrícula, {len(alunos)-com_mat} sem matrícula.")

        # Preview
        with st.expander("Ver lista importada"):
            for a in alunos[:20]:
                mat_str = a['matricula'] or '—'
                st.write(f"• {a['nome']}  |  Matrícula: {mat_str}")
            if len(alunos) > 20:
                st.caption(f"... e mais {len(alunos)-20} alunos.")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao importar lista: {e}")


def _professor_exportar():
    st.header("📥 Exportar Resultados")

    provas = db.listar_provas()
    if not provas:
        st.info("Nenhuma prova cadastrada.")
        return

    opcoes = {f"{p['titulo']} ({fmt_status(p['status'])})": p['id'] for p in provas}
    sel = st.selectbox("Selecione a prova", list(opcoes.keys()))
    prova_id = opcoes[sel]
    prova = db.get_prova(prova_id)

    alunos = db.listar_alunos_turma(prova_id)
    sessoes = db.listar_sessoes_prova(prova_id)

    col1, col2, col3 = st.columns(3)
    col1.metric("👥 Lista oficial", len(alunos) if alunos else "Não cadastrada")
    col2.metric("🖥️ Logaram", len(sessoes))
    col3.metric("✅ Enviaram", sum(1 for s in sessoes
                                   if s['status'] in ('enviada', 'nota_liberada')))

    if not sessoes:
        st.info("Nenhum aluno participou ainda.")
        return

    st.divider()

    # Preview da tabela
    dados = db.gerar_dados_export(prova_id)

    st.subheader("Preview — Ordem Alfabética")
    for d in dados:
        status = str(d.get('Status', ''))
        nota = d.get('Nota', '')
        ico = ('🔴' if 'Não logou' in status
               else '🟡' if 'não enviou' in status.lower()
               else '🟠' if 'tempo' in status.lower()
               else '🟢')
        nota_str = f"**{nota:.1f}**" if isinstance(nota, float) else f"**{nota}**" if nota else "—"
        resp_str = d.get('Respondidas', '—')
        st.write(f"{ico} {d['Nome']}  |  {status}  |  Nota: {nota_str}  |  Respondidas: {resp_str}")

    st.divider()
    st.caption("🔴 Não logou  |  🟡 Logou mas não enviou  |  🟠 Enviada por tempo  |  🟢 Enviada")

    try:
        questoes_analise = db.gerar_analise_questoes(prova_id)
        excel_bytes = gerar_excel(prova, dados, questoes_analise)
        nome_arquivo = f"resultado_{prova['titulo'].replace(' ','_')[:30]}.xlsx"
        st.download_button(
            label="⬇️ Baixar Excel completo",
            data=excel_bytes,
            file_name=nome_arquivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
        st.caption("📊 Excel com 4 abas: Resumo da Turma | Respostas Detalhadas | "
                   "Análise por Questão | Para Impressão")
    except Exception as e:
        st.error(f"Erro ao gerar Excel: {e}")


# ─── ROTEADOR PRINCIPAL ───────────────────────────────────────────────────────

def _injetar_localStorage_escritor(nome_aluno: str, prova_id: int):
    """Salva sessão no localStorage do browser para recuperação após queda."""
    import streamlit.components.v1 as _c
    _c.html(f"""
    <script>
    try {{
        localStorage.setItem('senai_aval_nome', '{nome_aluno.replace("'", "\\'")}');
        localStorage.setItem('senai_aval_prova', '{prova_id}');
        localStorage.setItem('senai_aval_ts', Date.now().toString());
    }} catch(e) {{}}
    </script>
    """, height=0)


def _injetar_localStorage_limpeza():
    """Limpa localStorage quando aluno envia a prova."""
    import streamlit.components.v1 as _c
    _c.html("""
    <script>
    try {
        localStorage.removeItem('senai_aval_nome');
        localStorage.removeItem('senai_aval_prova');
        localStorage.removeItem('senai_aval_ts');
    } catch(e) {}
    </script>
    """, height=0)


def _tela_recuperacao():
    """
    Tela intermediária que lê o localStorage e tenta reconectar automaticamente.
    Injetada antes da tela_inicial quando não há sessão no session_state.
    """
    import streamlit.components.v1 as _c

    # Já tentou recuperar nesta sessão?
    if st.session_state.get('_ls_verificado'):
        return False

    st.session_state['_ls_verificado'] = True

    # Parâmetros vindos do JS via query string
    params = st.query_params
    ls_nome  = params.get('_ls_nome', '')
    ls_prova = params.get('_ls_prova', '')

    if ls_nome and ls_prova:
        try:
            prova_id  = int(ls_prova)
            nome      = ls_nome.strip().upper()
            prova     = db.get_prova(prova_id)
            sessao    = db.get_sessao_por_aluno(prova_id, nome)

            # Limpa os query params após usar
            st.query_params.clear()

            if prova and sessao and sessao['status'] == 'em_andamento':
                # Reconexão automática!
                st.session_state['perfil']    = 'aluno'
                st.session_state['nome_aluno'] = nome
                st.session_state['prova_id']   = prova_id
                st.session_state['_ls_verificado'] = True
                st.rerun()
                return True

            elif prova and sessao and sessao['status'] in ('enviada', 'nota_liberada'):
                # Prova já enviada — vai para tela de resultado
                st.session_state['perfil']    = 'aluno'
                st.session_state['nome_aluno'] = nome
                st.session_state['prova_id']   = prova_id
                st.rerun()
                return True

        except Exception:
            st.query_params.clear()

    # Injeta script que lê localStorage e redireciona com query params
    _c.html("""
    <script>
    (function() {
        try {
            var nome  = localStorage.getItem('senai_aval_nome');
            var prova = localStorage.getItem('senai_aval_prova');
            var ts    = parseInt(localStorage.getItem('senai_aval_ts') || '0');
            // Só recupera se a sessão tiver menos de 4 horas
            var valido = nome && prova && (Date.now() - ts) < 4 * 60 * 60 * 1000;
            if (valido) {
                var url = window.location.pathname +
                    '?_ls_nome=' + encodeURIComponent(nome) +
                    '&_ls_prova=' + encodeURIComponent(prova);
                window.location.href = url;
            }
        } catch(e) {}
    })();
    </script>
    """, height=0)

    return False


def main():
    perfil = st.session_state.get('perfil')

    if perfil == 'professor':
        painel_professor()
    elif perfil == 'aluno':
        # Injeta escritor de localStorage sempre que aluno está na prova
        nome   = st.session_state.get('nome_aluno', '')
        pid    = st.session_state.get('prova_id', 0)
        if nome and pid:
            _injetar_localStorage_escritor(nome, pid)
        tela_aluno()
    else:
        # Tenta recuperar sessão do localStorage antes de mostrar tela inicial
        _tela_recuperacao()
        tela_inicial()


if __name__ == "__main__":
    main()