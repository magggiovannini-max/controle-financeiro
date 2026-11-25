"""Configurações lidas das variáveis de ambiente.

Localmente você pode criar um arquivo `.env` na pasta `mobile/` (veja `.env.exemplo`).
Na nuvem, configure as mesmas variáveis no painel do serviço de hospedagem.
"""
import os
from pathlib import Path


def _carregar_env_local():
    """Lê `mobile/.env` (se existir) sem precisar de biblioteca extra."""
    caminho = Path(__file__).resolve().parent.parent / ".env"
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


_carregar_env_local()

# Banco: SQLite local por padrão; na nuvem use Postgres (ex: Neon/Supabase).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quinza_mobile.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Senha de acesso ao app (você digita uma vez no iPhone).
APP_SENHA = os.getenv("APP_SENHA", "")
# Chave usada para assinar o token de login. Troque por algo aleatório.
SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave")

# Claude (interpretação/classificação). A chave vem de ANTHROPIC_API_KEY.
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

# Transcrição de áudio: qualquer API compatível com o endpoint
# /audio/transcriptions (Groq ou OpenAI).
TRANSCRICAO_API_KEY = os.getenv("TRANSCRICAO_API_KEY", "")
TRANSCRICAO_BASE_URL = os.getenv("TRANSCRICAO_BASE_URL", "https://api.groq.com/openai/v1")
TRANSCRICAO_MODELO = os.getenv("TRANSCRICAO_MODELO", "whisper-large-v3-turbo")

FUSO_HORARIO = os.getenv("FUSO_HORARIO", "America/Sao_Paulo")
