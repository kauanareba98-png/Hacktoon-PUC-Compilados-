"""
Nida — Gestão e orientação para pacientes em FIV
Protótipo para o IV CodeCraft (PUC Goiás).

Rodar:  py -m pip install flask   e depois   py app.py
Abrir:  http://127.0.0.1:5000
Conta de demonstração: juliana@demo.com / nida2026
Para voltar aos dados de exemplo, apague o arquivo nida.db e rode de novo.
"""
import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, g, session
from werkzeug.security import generate_password_hash, check_password_hash

import conteudo as C

app = Flask(__name__)
# Em produção a chave viria de uma variável de ambiente; aqui há um valor padrão para o protótipo.
app.secret_key = os.environ.get("NIDA_SECRET", "nida-prototipo-troque-em-producao")
DB = "nida.db"

DEMO_EMAIL, DEMO_SENHA = "juliana@demo.com", "nida2026"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


# ================================================================ banco
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def fechar_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


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
            "agora_str": agora_str(), "nome_usuaria": nome}


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
        db().execute("INSERT INTO humor (usuario_id, data, nivel, nota) VALUES (?,?,?,?)",
                     (uid(), request.form.get("data") or date.today().isoformat(), int(request.form["nivel"]),
                      request.form.get("nota", "")))
        db().commit()
        return redirect(url_for("apoio"))
    _, etapas = linha_do_tempo()
    atual = etapa_atual(etapas)
    texto, fts = C.EMOCIONAL.get(atual["nome"], ("", [])) if atual else ("", [])
    registros = db().execute("SELECT * FROM humor WHERE usuario_id=? ORDER BY data DESC, id DESC LIMIT 14",
                             (uid(),)).fetchall()
    # Sinal de cuidado: os três últimos registros com humor difícil ou muito difícil.
    alerta_humor = len(registros) >= 3 and all(r["nivel"] <= 2 for r in registros[:3])
    # Remédios ativos hoje, para a paciente relacionar o humor com a medicação.
    hoje = date.today().isoformat()
    meds_hoje = db().execute("SELECT nome, classe FROM medicamentos WHERE usuario_id=? AND data_inicio<=? AND data_fim>=?",
                             (uid(), hoje, hoje)).fetchall()
    return render_template("apoio.html", atual=atual, texto=texto, fontes_texto=C.fontes(fts),
                           parceria=C.EMOCIONAL_PARCERIA[0], fontes_parceria=C.fontes(C.EMOCIONAL_PARCERIA[1]),
                           registros=registros, humores=C.HUMORES, alerta_humor=alerta_humor, meds_hoje=meds_hoje)


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
