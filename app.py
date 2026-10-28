"""
Nida — Gestão e orientação para pacientes em FIV
Protótipo para o IV CodeCraft (PUC Goiás).

Rodar:  py -m pip install flask   e depois   py app.py
Abrir:  http://127.0.0.1:5000
Conta de demonstração: juliana@demo.com / nida2026
Para voltar aos dados de exemplo, apague o arquivo nida.db e rode de novo.
"""
import hmac
import json
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, abort, jsonify, render_template, request, redirect, url_for, g, session
from werkzeug.security import generate_password_hash, check_password_hash

import conteudo as C

app = Flask(__name__)
if os.environ.get("NIDA_ENV") == "production" and not os.environ.get("NIDA_SECRET"):
    raise RuntimeError("Defina NIDA_SECRET com uma chave forte antes de iniciar em produção.")
app.secret_key = os.environ.get("NIDA_SECRET") or os.urandom(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("NIDA_ENV") == "production",
    MAX_CONTENT_LENGTH=64 * 1024,
)
DB = "nida.db"
COMMUNITY_DB = os.environ.get("NIDA_COMMUNITY_DB", "nida-community.db")
app.config["COMMUNITY_MODERATOR_IDS"] = os.environ.get("NIDA_COMMUNITY_MODERATOR_IDS", "")
COMMUNITY_CATEGORIES = {
    "comecando": "Começando a FIV",
    "incerteza": "Lidando com a incerteza",
    "apoio": "Encontrando apoio",
    "relacionamentos": "Relacionamentos e família",
    "resultado": "Vivências após o resultado",
}
COMMUNITY_REACTIONS = {
    "estou_aqui": "Estou aqui com você",
    "obrigada": "Obrigada por compartilhar",
    "acolhimento": "Você merece acolhimento",
}
COMMUNITY_REPORT_REASONS = {
    "assédio": "Assédio ou desrespeito",
    "dados_pessoais": "Dados pessoais expostos",
    "orientacao_clinica": "Prescrição ou orientação clínica",
    "risco": "Possível risco imediato",
    "outro": "Outro motivo",
}
COMMUNITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS perfis (
    usuario_id INTEGER PRIMARY KEY,
    pseudonimo TEXT NOT NULL UNIQUE COLLATE NOCASE,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS publicacoes (
    id INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL,
    categoria TEXT NOT NULL,
    texto TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('pendente', 'aprovada', 'removida')),
    criada_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comentarios (
    id INTEGER PRIMARY KEY,
    publicacao_id INTEGER NOT NULL REFERENCES publicacoes(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL,
    texto TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('pendente', 'aprovado', 'removido')),
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reacoes (
    publicacao_id INTEGER NOT NULL REFERENCES publicacoes(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    criada_em TEXT NOT NULL,
    PRIMARY KEY (publicacao_id, usuario_id, tipo)
);
CREATE TABLE IF NOT EXISTS denuncias (
    id INTEGER PRIMARY KEY,
    denunciante_id INTEGER NOT NULL,
    tipo_alvo TEXT NOT NULL CHECK (tipo_alvo IN ('publicacao', 'comentario')),
    publicacao_id INTEGER REFERENCES publicacoes(id) ON DELETE CASCADE,
    comentario_id INTEGER REFERENCES comentarios(id) ON DELETE CASCADE,
    motivo TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('aberta', 'revisada')),
    criada_em TEXT NOT NULL,
    CHECK ((tipo_alvo = 'publicacao' AND publicacao_id IS NOT NULL AND comentario_id IS NULL)
        OR (tipo_alvo = 'comentario' AND comentario_id IS NOT NULL AND publicacao_id IS NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS denuncia_unica_publicacao
    ON denuncias (denunciante_id, publicacao_id) WHERE tipo_alvo = 'publicacao';
CREATE UNIQUE INDEX IF NOT EXISTS denuncia_unica_comentario
    ON denuncias (denunciante_id, comentario_id) WHERE tipo_alvo = 'comentario';
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    criado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS eventos_usuario_tipo_data
    ON eventos (usuario_id, tipo, criado_em);
CREATE TABLE IF NOT EXISTS auditoria_moderacao (
    id INTEGER PRIMARY KEY,
    moderadora_id INTEGER NOT NULL,
    tipo_alvo TEXT NOT NULL,
    alvo_id INTEGER NOT NULL,
    acao TEXT NOT NULL,
    criada_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS publicacoes_estado_data ON publicacoes (estado, criada_em);
CREATE INDEX IF NOT EXISTS comentarios_publicacao_estado ON comentarios (publicacao_id, estado);
CREATE INDEX IF NOT EXISTS denuncias_estado_data ON denuncias (estado, criada_em);
"""

DEMO_EMAIL, DEMO_SENHA = "juliana@demo.com", "nida2026"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


# ================================================================ banco
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.create_function("casefold", 1, lambda value: value.casefold() if isinstance(value, str) else "")
    return g.db


def community_db():
    if "community_db" not in g:
        g.community_db = sqlite3.connect(COMMUNITY_DB, timeout=5)
        g.community_db.row_factory = sqlite3.Row
        g.community_db.execute("PRAGMA foreign_keys=ON")
        g.community_db.executescript(COMMUNITY_SCHEMA)
    return g.community_db


@app.teardown_appcontext
def fechar_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()
    community_conn = g.pop("community_db", None)
    if community_conn:
        community_conn.close()


def comunidade_pseudonimo_valido(value):
    pseudonimo = value.strip()
    return (3 <= len(pseudonimo) <= 24
            and all(char.isalnum() or char in "_-" for char in pseudonimo))


def comunidade_moderadoras():
    configured = app.config["COMMUNITY_MODERATOR_IDS"]
    if isinstance(configured, str):
        try:
            return {int(item.strip()) for item in configured.split(",") if item.strip()}
        except ValueError as error:
            raise RuntimeError("NIDA_COMMUNITY_MODERATOR_IDS deve conter IDs numéricos separados por vírgula.") from error
    return {int(item) for item in configured}


def exigir_moderadora():
    if uid() not in comunidade_moderadoras():
        abort(403)


def comunidade_perfil(usuario_id):
    return community_db().execute(
        "SELECT pseudonimo FROM perfis WHERE usuario_id=?", (usuario_id,)
    ).fetchone()


def comunidade_registrar_evento(usuario_id, tipo, limite, janela):
    conn = community_db()
    conn.execute("BEGIN IMMEDIATE")
    agora = datetime.now().isoformat(timespec="seconds")
    inicio = (datetime.now() - janela).isoformat(timespec="seconds")
    total = conn.execute(
        "SELECT COUNT(*) FROM eventos WHERE usuario_id=? AND tipo=? AND criado_em>=?",
        (usuario_id, tipo, inicio),
    ).fetchone()[0]
    if total >= limite:
        abort(429, description="Você atingiu o limite temporário desta ação. Tente novamente mais tarde.")
    conn.execute(
        "INSERT INTO eventos (usuario_id, tipo, criado_em) VALUES (?,?,?)",
        (usuario_id, tipo, agora),
    )
    conn.execute("DELETE FROM eventos WHERE criado_em<?", ((datetime.now() - timedelta(days=30)).isoformat(),))
    return conn


# Toda tabela de dados tem usuario_id: cada usuária só enxerga o que é dela.
SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, senha_hash TEXT NOT NULL, criado_em TEXT);
CREATE TABLE IF NOT EXISTS paciente (
    id INTEGER PRIMARY KEY, usuario_id INTEGER UNIQUE NOT NULL, nome TEXT, data_nascimento TEXT,
    caminho TEXT DEFAULT 'particular', data_inicio TEXT, clinica TEXT);
CREATE TABLE IF NOT EXISTS etapas (
    id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL, ordem INTEGER, nome TEXT, duracao_dias INTEGER,
    concluida INTEGER DEFAULT 0, data_conclusao TEXT);
CREATE TABLE IF NOT EXISTS exames (
    id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL, nome TEXT, para_quem TEXT, status TEXT DEFAULT 'pendente');
CREATE TABLE IF NOT EXISTS compromissos (
    id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL, tipo TEXT, titulo TEXT, data_hora TEXT, local TEXT);
CREATE TABLE IF NOT EXISTS medicamentos (
    id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL, nome TEXT, classe TEXT, dose_texto TEXT, via TEXT,
    horario TEXT, data_inicio TEXT, data_fim TEXT);
CREATE TABLE IF NOT EXISTS doses (
    id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL, medicamento_id INTEGER, data_hora_prevista TEXT,
    tomada INTEGER DEFAULT 0, data_hora_real TEXT);
CREATE TABLE IF NOT EXISTS sintomas (
    id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL, data TEXT, nome TEXT, intensidade INTEGER,
    observacao TEXT, nivel INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS equipe (
    id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL, nome TEXT, especialidade TEXT, telefone TEXT);
CREATE TABLE IF NOT EXISTS humor (
    id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL, data TEXT, nivel INTEGER, nota TEXT);
"""


def criar_etapas(conn, uid, caminho):
    conn.execute("DELETE FROM etapas WHERE usuario_id=?", (uid,))
    nomes = ([C.ETAPA_SUS] if caminho == "SUS" else []) + C.ORDEM_ETAPAS
    for i, nome in enumerate(nomes):
        conn.execute("INSERT INTO etapas (usuario_id, ordem, nome, duracao_dias) VALUES (?,?,?,?)",
                     (uid, i, nome, C.ETAPAS[nome][0]))


def criar_exames_padrao(conn, uid):
    for nome, (quem, _, _) in C.EXAMES.items():
        conn.execute("INSERT INTO exames (usuario_id, nome, para_quem) VALUES (?,?,?)", (uid, nome, quem))


def gerar_doses(conn, uid, med_id, inicio, fim, horario):
    d = date.fromisoformat(inicio)
    while d <= date.fromisoformat(fim):
        conn.execute("INSERT INTO doses (usuario_id, medicamento_id, data_hora_prevista) VALUES (?,?,?)",
                     (uid, med_id, f"{d.isoformat()} {horario}"))
        d += timedelta(days=1)


def criar_usuaria(conn, email, senha, nome):
    cur = conn.execute("INSERT INTO usuarios (email, senha_hash, criado_em) VALUES (?,?,?)",
                       (email.lower().strip(), generate_password_hash(senha), datetime.now().isoformat()))
    uid = cur.lastrowid
    conn.execute("INSERT INTO paciente (usuario_id, nome) VALUES (?,?)", (uid, nome.strip()))
    criar_exames_padrao(conn, uid)
    return uid


def criar_demo(conn):
    """Conta de demonstração da Juliana, com dados relativos a hoje (ela está na estimulação ovariana)."""
    hoje = date.today()
    d = lambda n: (hoje + timedelta(days=n)).isoformat()
    uid = criar_usuaria(conn, DEMO_EMAIL, DEMO_SENHA, "Juliana Souza")
    conn.execute("UPDATE paciente SET data_nascimento='1993-04-12', caminho='particular', data_inicio=?, "
                 "clinica='Clínica Vida' WHERE usuario_id=?", (d(-33), uid))
    criar_etapas(conn, uid, "particular")
    conn.execute("UPDATE etapas SET concluida=1, data_conclusao=? WHERE usuario_id=? AND ordem=0", (d(-6), uid))
    conn.execute("UPDATE exames SET status='entregue' WHERE usuario_id=?", (uid,))
    conn.execute("UPDATE exames SET status='feito' WHERE usuario_id=? AND nome='Preventivo (citopatológico)'", (uid,))
    for tipo, titulo, dias, hora, local in [
        ("consulta", "Primeira consulta com a especialista", -35, "14:00", "Clínica Vida"),
        ("exame", "Coleta de sangue para sorologias", -25, "07:30", "Laboratório Central"),
        ("ultrassom", "Ultrassom de controle", 1, "09:00", "Clínica Vida"),
        ("exame", "Exame de sangue (estradiol)", 3, "07:30", "Laboratório Central"),
        ("consulta", "Retorno com a especialista", 5, "15:30", "Clínica Vida"),
    ]:
        conn.execute("INSERT INTO compromissos (usuario_id, tipo, titulo, data_hora, local) VALUES (?,?,?,?,?)",
                     (uid, tipo, titulo, f"{d(dias)} {hora}", local))
    meds = {}
    for nome, classe, via, hora, ini, fim in [
        ("Ácido fólico", "Ácido fólico", "oral", "08:00", -40, 60),
        ("Folitropina alfa", "Gonadotrofina (estímulo dos ovários)", "injeção", "20:00", -5, 4),
        ("Cetrorrelix", "Antagonista de GnRH", "injeção", "08:00", -1, 4),
    ]:
        cur = conn.execute("INSERT INTO medicamentos (usuario_id, nome, classe, dose_texto, via, horario, data_inicio, "
                           "data_fim) VALUES (?,?,?,'conforme receita',?,?,?,?)",
                           (uid, nome, classe, via, hora, d(ini), d(fim)))
        meds[nome] = cur.lastrowid
        gerar_doses(conn, uid, cur.lastrowid, d(ini), d(fim), hora)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute("UPDATE doses SET tomada=1, data_hora_real=data_hora_prevista WHERE usuario_id=? "
                 "AND data_hora_prevista < ?", (uid, agora))
    # Uma dose de ontem fica sem marcar, para a demo mostrar uma dose atrasada.
    conn.execute("UPDATE doses SET tomada=0, data_hora_real=NULL WHERE medicamento_id=? AND data_hora_prevista=?",
                 (meds["Cetrorrelix"], f"{d(-1)} 08:00"))
    for dias, nome, inten, obs in [
        (-4, "Inchaço ou vermelhidão no local da injeção", 2, "Passou em algumas horas"),
        (-2, "Barriga estufada", 3, "Mais à noite"),
        (-1, "Mudança de humor", 5, "Ansiosa com o ultrassom"),
    ]:
        conn.execute("INSERT INTO sintomas (usuario_id, data, nome, intensidade, observacao, nivel) "
                     "VALUES (?,?,?,?,?,0)", (uid, d(dias), nome, inten, obs))
    for dias, nivel, nota in [(-3, 4, "Dia tranquilo"), (-2, 3, ""), (-1, 2, "Chorei à toa, acho que são os hormônios")]:
        conn.execute("INSERT INTO humor (usuario_id, data, nivel, nota) VALUES (?,?,?,?)", (uid, d(dias), nivel, nota))
    conn.execute("INSERT INTO equipe (usuario_id, nome, especialidade, telefone) VALUES "
                 "(?, 'Clínica Vida', 'Central de atendimento', '(62) 0000-0000')", (uid,))


def iniciar_banco():
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
        criar_demo(conn)
    conn.commit()
    conn.close()


# ================================================================ sessão e acesso
ROTAS_PUBLICAS = {"entrar", "cadastrar", "static"}


def uid():
    return session.get("uid")


def csrf_token():
    token = session.get("_csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def validar_csrf():
    esperado = session.get("_csrf_token", "")
    recebido = request.form.get("csrf_token", "")
    if not esperado or not recebido or not hmac.compare_digest(esperado, recebido):
        abort(400, description="Token de segurança inválido. Recarregue a página e tente novamente.")


@app.before_request
def exigir_login():
    if request.endpoint in ROTAS_PUBLICAS or request.endpoint is None:
        return None
    if not uid():
        return redirect(url_for("entrar"))
    # Conta nova ainda sem os dados do tratamento: completa primeiro em "Minha conta".
    pac = paciente()
    if pac is None:
        session.clear()
        return redirect(url_for("entrar"))
    if not pac["data_inicio"] and request.endpoint not in ("minha_conta", "sair"):
        return redirect(url_for("minha_conta"))
    return None


def paciente():
    return db().execute("SELECT * FROM paciente WHERE usuario_id=?", (uid(),)).fetchone()


# ================================================================ lógica
def agora_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def linha_do_tempo():
    """Soma as durações a partir do início. Etapa concluída numa data real move as seguintes."""
    pac = paciente()
    etapas = db().execute("SELECT * FROM etapas WHERE usuario_id=? ORDER BY ordem", (uid(),)).fetchall()
    cursor, hoje = date.fromisoformat(pac["data_inicio"]), date.today()
    resultado, atual_marcada = [], False
    for e in etapas:
        inicio = cursor
        if e["concluida"] and e["data_conclusao"]:
            fim = max(date.fromisoformat(e["data_conclusao"]), inicio)
        else:
            fim = inicio + timedelta(days=e["duracao_dias"] - 1)
        if e["concluida"]:
            status = "concluida"
        elif not atual_marcada:
            status, atual_marcada = "atual", True
        else:
            status = "futura"
        dur, resumo, esperar, efeitos, fts = C.ETAPAS.get(e["nome"], (0, "", "", [], []))
        resultado.append({**dict(e), "inicio": inicio, "fim": fim, "status": status,
                          "atrasada": status == "atual" and hoje > fim, "resumo": resumo,
                          "esperar": esperar, "efeitos": efeitos, "fontes": C.fontes(fts)})
        cursor = fim + timedelta(days=1)
    return pac, resultado


def etapa_atual(etapas):
    return next((e for e in etapas if e["status"] == "atual"), None)


def doses_resumo():
    agora, c, u = agora_str(), db(), uid()
    base = "FROM doses d JOIN medicamentos m ON m.id=d.medicamento_id WHERE d.usuario_id=?"
    proxima = c.execute(f"SELECT d.*, m.nome, m.dose_texto, m.via {base} AND d.tomada=0 AND d.data_hora_prevista >= ? "
                        "ORDER BY d.data_hora_prevista LIMIT 1", (u, agora)).fetchone()
    atrasadas = c.execute(f"SELECT d.*, m.nome, m.dose_texto, m.via {base} AND d.tomada=0 AND d.data_hora_prevista < ? "
                          "ORDER BY d.data_hora_prevista", (u, agora)).fetchall()
    total = c.execute("SELECT COUNT(*) FROM doses WHERE usuario_id=? AND data_hora_prevista < ?", (u, agora)).fetchone()[0]
    tomadas = c.execute("SELECT COUNT(*) FROM doses WHERE usuario_id=? AND tomada=1 AND data_hora_prevista < ?",
                        (u, agora)).fetchone()[0]
    doses_hoje = c.execute(f"SELECT d.*, m.nome, m.dose_texto, m.via, m.classe {base} "
                           "AND substr(d.data_hora_prevista,1,10)=? ORDER BY d.data_hora_prevista",
                           (u, date.today().isoformat())).fetchall()
    return {"proxima": proxima, "atrasadas": atrasadas, "tomadas": tomadas, "total": total,
            "hoje": doses_hoje, "hoje_tomadas": sum(1 for x in doses_hoje if x["tomada"]),
            "adesao": round(100 * tomadas / total) if total else 100}


def nivel_sintoma(nome, intensidade):
    if nome in C.ALERTA_EMERGENCIA:
        return 2
    if nome in C.ALERTA_CLINICA or intensidade >= 8:
        return 1
    return 0


def telefone_clinica():
    row = db().execute("SELECT telefone FROM equipe WHERE usuario_id=? ORDER BY id LIMIT 1", (uid(),)).fetchone()
    return row["telefone"] if row else None


def idade(pac):
    if not pac["data_nascimento"]:
        return None
    return (date.today() - date.fromisoformat(pac["data_nascimento"])).days // 365


# ================================================================ filtros e globais
@app.template_filter("br")
def data_br(valor):
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    if not valor:
        return "—"
    partes = str(valor).split(" ")
    d = date.fromisoformat(partes[0]).strftime("%d/%m/%Y")
    return f"{d} {partes[1]}" if len(partes) > 1 else d


@app.template_filter("curta")
def data_curta(valor):
    if not valor:
        return "—"
    if isinstance(valor, date):
        return f"{valor.day} {MESES_CURTOS[valor.month - 1]}"
    partes = str(valor).split(" ")
    d = date.fromisoformat(partes[0])
    txt = f"{d.day} {MESES_CURTOS[d.month - 1]}"
    return f"{txt}, {partes[1]}" if len(partes) > 1 else txt


@app.template_filter("tel")
def tel_link(valor):
    return "tel:" + "".join(ch for ch in (valor or "") if ch.isdigit())


@app.context_processor
def comuns():
    hoje = date.today()
    nome = None
    if uid():
        p = db().execute("SELECT nome FROM paciente WHERE usuario_id=?", (uid(),)).fetchone()
        nome = p["nome"] if p else None
    return {"hoje": hoje, "agora": datetime.now().strftime("%H:%M"),
            "hoje_extenso": f"{hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}",
            "agora_str": agora_str(), "nome_usuaria": nome, "csrf_token": csrf_token}


# ================================================================ entrada, cadastro e conta
@app.route("/entrar", methods=["GET", "POST"])
def entrar():
    if uid():
        return redirect(url_for("painel"))
    erro = None
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        senha = request.form.get("senha", "")
        u = db().execute("SELECT * FROM usuarios WHERE email=?", (email,)).fetchone()
        if u and check_password_hash(u["senha_hash"], senha):
            session.clear()
            session["uid"] = u["id"]
            return redirect(url_for("painel"))
        erro = "E-mail ou senha incorretos."
    return render_template("entrar.html", erro=erro, aba="entrar", demo=(DEMO_EMAIL, DEMO_SENHA))


@app.route("/cadastrar", methods=["POST"])
def cadastrar():
    f = request.form
    email, senha, nome = f.get("email", "").lower().strip(), f.get("senha", ""), f.get("nome", "").strip()
    erro = None
    if not nome or "@" not in email:
        erro = "Preencha nome e um e-mail válido."
    elif len(senha) < 8:
        erro = "A senha precisa ter pelo menos 8 caracteres."
    elif senha != f.get("senha2", ""):
        erro = "As senhas não conferem."
    elif db().execute("SELECT 1 FROM usuarios WHERE email=?", (email,)).fetchone():
        erro = "Já existe uma conta com este e-mail."
    if erro:
        return render_template("entrar.html", erro=erro, aba="cadastrar", demo=(DEMO_EMAIL, DEMO_SENHA))
    novo = criar_usuaria(db(), email, senha, nome)
    db().commit()
    session.clear()
    session["uid"] = novo
    return redirect(url_for("minha_conta"))


@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("entrar"))


@app.route("/minha-conta", methods=["GET", "POST"])
def minha_conta():
    pac = paciente()
    primeira_vez = not pac["data_inicio"]
    if request.method == "POST":
        f = request.form
        db().execute("UPDATE paciente SET nome=?, data_nascimento=?, caminho=?, data_inicio=?, clinica=? "
                     "WHERE usuario_id=?", (f["nome"], f["data_nascimento"], f["caminho"], f["data_inicio"],
                                            f.get("clinica", ""), uid()))
        # Refaz a linha do tempo se é a primeira vez ou se o caminho ou o início mudaram.
        if primeira_vez or pac["caminho"] != f["caminho"] or pac["data_inicio"] != f["data_inicio"]:
            criar_etapas(db(), uid(), f["caminho"])
        db().commit()
        return redirect(url_for("painel" if primeira_vez else "minha_conta"))
    email = db().execute("SELECT email FROM usuarios WHERE id=?", (uid(),)).fetchone()["email"]
    return render_template("minha_conta.html", pac=pac, primeira_vez=primeira_vez, email=email)


# ================================================================ telas do tratamento
@app.route("/")
def painel():
    pac, etapas = linha_do_tempo()
    u = uid()
    exames = db().execute("SELECT status FROM exames WHERE usuario_id=?", (u,)).fetchall()
    proximos = db().execute("SELECT * FROM compromissos WHERE usuario_id=? AND data_hora >= ? ORDER BY data_hora LIMIT 4",
                            (u, agora_str())).fetchall()
    limite = (date.today() - timedelta(days=7)).isoformat()
    alertas = db().execute("SELECT * FROM sintomas WHERE usuario_id=? AND nivel > 0 AND data >= ? "
                           "ORDER BY data DESC, id DESC", (u, limite)).fetchall()
    return render_template("painel.html", pac=pac, etapas=etapas, atual=etapa_atual(etapas), doses=doses_resumo(),
                           exames_pend=sum(1 for e in exames if e["status"] != "entregue"),
                           exames_total=len(exames), proximos=proximos, alertas=alertas,
                           dias_restantes=max(0, (etapas[-1]["fim"] - date.today()).days),
                           telefone=telefone_clinica())


@app.route("/linha-do-tempo")
def tela_linha_do_tempo():
    pac, etapas = linha_do_tempo()
    concluidas = sum(1 for e in etapas if e["status"] == "concluida")
    return render_template("linha_do_tempo.html", pac=pac, etapas=etapas, atual=etapa_atual(etapas),
                           concluidas=concluidas, pct=round(100 * concluidas / len(etapas)),
                           dias_restantes=max(0, (etapas[-1]["fim"] - date.today()).days),
                           duracao=(etapas[-1]["fim"] - etapas[0]["inicio"]).days + 1)


@app.route("/etapa/<int:id>/concluir", methods=["POST"])
def concluir_etapa(id):
    db().execute("UPDATE etapas SET concluida=1, data_conclusao=? WHERE id=? AND usuario_id=?",
                 (request.form.get("data") or date.today().isoformat(), id, uid()))
    db().commit()
    return redirect(url_for("tela_linha_do_tempo"))


@app.route("/etapa/<int:id>/reabrir", methods=["POST"])
def reabrir_etapa(id):
    db().execute("UPDATE etapas SET concluida=0, data_conclusao=NULL WHERE id=? AND usuario_id=?", (id, uid()))
    db().commit()
    return redirect(url_for("tela_linha_do_tempo"))


@app.route("/etapa/<int:id>/duracao", methods=["POST"])
def mudar_duracao(id):
    db().execute("UPDATE etapas SET duracao_dias=? WHERE id=? AND usuario_id=?",
                 (max(1, int(request.form["dias"])), id, uid()))
    db().commit()
    return redirect(url_for("tela_linha_do_tempo"))


@app.route("/exames", methods=["GET", "POST"])
def exames():
    if request.method == "POST":
        f = request.form
        nome = f.get("outro", "").strip() if f["nome"] == "Outro" else f["nome"]
        if nome:
            db().execute("INSERT INTO exames (usuario_id, nome, para_quem) VALUES (?,?,?)", (uid(), nome, f["para_quem"]))
            db().commit()
        return redirect(url_for("exames"))
    lista = db().execute("SELECT * FROM exames WHERE usuario_id=? ORDER BY CASE status WHEN 'pendente' THEN 0 "
                         "WHEN 'feito' THEN 1 ELSE 2 END, id", (uid(),)).fetchall()
    cont = {s: sum(1 for e in lista if e["status"] == s) for s in ("pendente", "feito", "entregue")}
    return render_template("exames.html", exames=lista, cont=cont, info=C.EXAMES, F=C.F)


@app.route("/exames/<int:id>/status", methods=["POST"])
def status_exame(id):
    db().execute("UPDATE exames SET status=? WHERE id=? AND usuario_id=?", (request.form["status"], id, uid()))
    db().commit()
    return redirect(url_for("exames"))


@app.route("/exames/<int:id>/excluir", methods=["POST"])
def excluir_exame(id):
    db().execute("DELETE FROM exames WHERE id=? AND usuario_id=?", (id, uid()))
    db().commit()
    return redirect(url_for("exames"))


TIPOS_AGENDA = ["consulta", "exame", "ultrassom", "vacina", "outro"]


@app.route("/agenda", methods=["GET", "POST"])
def agenda():
    if request.method == "POST":
        f = request.form
        db().execute("INSERT INTO compromissos (usuario_id, tipo, titulo, data_hora, local) VALUES (?,?,?,?,?)",
                     (uid(), f["tipo"], f["titulo"], f"{f['data']} {f['hora']}", f["local"]))
        db().commit()
        return redirect(url_for("agenda"))
    aba = request.args.get("aba", "proximos")
    tipo = request.args.get("tipo", "todos")
    sql = "SELECT * FROM compromissos WHERE usuario_id=? AND data_hora " + (">= ?" if aba == "proximos" else "< ?")
    params = [uid(), agora_str()]
    if tipo in TIPOS_AGENDA:
        sql += " AND tipo = ?"
        params.append(tipo)
    sql += " ORDER BY data_hora" + ("" if aba == "proximos" else " DESC")
    return render_template("agenda.html", lista=db().execute(sql, params).fetchall(), aba=aba, tipo=tipo,
                           tipos=TIPOS_AGENDA)


@app.route("/agenda/<int:id>/excluir", methods=["POST"])
def excluir_compromisso(id):
    db().execute("DELETE FROM compromissos WHERE id=? AND usuario_id=?", (id, uid()))
    db().commit()
    return redirect(url_for("agenda"))


@app.route("/medicacao", methods=["GET", "POST"])
def medicacao():
    if request.method == "POST":
        f = request.form
        classe = (f.get("classe_outro", "").strip() or "Outro") if f["classe"] == "Outro" else f["classe"]
        cur = db().execute("INSERT INTO medicamentos (usuario_id, nome, classe, dose_texto, via, horario, data_inicio, "
                           "data_fim) VALUES (?,?,?,?,?,?,?,?)", (uid(), f["nome"], classe, f["dose_texto"], f["via"],
                                                                 f["horario"], f["data_inicio"], f["data_fim"]))
        gerar_doses(db(), uid(), cur.lastrowid, f["data_inicio"], f["data_fim"], f["horario"])
        db().commit()
        return redirect(url_for("medicacao"))
    aba = request.args.get("aba", "hoje")
    meds = db().execute("SELECT * FROM medicamentos WHERE usuario_id=? ORDER BY data_inicio", (uid(),)).fetchall()
    classes_json = json.dumps({k: {"serve": v[0], "efeitos": v[1], "fonte": C.F[v[2]] if v[2] else None}
                               for k, v in C.CLASSES.items()}, ensure_ascii=False)
    return render_template("medicacao.html", meds=meds, doses=doses_resumo(), aba=aba, classes=C.CLASSES,
                           classes_json=classes_json, F=C.F,
                           tem_gatilho=any(m["classe"] == "Gatilho (hCG)" for m in meds))


@app.route("/dose/<int:id>/tomar", methods=["POST"])
def tomar_dose(id):
    db().execute("UPDATE doses SET tomada=1, data_hora_real=? WHERE id=? AND usuario_id=?", (agora_str(), id, uid()))
    db().commit()
    return redirect(request.referrer or url_for("medicacao"))


@app.route("/medicacao/<int:id>/excluir", methods=["POST"])
def excluir_medicamento(id):
    db().execute("DELETE FROM doses WHERE medicamento_id=? AND usuario_id=?", (id, uid()))
    db().execute("DELETE FROM medicamentos WHERE id=? AND usuario_id=?", (id, uid()))
    db().commit()
    return redirect(url_for("medicacao", aba="todas"))


@app.route("/sintomas", methods=["GET", "POST"])
def sintomas():
    novo = None
    if request.method == "POST":
        f = request.form
        nome = (f.get("outro", "").strip() or "Outro") if f["nome"] == "Outro" else f["nome"]
        inten = int(f.get("intensidade", 0))
        nivel = nivel_sintoma(nome, inten)
        db().execute("INSERT INTO sintomas (usuario_id, data, nome, intensidade, observacao, nivel) VALUES (?,?,?,?,?,?)",
                     (uid(), f["data"], nome, inten, f.get("observacao", ""), nivel))
        db().commit()
        novo = {"nome": nome, "nivel": nivel}
    _, etapas = linha_do_tempo()
    atual = etapa_atual(etapas)
    esperados = atual["efeitos"] if atual else []
    lista = db().execute("SELECT * FROM sintomas WHERE usuario_id=? ORDER BY data DESC, id DESC", (uid(),)).fetchall()
    return render_template("sintomas.html", sintomas=lista, novo=novo, atual=atual, esperados=esperados,
                           comuns=C.SINTOMAS_COMUNS, clinica=C.ALERTA_CLINICA, emergencia=C.ALERTA_EMERGENCIA,
                           fontes_alerta=C.fontes(C.FONTES_ALERTA), telefone=telefone_clinica(),
                           cont={"total": len(lista), "esperados": sum(1 for s in lista if s["nome"] in esperados),
                                 "alertas": sum(1 for s in lista if s["nivel"] > 0)})


@app.route("/apoio-emocional", methods=["GET", "POST"])
def apoio():
    if request.method == "POST":
        validar_csrf()
        tipo = request.form.get("tipo", "humor")
        nota = request.form.get("nota", "").strip()
        if tipo == "diario":
            data_registro = request.form.get("data", "")
            try:
                data_registro = date.fromisoformat(data_registro)
            except ValueError:
                data_registro = None
            if data_registro is None or data_registro > date.today():
                return render_template("apoio.html", **contexto_apoio(),
                                       erro="Escolha uma data válida, até hoje.", diario_ativo=True,
                                       diario_data=data_registro.isoformat() if data_registro else date.today().isoformat()), 400
            if not nota:
                return render_template("apoio.html", **contexto_apoio(),
                                       erro="Escreva algo antes de salvar no diário.", diario_ativo=True,
                                       diario_data=data_registro.isoformat()), 400
            if len(nota) > 3000:
                return render_template("apoio.html", **contexto_apoio(),
                                       erro="O texto do diário deve ter até 3.000 caracteres.", diario_ativo=True,
                                       diario_data=data_registro.isoformat()), 400
            nivel = None
        elif tipo == "humor":
            try:
                nivel = int(request.form.get("nivel", ""))
            except ValueError:
                nivel = 0
            if nivel not in C.HUMORES:
                return render_template("apoio.html", **contexto_apoio(),
                                       erro="Escolha uma opção válida para registrar como está."), 400
            if len(nota) > 500:
                return render_template("apoio.html", **contexto_apoio(),
                                       erro="A anotação deve ter até 500 caracteres."), 400
        else:
            abort(400, description="Tipo de registro inválido.")
        db().execute("INSERT INTO humor (usuario_id, data, nivel, nota) VALUES (?,?,?,?)",
                     (uid(), data_registro.isoformat() if tipo == "diario" else date.today().isoformat(), nivel, nota))
        db().commit()
        if tipo == "diario":
            return redirect(url_for("apoio", diario="1", registro="salvo", data=data_registro.isoformat()))
        return redirect(url_for("apoio"))

    diario_data = request.args.get("data", "")
    try:
        selecionada = date.fromisoformat(diario_data)
        if selecionada > date.today():
            raise ValueError
    except ValueError:
        selecionada = date.today()
    return render_template("apoio.html", **contexto_apoio(), diario_ativo=request.args.get("diario") == "1",
                           diario_data=selecionada.isoformat())


@app.route("/apoio-emocional/comunidade")
def comunidade():
    categoria = request.args.get("categoria", "")
    if categoria and categoria not in COMMUNITY_CATEGORIES:
        abort(400, description="Categoria da comunidade inválida.")
    conn = community_db()
    usuario_id = uid()
    perfil = comunidade_perfil(usuario_id)
    posts = conn.execute(
        """
        SELECT p.id, p.categoria, p.texto, p.estado, p.criada_em,
               (p.usuario_id=?) AS sou_autora,
               COALESCE(perfil.pseudonimo, 'Participante') AS pseudonimo,
               (SELECT COUNT(*) FROM comentarios c
                WHERE c.publicacao_id=p.id AND c.estado='aprovado') AS total_comentarios
        FROM publicacoes p
        LEFT JOIN perfis perfil ON perfil.usuario_id=p.usuario_id
        WHERE (p.estado='aprovada' OR (p.estado='pendente' AND p.usuario_id=?))
          AND (?='' OR p.categoria=?)
        ORDER BY p.criada_em DESC, p.id DESC LIMIT 50
        """,
        (usuario_id, usuario_id, categoria, categoria),
    ).fetchall()
    publicacao_ids = [post["id"] for post in posts]
    comentarios_por_publicacao = {post_id: [] for post_id in publicacao_ids}
    reacoes_por_publicacao = {post_id: {} for post_id in publicacao_ids}
    if publicacao_ids:
        placeholders = ",".join("?" for _ in publicacao_ids)
        comments = conn.execute(
            f"""
            SELECT c.id, c.publicacao_id, c.texto, c.estado, c.criado_em,
                   (c.usuario_id=?) AS sou_autora,
                   COALESCE(perfil.pseudonimo, 'Participante') AS pseudonimo
            FROM comentarios c
            LEFT JOIN perfis perfil ON perfil.usuario_id=c.usuario_id
            WHERE c.publicacao_id IN ({placeholders})
              AND (c.estado='aprovado' OR (c.estado='pendente' AND c.usuario_id=?))
            ORDER BY c.criado_em, c.id
            """,
            (usuario_id, *publicacao_ids, usuario_id),
        ).fetchall()
        for comment in comments:
            comentarios_por_publicacao[comment["publicacao_id"]].append(dict(comment))
        reactions = conn.execute(
            f"""
            SELECT publicacao_id, tipo, COUNT(*) AS total,
                   MAX(CASE WHEN usuario_id=? THEN 1 ELSE 0 END) AS minha
            FROM reacoes WHERE publicacao_id IN ({placeholders})
            GROUP BY publicacao_id, tipo
            """,
            (usuario_id, *publicacao_ids),
        ).fetchall()
        for reaction in reactions:
            reacoes_por_publicacao[reaction["publicacao_id"]][reaction["tipo"]] = dict(reaction)

    feed = []
    for post in posts:
        item = dict(post)
        item["comentarios"] = comentarios_por_publicacao[post["id"]]
        item["reacoes"] = reacoes_por_publicacao[post["id"]]
        feed.append(item)
    moderators = comunidade_moderadoras()
    notices = {
        "pseudonimo_salvo": "Seu pseudônimo foi atualizado.",
        "pseudonimo_invalido": "Use um pseudônimo de 3 a 24 letras, números, hífen ou sublinhado. Evite seu nome real.",
        "pseudonimo_em_uso": "Esse pseudônimo já está sendo usado. Escolha outro.",
        "perfil_necessario": "Escolha um pseudônimo antes de publicar ou comentar.",
        "publicacao_publicada": "Seu relato já está visível para as participantes da comunidade.",
        "comentario_publicado": "Seu comentário já está visível na conversa.",
        "reacao_salva": "Sua reação foi atualizada.",
        "denuncia_enviada": "A denúncia foi enviada em privado para revisão.",
        "denuncia_repetida": "Você já enviou uma denúncia sobre este conteúdo.",
        "conteudo_excluido": "O conteúdo foi removido.",
        "categoria_invalida": "Escolha um assunto válido para a publicação.",
        "texto_invalido": "Revise o texto: a publicação precisa ter até 3.000 caracteres.",
        "comentario_invalido": "Revise o texto: o comentário precisa ter até 1.200 caracteres.",
        "motivo_invalido": "Escolha um motivo válido para a denúncia.",
    }
    return render_template(
        "comunidade.html",
        pseudonimo=perfil["pseudonimo"] if perfil else "",
        posts=feed,
        categoria=categoria,
        categorias=COMMUNITY_CATEGORIES,
        reacoes=COMMUNITY_REACTIONS,
        motivos_denuncia=COMMUNITY_REPORT_REASONS,
        moderadora=usuario_id in moderators,
        aviso=notices.get(request.args.get("aviso", "")),
    )


@app.route("/apoio-emocional/comunidade/perfil", methods=["POST"])
def comunidade_atualizar_perfil():
    validar_csrf()
    pseudonimo = request.form.get("pseudonimo", "").strip()
    if not comunidade_pseudonimo_valido(pseudonimo):
        return redirect(url_for("comunidade", aviso="pseudonimo_invalido"))
    conn = community_db()
    agora = datetime.now().isoformat(timespec="seconds")
    try:
        perfil = comunidade_perfil(uid())
        if perfil:
            conn.execute(
                "UPDATE perfis SET pseudonimo=?, atualizado_em=? WHERE usuario_id=?",
                (pseudonimo, agora, uid()),
            )
        else:
            conn.execute(
                "INSERT INTO perfis (usuario_id, pseudonimo, criado_em, atualizado_em) VALUES (?,?,?,?)",
                (uid(), pseudonimo, agora, agora),
            )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return redirect(url_for("comunidade", aviso="pseudonimo_em_uso"))
    return redirect(url_for("comunidade", aviso="pseudonimo_salvo"))


@app.route("/apoio-emocional/comunidade/publicacoes", methods=["POST"])
def comunidade_publicar():
    validar_csrf()
    categoria = request.form.get("categoria", "")
    texto = request.form.get("texto", "").strip()
    if categoria not in COMMUNITY_CATEGORIES:
        return redirect(url_for("comunidade", aviso="categoria_invalida"))
    if not texto or len(texto) > 3000:
        return redirect(url_for("comunidade", aviso="texto_invalido"))
    if comunidade_perfil(uid()) is None:
        return redirect(url_for("comunidade", aviso="perfil_necessario"))
    conn = comunidade_registrar_evento(uid(), "publicacao", 5, timedelta(hours=1))
    conn.execute(
        "INSERT INTO publicacoes (usuario_id, categoria, texto, estado, criada_em) VALUES (?,?,?,'aprovada',?)",
        (uid(), categoria, texto, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return redirect(url_for("comunidade", aviso="publicacao_publicada"))


@app.route("/apoio-emocional/comunidade/publicacoes/<int:id>/publicar", methods=["POST"])
def comunidade_publicar_legacy(id):
    validar_csrf()
    conn = community_db()
    cursor = conn.execute(
        "UPDATE publicacoes SET estado='aprovada' WHERE id=? AND usuario_id=? AND estado='pendente'",
        (id, uid()),
    )
    if not cursor.rowcount:
        conn.rollback()
        abort(404)
    conn.commit()
    return redirect(url_for("comunidade", aviso="publicacao_publicada"))


@app.route("/apoio-emocional/comunidade/publicacoes/<int:id>/comentarios", methods=["POST"])
def comunidade_comentar(id):
    validar_csrf()
    texto = request.form.get("texto", "").strip()
    if not texto or len(texto) > 1200:
        return redirect(url_for("comunidade", aviso="comentario_invalido"))
    conn = community_db()
    if comunidade_perfil(uid()) is None:
        return redirect(url_for("comunidade", aviso="perfil_necessario"))
    if conn.execute("SELECT 1 FROM publicacoes WHERE id=? AND estado='aprovada'", (id,)).fetchone() is None:
        abort(404)
    conn = comunidade_registrar_evento(uid(), "comentario", 20, timedelta(hours=1))
    conn.execute(
        "INSERT INTO comentarios (publicacao_id, usuario_id, texto, estado, criado_em) "
        "VALUES (?,?,?,'aprovado',?)",
        (id, uid(), texto, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return redirect(url_for("comunidade", aviso="comentario_publicado"))


@app.route("/apoio-emocional/comunidade/comentarios/<int:id>/publicar", methods=["POST"])
def comunidade_publicar_comentario_legacy(id):
    validar_csrf()
    conn = community_db()
    cursor = conn.execute(
        "UPDATE comentarios SET estado='aprovado' WHERE id=? AND usuario_id=? AND estado='pendente'",
        (id, uid()),
    )
    if not cursor.rowcount:
        conn.rollback()
        abort(404)
    conn.commit()
    return redirect(url_for("comunidade", aviso="comentario_publicado"))


@app.route("/apoio-emocional/comunidade/publicacoes/<int:id>/reacoes", methods=["POST"])
def comunidade_reagir(id):
    validar_csrf()
    tipo = request.form.get("tipo", "")
    if tipo not in COMMUNITY_REACTIONS:
        abort(400, description="Reação inválida.")
    conn = community_db()
    if conn.execute("SELECT 1 FROM publicacoes WHERE id=? AND estado='aprovada'", (id,)).fetchone() is None:
        abort(404)
    conn = comunidade_registrar_evento(uid(), "reacao", 60, timedelta(hours=1))
    existing = conn.execute(
        "SELECT 1 FROM reacoes WHERE publicacao_id=? AND usuario_id=? AND tipo=?",
        (id, uid(), tipo),
    ).fetchone()
    if existing:
        conn.execute(
            "DELETE FROM reacoes WHERE publicacao_id=? AND usuario_id=? AND tipo=?",
            (id, uid(), tipo),
        )
    else:
        conn.execute(
            "INSERT INTO reacoes (publicacao_id, usuario_id, tipo, criada_em) VALUES (?,?,?,?)",
            (id, uid(), tipo, datetime.now().isoformat(timespec="seconds")),
        )
    conn.commit()
    return redirect(url_for("comunidade", aviso="reacao_salva"))


@app.route("/apoio-emocional/comunidade/denuncias", methods=["POST"])
def comunidade_denunciar():
    validar_csrf()
    tipo_alvo = request.form.get("tipo_alvo", "")
    motivo = request.form.get("motivo", "")
    if motivo not in COMMUNITY_REPORT_REASONS or tipo_alvo not in ("publicacao", "comentario"):
        return redirect(url_for("comunidade", aviso="motivo_invalido"))
    try:
        alvo_id = int(request.form.get("alvo_id", ""))
    except ValueError:
        abort(400, description="Conteúdo inválido.")
    conn = community_db()
    if tipo_alvo == "publicacao":
        alvo = conn.execute(
            "SELECT id FROM publicacoes WHERE id=? AND estado='aprovada'", (alvo_id,)
        ).fetchone()
    else:
        alvo = conn.execute(
            "SELECT id FROM comentarios WHERE id=? AND estado='aprovado'", (alvo_id,)
        ).fetchone()
    if alvo is None:
        abort(404)
    conn = comunidade_registrar_evento(uid(), "denuncia", 5, timedelta(days=1))
    if tipo_alvo == "publicacao":
        duplicada = conn.execute(
            "SELECT 1 FROM denuncias WHERE denunciante_id=? AND publicacao_id=?",
            (uid(), alvo_id),
        ).fetchone()
    else:
        duplicada = conn.execute(
            "SELECT 1 FROM denuncias WHERE denunciante_id=? AND comentario_id=?",
            (uid(), alvo_id),
        ).fetchone()
    if duplicada:
        conn.commit()
        return redirect(url_for("comunidade", aviso="denuncia_repetida"))
    values = (uid(), tipo_alvo, alvo_id if tipo_alvo == "publicacao" else None,
              alvo_id if tipo_alvo == "comentario" else None, motivo,
              datetime.now().isoformat(timespec="seconds"))
    try:
        conn.execute(
            "INSERT INTO denuncias (denunciante_id, tipo_alvo, publicacao_id, comentario_id, motivo, estado, criada_em) "
            "VALUES (?,?,?,?,?,'aberta',?)",
            values,
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return redirect(url_for("comunidade", aviso="denuncia_repetida"))
    return redirect(url_for("comunidade", aviso="denuncia_enviada"))


@app.route("/apoio-emocional/comunidade/publicacoes/<int:id>/excluir", methods=["POST"])
def comunidade_excluir_publicacao(id):
    validar_csrf()
    conn = comunidade_registrar_evento(uid(), "exclusao", 10, timedelta(hours=1))
    cursor = conn.execute("DELETE FROM publicacoes WHERE id=? AND usuario_id=?", (id, uid()))
    if not cursor.rowcount:
        conn.rollback()
        abort(404)
    conn.commit()
    return redirect(url_for("comunidade", aviso="conteudo_excluido"))


@app.route("/apoio-emocional/comunidade/comentarios/<int:id>/excluir", methods=["POST"])
def comunidade_excluir_comentario(id):
    validar_csrf()
    conn = comunidade_registrar_evento(uid(), "exclusao", 10, timedelta(hours=1))
    cursor = conn.execute("DELETE FROM comentarios WHERE id=? AND usuario_id=?", (id, uid()))
    if not cursor.rowcount:
        conn.rollback()
        abort(404)
    conn.commit()
    return redirect(url_for("comunidade", aviso="conteudo_excluido"))


@app.route("/apoio-emocional/comunidade/moderacao")
def comunidade_moderacao():
    exigir_moderadora()
    conn = community_db()
    publicacoes = conn.execute(
        """
        SELECT p.id, p.categoria, p.texto, p.criada_em,
               COALESCE(perfil.pseudonimo, 'Participante') AS pseudonimo
        FROM publicacoes p LEFT JOIN perfis perfil ON perfil.usuario_id=p.usuario_id
        WHERE p.estado='pendente' ORDER BY p.criada_em, p.id
        """
    ).fetchall()
    comentarios = conn.execute(
        """
        SELECT c.id, c.publicacao_id, c.texto, c.criado_em,
               COALESCE(perfil.pseudonimo, 'Participante') AS pseudonimo
        FROM comentarios c LEFT JOIN perfis perfil ON perfil.usuario_id=c.usuario_id
        WHERE c.estado='pendente' ORDER BY c.criado_em, c.id
        """
    ).fetchall()
    denuncias = conn.execute(
        """
        SELECT d.id, d.tipo_alvo, d.motivo, d.criada_em,
               COALESCE(p.texto, c.texto, '') AS texto,
               COALESCE(alvo_perfil.pseudonimo, 'Participante') AS pseudonimo
        FROM denuncias d
        LEFT JOIN publicacoes p ON p.id=d.publicacao_id
        LEFT JOIN comentarios c ON c.id=d.comentario_id
        LEFT JOIN perfis alvo_perfil ON alvo_perfil.usuario_id=COALESCE(p.usuario_id, c.usuario_id)
        WHERE d.estado='aberta' ORDER BY d.criada_em, d.id
        """
    ).fetchall()
    return render_template(
        "comunidade_moderacao.html",
        publicacoes=publicacoes,
        comentarios=comentarios,
        denuncias=denuncias,
        categorias=COMMUNITY_CATEGORIES,
        motivos_denuncia=COMMUNITY_REPORT_REASONS,
    )


@app.route("/apoio-emocional/comunidade/moderacao/<tipo_alvo>/<int:id>", methods=["POST"])
def comunidade_moderar_conteudo(tipo_alvo, id):
    validar_csrf()
    exigir_moderadora()
    acao = request.form.get("acao", "")
    if tipo_alvo == "publicacao":
        table = "publicacoes"
        accepted = "aprovada"
        removed = "removida"
    elif tipo_alvo == "comentario":
        table = "comentarios"
        accepted = "aprovado"
        removed = "removido"
    else:
        abort(404)
    if acao not in ("aprovar", "remover"):
        abort(400, description="Ação de moderação inválida.")
    conn = community_db()
    if acao == "aprovar":
        cursor = conn.execute(
            f"UPDATE {table} SET estado=? WHERE id=? AND estado='pendente'", (accepted, id)
        )
    else:
        cursor = conn.execute(
            f"UPDATE {table} SET estado=?, texto='' WHERE id=? AND estado IN ('pendente', ?)",
            (removed, id, accepted),
        )
    if not cursor.rowcount:
        conn.rollback()
        abort(404)
    if tipo_alvo == "publicacao" and acao == "remover":
        conn.execute(
            "UPDATE comentarios SET estado='removido', texto='' WHERE publicacao_id=?", (id,)
        )
        conn.execute("DELETE FROM reacoes WHERE publicacao_id=?", (id,))
    conn.execute(
        "INSERT INTO auditoria_moderacao (moderadora_id, tipo_alvo, alvo_id, acao, criada_em) "
        "VALUES (?,?,?,?,?)",
        (uid(), tipo_alvo, id, acao, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return redirect(url_for("comunidade_moderacao"))


@app.route("/apoio-emocional/comunidade/moderacao/denuncias/<int:id>", methods=["POST"])
def comunidade_revisar_denuncia(id):
    validar_csrf()
    exigir_moderadora()
    acao = request.form.get("acao", "")
    if acao not in ("manter", "remover"):
        abort(400, description="Ação de moderação inválida.")
    conn = community_db()
    denuncia = conn.execute(
        "SELECT tipo_alvo, publicacao_id, comentario_id FROM denuncias WHERE id=? AND estado='aberta'",
        (id,),
    ).fetchone()
    if denuncia is None:
        abort(404)
    alvo_id = denuncia["publicacao_id"] or denuncia["comentario_id"]
    if acao == "remover":
        if denuncia["tipo_alvo"] == "publicacao":
            conn.execute("UPDATE publicacoes SET estado='removida', texto='' WHERE id=?", (alvo_id,))
            conn.execute(
                "UPDATE comentarios SET estado='removido', texto='' WHERE publicacao_id=?", (alvo_id,)
            )
            conn.execute("DELETE FROM reacoes WHERE publicacao_id=?", (alvo_id,))
        else:
            conn.execute("UPDATE comentarios SET estado='removido', texto='' WHERE id=?", (alvo_id,))
    conn.execute("UPDATE denuncias SET estado='revisada' WHERE id=?", (id,))
    conn.execute(
        "INSERT INTO auditoria_moderacao (moderadora_id, tipo_alvo, alvo_id, acao, criada_em) "
        "VALUES (?,?,?,?,?)",
        (uid(), denuncia["tipo_alvo"], alvo_id, f"denuncia_{acao}", datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return redirect(url_for("comunidade_moderacao"))


@app.route("/apoio-emocional/diario")
def buscar_registros_diario():
    mes = request.args.get("mes", "")
    try:
        primeiro_dia = date.fromisoformat(f"{mes}-01")
    except ValueError:
        abort(400, description="Mês inválido.")
    if primeiro_dia.strftime("%Y-%m") != mes:
        abort(400, description="Mês inválido.")
    if primeiro_dia > date.today().replace(day=1):
        abort(400, description="Não há registros em meses futuros.")
    if primeiro_dia.month == 12:
        proximo_mes = date(primeiro_dia.year + 1, 1, 1)
    else:
        proximo_mes = date(primeiro_dia.year, primeiro_dia.month + 1, 1)
    query = request.args.get("q", "").strip()[:80]
    if query:
        registros = db().execute(
            "SELECT id, data, nivel, nota FROM humor WHERE usuario_id=? "
            "AND instr(casefold(COALESCE(nota,'')), casefold(?)) > 0 ORDER BY data DESC, id DESC LIMIT 100",
            (uid(), query),
        ).fetchall()
    else:
        registros = db().execute(
            "SELECT id, data, nivel, nota FROM humor WHERE usuario_id=? AND data>=? AND data<? "
            "ORDER BY data DESC, id DESC",
            (uid(), primeiro_dia.isoformat(), proximo_mes.isoformat()),
        ).fetchall()
    return jsonify({
        "mes": mes,
        "registros": [
            {"id": row["id"], "data": row["data"], "nivel": row["nivel"], "nota": row["nota"] or ""}
            for row in registros
        ],
        "busca": bool(query),
        "limite": 100 if query else None,
    })


def contexto_apoio():
    _, etapas = linha_do_tempo()
    atual = etapa_atual(etapas)
    texto, fts = C.EMOCIONAL.get(atual["nome"], ("", [])) if atual else ("", [])
    # Text-only diary entries have no rating and must not affect this optional check-in.
    humores_recentes = db().execute("SELECT nivel FROM humor WHERE usuario_id=? AND nivel IS NOT NULL "
                                    "ORDER BY data DESC, id DESC LIMIT 3", (uid(),)).fetchall()
    alerta_humor = len(humores_recentes) == 3 and all(r["nivel"] <= 2 for r in humores_recentes)
    return {"atual": atual, "texto": texto, "fontes_texto": C.fontes(fts),
            "parceria": C.EMOCIONAL_PARCERIA[0], "fontes_parceria": C.fontes(C.EMOCIONAL_PARCERIA[1]),
            "humores": C.HUMORES, "alerta_humor": alerta_humor}


@app.route("/apoio-emocional/registros/<int:id>/excluir", methods=["POST"])
def excluir_registro_apoio(id):
    validar_csrf()
    registro = db().execute("SELECT data FROM humor WHERE id=? AND usuario_id=?", (id, uid())).fetchone()
    if registro is None:
        abort(404)
    db().execute("DELETE FROM humor WHERE id=? AND usuario_id=?", (id, uid()))
    db().commit()
    return redirect(url_for("apoio", diario="1", data=registro["data"]))


@app.route("/clinicas")
def clinicas():
    pac = paciente()
    titulo, itens, fts = C.CAMINHOS[pac["caminho"]]
    return render_template("clinicas.html", pac=pac, idade=idade(pac), guia_titulo=titulo, guia=itens,
                           guia_fontes=C.fontes(fts),
                           equipe=db().execute("SELECT * FROM equipe WHERE usuario_id=? ORDER BY id", (uid(),)).fetchall())


@app.route("/equipe", methods=["POST"])
def adicionar_equipe():
    f = request.form
    db().execute("INSERT INTO equipe (usuario_id, nome, especialidade, telefone) VALUES (?,?,?,?)",
                 (uid(), f["nome"], f["especialidade"], f["telefone"]))
    db().commit()
    return redirect(url_for("clinicas"))


@app.route("/equipe/<int:id>/excluir", methods=["POST"])
def excluir_equipe(id):
    db().execute("DELETE FROM equipe WHERE id=? AND usuario_id=?", (id, uid()))
    db().commit()
    return redirect(url_for("clinicas"))


@app.route("/relatorio")
def relatorio():
    pac, etapas = linha_do_tempo()
    u = uid()
    exames = db().execute("SELECT * FROM exames WHERE usuario_id=?", (u,)).fetchall()
    return render_template("relatorio.html", pac=pac, idade=idade(pac), atual=etapa_atual(etapas), etapas=etapas,
                           meds=db().execute("SELECT * FROM medicamentos WHERE usuario_id=?", (u,)).fetchall(),
                           doses=doses_resumo(),
                           sintomas=db().execute("SELECT * FROM sintomas WHERE usuario_id=? ORDER BY data DESC",
                                                 (u,)).fetchall(),
                           exames=exames, exames_pend=[e for e in exames if e["status"] != "entregue"],
                           prox=db().execute("SELECT * FROM compromissos WHERE usuario_id=? AND data_hora >= ? "
                                             "ORDER BY data_hora LIMIT 5", (u, agora_str())).fetchall())


if __name__ == "__main__":
    iniciar_banco()
    app.run(debug=True)
