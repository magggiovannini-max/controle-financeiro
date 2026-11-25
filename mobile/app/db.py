"""Modelos e conexão com o banco (SQLite local ou Postgres na nuvem)."""
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text,
    create_engine, func, select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app import config

_connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(60))
    emoji: Mapped[str] = mapped_column(String(16), default="📦")
    cor: Mapped[str] = mapped_column(String(9), default="#5C6BC0")
    orcamento: Mapped[float | None] = mapped_column(Float, nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class Gasto(Base):
    __tablename__ = "gastos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    valor: Mapped[float] = mapped_column(Float)
    descricao: Mapped[str] = mapped_column(String(120))
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"))
    data: Mapped[date] = mapped_column(Date, index=True)
    forma_pagamento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    origem: Mapped[str] = mapped_column(String(10), default="manual")  # audio|texto|manual
    transcricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RegraAprendida(Base):
    """Memória de classificação: descrição normalizada -> categoria.

    Toda vez que você confirma um gasto, o app lembra a categoria escolhida
    para aquela descrição. Na próxima vez, ela é aplicada automaticamente.
    """
    __tablename__ = "regras_aprendidas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chave: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"))
    usos: Mapped[int] = mapped_column(Integer, default=1)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


CATEGORIAS_PADRAO = [
    ("Alimentação", "🍔", "#FF7043"),
    ("Mercado", "🛒", "#66BB6A"),
    ("Transporte", "🚗", "#42A5F5"),
    ("Casa e contas", "🏠", "#5C6BC0"),
    ("Saúde", "💊", "#26A69A"),
    ("Lazer", "🎉", "#AB47BC"),
    ("Compras", "🛍️", "#EC407A"),
    ("Assinaturas", "📺", "#FFA726"),
    ("Educação", "📚", "#8D6E63"),
    ("Outros", "📦", "#78909C"),
]


def inicializar_banco():
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if s.scalar(select(func.count()).select_from(Categoria)) == 0:
            for i, (nome, emoji, cor) in enumerate(CATEGORIAS_PADRAO):
                s.add(Categoria(nome=nome, emoji=emoji, cor=cor, ordem=i))
            s.commit()


def obter_sessao():
    with SessionLocal() as s:
        yield s


__all__ = [
    "Base", "Categoria", "Gasto", "RegraAprendida", "Session", "engine",
    "SessionLocal", "inicializar_banco", "obter_sessao",
]
