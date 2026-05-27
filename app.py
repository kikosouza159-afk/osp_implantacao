from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from flask import (
    Flask, Response, flash, redirect, render_template, request,
    send_file, session, url_for
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

# ============================================================
# BANCO DE DADOS
# ============================================================
# Em produção no Render, use obrigatoriamente DATABASE_URL apontando para
# PostgreSQL. Se DATABASE_URL não existir no Render, o app NÃO deve cair em
# SQLite, porque SQLite no Render é efêmero e perde os dados a cada deploy.
database_url = os.getenv("DATABASE_URL")

if not database_url:
    local_dev = os.getenv("LOCAL_DEV", "0").strip().lower() in {"1", "true", "sim", "yes"}
    if local_dev:
        database_url = "sqlite:///implantacao.db"
    else:
        raise RuntimeError(
            "DATABASE_URL não configurada. No Render, configure DATABASE_URL "
            "com a Internal Database URL do PostgreSQL para manter os dados após deploy."
        )

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Projeto(db.Model):
    __tablename__ = "projetos_implantacao"

    id = db.Column(db.Integer, primary_key=True)
    produto = db.Column(db.String(80), nullable=False, default="")
    projeto = db.Column(db.String(20), nullable=False, default="SIM")
    org = db.Column(db.Integer, nullable=True)
    cliente = db.Column(db.String(255), nullable=False, default="")
    carteira = db.Column(db.String(255), nullable=True, default="")
    etapa_atual = db.Column(db.String(120), nullable=True, default="")
    inicio_poc = db.Column(db.Date, nullable=True)
    prazo_final_poc = db.Column(db.Date, nullable=True)
    data_alvo_faturamento = db.Column(db.Date, nullable=True)
    situacao = db.Column(db.Text, nullable=True, default="")
    responsavel = db.Column(db.String(150), nullable=True, default="")
    proxima_acao = db.Column(db.Text, nullable=True, default="")
    risco = db.Column(db.String(50), nullable=True, default="")
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def grupo_etapa(self) -> str:
        etapa = (self.etapa_atual or "").upper()
        if "POC" in etapa:
            return "poc"
        if "IMPLANT" in etapa:
            return "implantando"
        if "HOMOLOG" in etapa:
            return "homologacao"
        return "outros"

    @property
    def produto_grupo(self) -> str:
        prod = (self.produto or "").upper()
        if "ADA" in prod:
            return "ada"
        return "locator"

    def to_dict(self):
        return {
            "id": self.id,
            "produto": self.produto,
            "projeto": self.projeto,
            "org": self.org,
            "cliente": self.cliente,
            "carteira": self.carteira,
            "etapa_atual": self.etapa_atual,
            "inicio_poc": format_date(self.inicio_poc),
            "prazo_final_poc": format_date(self.prazo_final_poc),
            "data_alvo_faturamento": format_date(self.data_alvo_faturamento),
            "situacao": self.situacao,
            "responsavel": self.responsavel,
            "proxima_acao": self.proxima_acao,
            "risco": self.risco,
            "grupo_etapa": self.grupo_etapa,
            "produto_grupo": self.produto_grupo,
        }


def init_db():
    with app.app_context():
        db.create_all()


@app.before_request
def ensure_db():
    db.create_all()


def is_logged():
    return session.get("logged_in") is True


def admin_required():
    if not is_logged():
        return redirect(url_for("login"))
    return None


def parse_date(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value or value.lower() in {"nan", "nat", "none", "(vazio)"}:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def format_date(value):
    if not value:
        return "(vazio)"
    return value.strftime("%d/%m/%Y")


def safe_int(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(str(value).replace(",", ".")))
    except Exception:
        return None


def normalize_columns(df):
    mapping = {
        "PRODUTO": "produto",
        "PROJETO": "projeto",
        "ORG": "org",
        "CLIENTE": "cliente",
        "CARTEIRA": "carteira",
        "ETAPA ATUAL": "etapa_atual",
        "ETAPA": "etapa_atual",
        "INICIO DE POC": "inicio_poc",
        "INÍCIO DE POC": "inicio_poc",
        "PRAZO FINAL POC": "prazo_final_poc",
        "DATA ALVO [FATURAMENTO]": "data_alvo_faturamento",
        "DATA ALVO (FATURAMENTO)": "data_alvo_faturamento",
        "SITUAÇÃO": "situacao",
        "SITUACAO": "situacao",
    }

    def clean(col):
        c = str(col).strip().upper()
        c = c.replace("Á", "A").replace("À", "A").replace("Ã", "A").replace("Â", "A")
        c = c.replace("É", "E").replace("Ê", "E").replace("Í", "I").replace("Ó", "O")
        c = c.replace("Ô", "O").replace("Õ", "O").replace("Ú", "U").replace("Ç", "C")
        return c

    renamed = {}
    for col in df.columns:
        key = clean(col)
        if key in mapping:
            renamed[col] = mapping[key]
    return df.rename(columns=renamed)


def build_context():
    projetos = Projeto.query.order_by(Projeto.produto, Projeto.org, Projeto.cliente).all()

    locator = [p for p in projetos if p.produto_grupo == "locator"]
    ada = [p for p in projetos if p.produto_grupo == "ada"]

    poc = [p for p in projetos if p.grupo_etapa == "poc"]
    implantando = [p for p in projetos if p.grupo_etapa == "implantando"]
    homologacao = [p for p in projetos if p.grupo_etapa == "homologacao"]
    outros = [p for p in projetos if p.grupo_etapa == "outros"]
    riscos = [p for p in projetos if (p.risco or "").strip() and (p.risco or "").upper() not in {"BAIXO", "SEM RISCO"}]

    return {
        "projetos": projetos,
        "locator": locator,
        "ada": ada,
        "riscos": riscos[:8],
        "indicators": {
            "total": len(projetos),
            "total_locator": len(locator),
            "total_ada": len(ada),
            "total_poc": len(poc),
            "poc_locator": len([p for p in poc if p.produto_grupo == "locator"]),
            "poc_ada": len([p for p in poc if p.produto_grupo == "ada"]),
            "total_implantando": len(implantando),
            "total_homologacao": len(homologacao),
            "total_outros": len(outros),
            "total_risco": len(riscos),
            "data_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("usuario", "").strip()
        password = request.form.get("senha", "").strip()
        admin_user = os.getenv("ADMIN_USER", "gerber")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

        if user.lower() == admin_user.lower() and password == admin_password:
            session["logged_in"] = True
            session["usuario"] = user.upper()
            session["perfil"] = "ADMIN"
            return redirect(url_for("home"))

        flash("Usuário ou senha inválido.", "erro")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def home():
    gate = admin_required()
    if gate:
        return gate
    return render_template("painel.html", **build_context(), usuario=session.get("usuario", "GERBER"), perfil=session.get("perfil", "ADMIN"))

@app.route("/db-status")
def db_status():
    gate = admin_required()
    if gate:
        return gate

    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    tipo = "PostgreSQL" if uri.startswith("postgresql://") else "SQLite/local"
    return {
        "tipo_banco": tipo,
        "total_projetos": Projeto.query.count(),
        "persistente_render": tipo == "PostgreSQL",
    }



@app.route("/projeto/novo", methods=["POST"])
def novo_projeto():
    gate = admin_required()
    if gate:
        return gate

    p = Projeto()
    fill_project_from_form(p, request.form)
    db.session.add(p)
    db.session.commit()
    flash("Projeto criado com sucesso.", "ok")
    return redirect(url_for("home"))


@app.route("/projeto/<int:project_id>/editar", methods=["POST"])
def editar_projeto(project_id):
    gate = admin_required()
    if gate:
        return gate

    p = Projeto.query.get_or_404(project_id)
    fill_project_from_form(p, request.form)
    db.session.commit()
    flash("Projeto atualizado com sucesso.", "ok")
    return redirect(url_for("home"))


@app.route("/projeto/<int:project_id>/excluir", methods=["POST"])
def excluir_projeto(project_id):
    gate = admin_required()
    if gate:
        return gate

    p = Projeto.query.get_or_404(project_id)
    db.session.delete(p)
    db.session.commit()
    flash("Projeto excluído com sucesso.", "ok")
    return redirect(url_for("home"))


def fill_project_from_form(p, form):
    p.produto = form.get("produto", "").strip()
    p.projeto = form.get("projeto", "SIM").strip() or "SIM"
    p.org = safe_int(form.get("org"))
    p.cliente = form.get("cliente", "").strip()
    p.carteira = form.get("carteira", "").strip()
    p.etapa_atual = form.get("etapa_atual", "").strip()
    p.inicio_poc = parse_date(form.get("inicio_poc"))
    p.prazo_final_poc = parse_date(form.get("prazo_final_poc"))
    p.data_alvo_faturamento = parse_date(form.get("data_alvo_faturamento"))
    p.situacao = form.get("situacao", "").strip()
    p.responsavel = form.get("responsavel", "").strip()
    p.proxima_acao = form.get("proxima_acao", "").strip()
    p.risco = form.get("risco", "").strip()


@app.route("/modelo")
def baixar_modelo():
    cols = [
        "PRODUTO", "PROJETO", "ORG", "CLIENTE", "CARTEIRA", "Etapa atual",
        "Inicio de POC", "Prazo Final POC", "Data Alvo [Faturamento]",
        "Situação", "Responsável", "Próxima Ação", "Risco"
    ]
    df = pd.DataFrame(columns=cols)
    output = BytesIO()
    df.to_excel(output, index=False, sheet_name="Projetos")
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="modelo_projetos_implantacao.xlsx")


@app.route("/exportar")
def exportar_csv():
    gate = admin_required()
    if gate:
        return gate

    rows = [p.to_dict() for p in Projeto.query.order_by(Projeto.id).all()]
    df = pd.DataFrame(rows)
    csv = df.to_csv(index=False, sep=";", encoding="utf-8-sig")
    filename = f"projetos_implantacao_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        csv,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route("/importar", methods=["POST"])
def importar():
    gate = admin_required()
    if gate:
        return gate

    file = request.files.get("arquivo")
    if not file or file.filename == "":
        flash("Selecione um arquivo Excel ou CSV.", "erro")
        return redirect(url_for("home"))

    filename = file.filename.lower()
    if filename.endswith(".csv"):
        try:
            df = pd.read_csv(file, sep=None, engine="python", encoding="utf-8-sig")
        except UnicodeDecodeError:
            file.seek(0)
            df = pd.read_csv(file, sep=None, engine="python", encoding="latin1")
    else:
        df = pd.read_excel(file, engine="openpyxl")

    df = normalize_columns(df)

    obrigatorias = {"produto", "cliente"}
    if not obrigatorias.issubset(set(df.columns)):
        flash("Arquivo inválido. Campos obrigatórios: PRODUTO e CLIENTE.", "erro")
        return redirect(url_for("home"))

    novos = 0
    atualizados = 0

    for _, row in df.iterrows():
        cliente = str(row.get("cliente", "")).strip()
        carteira = str(row.get("carteira", "")).strip()
        produto = str(row.get("produto", "")).strip()
        if not cliente:
            continue

        p = Projeto.query.filter_by(cliente=cliente, carteira=carteira, produto=produto).first()
        if not p:
            p = Projeto()
            db.session.add(p)
            novos += 1
        else:
            atualizados += 1

        p.produto = produto
        p.projeto = str(row.get("projeto", "SIM")).strip() or "SIM"
        p.org = safe_int(row.get("org"))
        p.cliente = cliente
        p.carteira = carteira
        p.etapa_atual = str(row.get("etapa_atual", "")).strip()
        p.inicio_poc = parse_date(row.get("inicio_poc"))
        p.prazo_final_poc = parse_date(row.get("prazo_final_poc"))
        p.data_alvo_faturamento = parse_date(row.get("data_alvo_faturamento"))
        p.situacao = str(row.get("situacao", "")).strip()
        p.responsavel = str(row.get("responsavel", "")).strip()
        p.proxima_acao = str(row.get("proxima_acao", "")).strip()
        p.risco = str(row.get("risco", "")).strip()

    db.session.commit()
    flash(f"Importação concluída. Novos: {novos} | Atualizados: {atualizados}", "ok")
    return redirect(url_for("home"))


@app.route("/seed")
def seed():
    gate = admin_required()
    if gate:
        return gate

    if Projeto.query.count() > 0:
        flash("Base já possui projetos.", "ok")
        return redirect(url_for("home"))

    exemplos = [
        ("1.LOCATOR", "SIM", 1, "TALENTOS", "Via Varejo Recovery", "OK Implantado"),
        ("1.LOCATOR", "SIM", 2, "FERREIRA E CHAGAS", "Ativos e Kroton", "POC"),
        ("2.ADA", "SIM", 1, "ENERGISA", "COBRANÇA", "POC"),
        ("2.ADA", "SIM", 3, "ATENTO", "VIVO", "Mapeamento"),
    ]
    for produto, projeto, org, cliente, carteira, etapa in exemplos:
        db.session.add(Projeto(produto=produto, projeto=projeto, org=org, cliente=cliente, carteira=carteira, etapa_atual=etapa))
    db.session.commit()
    flash("Dados exemplo criados.", "ok")
    return redirect(url_for("home"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG", "1") == "1")
