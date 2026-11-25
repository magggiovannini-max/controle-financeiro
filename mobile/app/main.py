"""API do Quinza Mobile + arquivos do app web (PWA)."""
import hashlib
import hmac
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config, ia
from app.db import Categoria, Gasto, RegraAprendida, inicializar_banco, obter_sessao

PASTA_STATIC = Path(__file__).resolve().parent.parent / "static"
TAMANHO_MAX_AUDIO = 15 * 1024 * 1024  # 15 MB

@asynccontextmanager
async def _ciclo_de_vida(_app):
    inicializar_banco()
    yield


app = FastAPI(title="Quinza Mobile", lifespan=_ciclo_de_vida)


def hoje() -> date:
    return datetime.now(ZoneInfo(config.FUSO_HORARIO)).date()


# ---------------------------------------------------------------- autenticação
def _token_valido() -> str:
    return hmac.new(config.SECRET_KEY.encode(), config.APP_SENHA.encode(),
                    hashlib.sha256).hexdigest()


def exigir_login(authorization: str = Header(default="")):
    if not config.APP_SENHA:
        return  # sem senha configurada (uso local)
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, _token_valido()):
        raise HTTPException(401, "Faça login novamente.")


class LoginIn(BaseModel):
    senha: str


@app.post("/api/login")
def login(dados: LoginIn):
    if not config.APP_SENHA:
        return {"token": ""}
    if not hmac.compare_digest(dados.senha, config.APP_SENHA):
        raise HTTPException(401, "Senha incorreta.")
    return {"token": _token_valido()}


api = Depends(exigir_login)


# ------------------------------------------------------------------ categorias
class CategoriaIn(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    emoji: str = "📦"
    cor: str = "#5C6BC0"
    orcamento: float | None = None


def _cat_dict(c: Categoria) -> dict:
    return {"id": c.id, "nome": c.nome, "emoji": c.emoji, "cor": c.cor,
            "orcamento": c.orcamento}


def _categorias_ativas(s: Session) -> list[Categoria]:
    return list(s.scalars(select(Categoria).where(Categoria.ativa)
                          .order_by(Categoria.ordem, Categoria.id)))


@app.get("/api/categorias", dependencies=[api])
def listar_categorias(s: Session = Depends(obter_sessao)):
    return [_cat_dict(c) for c in _categorias_ativas(s)]


@app.post("/api/categorias", dependencies=[api])
def criar_categoria(dados: CategoriaIn, s: Session = Depends(obter_sessao)):
    ordem = (s.scalar(select(func.max(Categoria.ordem))) or 0) + 1
    c = Categoria(**dados.model_dump(), ordem=ordem)
    s.add(c)
    s.commit()
    return _cat_dict(c)


@app.put("/api/categorias/{cat_id}", dependencies=[api])
def atualizar_categoria(cat_id: int, dados: CategoriaIn, s: Session = Depends(obter_sessao)):
    c = s.get(Categoria, cat_id)
    if not c or not c.ativa:
        raise HTTPException(404, "Categoria não encontrada.")
    for k, v in dados.model_dump().items():
        setattr(c, k, v)
    s.commit()
    return _cat_dict(c)


@app.delete("/api/categorias/{cat_id}", dependencies=[api])
def remover_categoria(cat_id: int, s: Session = Depends(obter_sessao)):
    """Desativa a categoria (os gastos antigos continuam no histórico)."""
    c = s.get(Categoria, cat_id)
    if not c:
        raise HTTPException(404, "Categoria não encontrada.")
    if len(_categorias_ativas(s)) <= 1:
        raise HTTPException(400, "Mantenha pelo menos uma categoria.")
    c.ativa = False
    s.query(RegraAprendida).filter(RegraAprendida.categoria_id == cat_id).delete()
    s.commit()
    return {"ok": True}


# --------------------------------------------------------------- interpretação
def _exemplos(s: Session, limite: int = 60) -> list[tuple[str, str]]:
    linhas = s.execute(
        select(RegraAprendida.chave, Categoria.nome)
        .join(Categoria, Categoria.id == RegraAprendida.categoria_id)
        .where(Categoria.ativa)
        .order_by(RegraAprendida.usos.desc(), RegraAprendida.atualizado_em.desc())
        .limit(limite)
    )
    return [(chave, nome) for chave, nome in linhas]


def _montar_propostas(s: Session, texto: str) -> dict:
    cats = _categorias_ativas(s)
    por_nome = {c.nome: c for c in cats}
    resultado = ia.interpretar(texto, list(por_nome), _exemplos(s), hoje())

    itens = []
    for item in resultado["itens"]:
        cat = por_nome.get(item["categoria"]) or por_nome.get("Outros") or cats[0]
        # A memória do app tem prioridade sobre o palpite da IA.
        regra = s.scalar(select(RegraAprendida).where(
            RegraAprendida.chave == ia.normalizar_descricao(item["descricao"])))
        aprendida = False
        if regra:
            cat_regra = s.get(Categoria, regra.categoria_id)
            if cat_regra and cat_regra.ativa:
                cat, aprendida = cat_regra, True
        forma = item.get("forma_pagamento")
        itens.append({
            "valor": item["valor"],
            "descricao": item["descricao"],
            "categoria_id": cat.id,
            "data": item["data"],
            "forma_pagamento": None if forma in (None, "nao_informado") else forma,
            "categoria_aprendida": aprendida,
        })
    return {"transcricao": texto, "itens": itens, "observacao": resultado["observacao"]}


class TextoIn(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)


@app.post("/api/interpretar/texto", dependencies=[api])
def interpretar_texto(dados: TextoIn, s: Session = Depends(obter_sessao)):
    try:
        return _montar_propostas(s, dados.texto.strip())
    except ia.ErroIA as e:
        raise HTTPException(502, str(e)) from e


@app.post("/api/interpretar/audio", dependencies=[api])
async def interpretar_audio(audio: UploadFile = File(...), s: Session = Depends(obter_sessao)):
    conteudo = await audio.read()
    if not conteudo:
        raise HTTPException(400, "Áudio vazio.")
    if len(conteudo) > TAMANHO_MAX_AUDIO:
        raise HTTPException(413, "Áudio muito longo.")
    try:
        texto = ia.transcrever(conteudo, audio.filename or "audio.m4a",
                               audio.content_type or "audio/mp4")
        return _montar_propostas(s, texto)
    except ia.ErroIA as e:
        raise HTTPException(502, str(e)) from e


# ---------------------------------------------------------------------- gastos
class GastoIn(BaseModel):
    valor: float = Field(gt=0)
    descricao: str = Field(min_length=1, max_length=120)
    categoria_id: int
    data: date
    forma_pagamento: str | None = None


class SalvarGastosIn(BaseModel):
    itens: list[GastoIn] = Field(min_length=1)
    origem: str = "manual"
    transcricao: str | None = None


def _gasto_dict(g: Gasto) -> dict:
    return {"id": g.id, "valor": g.valor, "descricao": g.descricao,
            "categoria_id": g.categoria_id, "data": g.data.isoformat(),
            "forma_pagamento": g.forma_pagamento, "origem": g.origem}


def _validar_categoria(s: Session, cat_id: int):
    c = s.get(Categoria, cat_id)
    if not c or not c.ativa:
        raise HTTPException(400, "Categoria inválida.")


def _aprender(s: Session, descricao: str, categoria_id: int):
    chave = ia.normalizar_descricao(descricao)
    if not chave:
        return
    regra = s.scalar(select(RegraAprendida).where(RegraAprendida.chave == chave))
    if regra:
        if regra.categoria_id == categoria_id:
            regra.usos += 1
        else:
            regra.categoria_id, regra.usos = categoria_id, 1
    else:
        s.add(RegraAprendida(chave=chave, categoria_id=categoria_id))
    s.flush()


@app.post("/api/gastos", dependencies=[api])
def salvar_gastos(dados: SalvarGastosIn, s: Session = Depends(obter_sessao)):
    origem = dados.origem if dados.origem in ("audio", "texto", "manual") else "manual"
    criados = []
    for item in dados.itens:
        _validar_categoria(s, item.categoria_id)
        g = Gasto(**item.model_dump(), origem=origem, transcricao=dados.transcricao)
        s.add(g)
        _aprender(s, item.descricao, item.categoria_id)
        criados.append(g)
    s.commit()
    return [_gasto_dict(g) for g in criados]


@app.put("/api/gastos/{gasto_id}", dependencies=[api])
def atualizar_gasto(gasto_id: int, dados: GastoIn, s: Session = Depends(obter_sessao)):
    g = s.get(Gasto, gasto_id)
    if not g:
        raise HTTPException(404, "Gasto não encontrado.")
    _validar_categoria(s, dados.categoria_id)
    for k, v in dados.model_dump().items():
        setattr(g, k, v)
    _aprender(s, dados.descricao, dados.categoria_id)
    s.commit()
    return _gasto_dict(g)


@app.delete("/api/gastos/{gasto_id}", dependencies=[api])
def remover_gasto(gasto_id: int, s: Session = Depends(obter_sessao)):
    g = s.get(Gasto, gasto_id)
    if not g:
        raise HTTPException(404, "Gasto não encontrado.")
    s.delete(g)
    s.commit()
    return {"ok": True}


def _intervalo_mes(mes: str) -> tuple[date, date]:
    try:
        inicio = datetime.strptime(mes, "%Y-%m").date()
    except ValueError as e:
        raise HTTPException(400, "Use o formato AAAA-MM.") from e
    fim = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
    return inicio, fim


@app.get("/api/gastos", dependencies=[api])
def listar_gastos(mes: str, s: Session = Depends(obter_sessao)):
    inicio, fim = _intervalo_mes(mes)
    gastos = s.scalars(select(Gasto).where(Gasto.data >= inicio, Gasto.data < fim)
                       .order_by(Gasto.data.desc(), Gasto.id.desc()))
    return [_gasto_dict(g) for g in gastos]


def _totais_por_categoria(s: Session, inicio: date, fim: date) -> dict[int, float]:
    linhas = s.execute(select(Gasto.categoria_id, func.sum(Gasto.valor))
                       .where(Gasto.data >= inicio, Gasto.data < fim)
                       .group_by(Gasto.categoria_id))
    return {cid: round(total or 0, 2) for cid, total in linhas}


@app.get("/api/resumo", dependencies=[api])
def resumo(mes: str, s: Session = Depends(obter_sessao)):
    inicio, fim = _intervalo_mes(mes)
    inicio_ant = (inicio - timedelta(days=1)).replace(day=1)
    atual = _totais_por_categoria(s, inicio, fim)
    anterior = _totais_por_categoria(s, inicio_ant, inicio)

    cats = {c.id: c for c in s.scalars(select(Categoria))}
    ativas = {c.id for c in _categorias_ativas(s)}
    linhas = []
    for cid in sorted(set(atual) | ativas, key=lambda i: (cats[i].ordem, i)):
        c = cats[cid]
        total = atual.get(cid, 0.0)
        if not total and cid not in ativas:
            continue
        linhas.append({**_cat_dict(c), "total": total,
                       "total_mes_anterior": anterior.get(cid, 0.0)})
    linhas.sort(key=lambda l: -l["total"])
    return {
        "mes": mes,
        "total": round(sum(atual.values()), 2),
        "total_mes_anterior": round(sum(anterior.values()), 2),
        "categorias": linhas,
    }


# ------------------------------------------------------------------ app web
app.mount("/static", StaticFiles(directory=PASTA_STATIC), name="static")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(PASTA_STATIC / "sw.js", media_type="application/javascript")


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(PASTA_STATIC / "manifest.webmanifest",
                        media_type="application/manifest+json")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(PASTA_STATIC / "index.html")
