"""Transcrição de áudio (Whisper) e interpretação/classificação (Claude)."""
import json
import re
import unicodedata
from datetime import date

import anthropic
import httpx

from app import config

FORMAS_PAGAMENTO = ["pix", "debito", "credito", "dinheiro", "caju", "nao_informado"]
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]

# Modelos que aceitam o parâmetro server-side `fallbacks`.
_MODELOS_COM_FALLBACK = {
    "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5",
    "claude-fable-5-1", "claude-fable-5-2",
}


class ErroIA(Exception):
    """Falha de transcrição ou interpretação, com mensagem amigável."""


def normalizar_descricao(texto: str) -> str:
    """'iFood  - Almoço 2' -> 'ifood almoco'. Usado como chave da memória."""
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-zA-Z ]+", " ", texto.lower())
    return re.sub(r"\s+", " ", texto).strip()


# ---------------------------------------------------------------- transcrição
def transcrever(conteudo: bytes, nome_arquivo: str, content_type: str) -> str:
    if not config.TRANSCRICAO_API_KEY:
        raise ErroIA("Transcrição não configurada (falta TRANSCRICAO_API_KEY).")
    try:
        resp = httpx.post(
            f"{config.TRANSCRICAO_BASE_URL.rstrip('/')}/audio/transcriptions",
            headers={"Authorization": f"Bearer {config.TRANSCRICAO_API_KEY}"},
            data={"model": config.TRANSCRICAO_MODELO, "language": "pt",
                  "response_format": "json"},
            files={"file": (nome_arquivo, conteudo, content_type)},
            timeout=60,
        )
    except httpx.HTTPError as e:
        raise ErroIA(f"Não consegui falar com o serviço de transcrição: {e}") from e
    if resp.status_code != 200:
        raise ErroIA(f"Erro na transcrição ({resp.status_code}): {resp.text[:200]}")
    texto = (resp.json().get("text") or "").strip()
    if not texto:
        raise ErroIA("Não entendi o áudio. Tente falar de novo, mais perto do microfone.")
    return texto


# -------------------------------------------------------------- interpretação
_SYSTEM = """Você é o assistente de um app pessoal de controle de gastos no Brasil.
Você recebe a transcrição de um áudio (ou um texto digitado) em que a pessoa conta \
um ou mais gastos que fez, e devolve cada gasto estruturado.

Regras:
- Um item por gasto. "25 de uber e 32 no almoço" são dois itens.
- valor: número em reais. Converta valores falados ("quarenta e cinco e noventa" = 45.90, \
"dez conto" = 10, "um e cinquenta" = 1.50). Se não houver valor, não crie o item.
- descricao: curta e limpa, como apareceria num extrato (ex: "iFood", "Uber", \
"Almoço restaurante", "Farmácia"). Use o nome do estabelecimento quando citado.
- categoria: escolha exatamente uma das categorias disponíveis. Use "Outros" se nenhuma servir.
- data: AAAA-MM-DD. Use a data de hoje, a menos que a pessoa diga outra \
("ontem", "sexta", "dia 3").
- forma_pagamento: pix, debito, credito, dinheiro ou caju (vale-refeição/alimentação Caju). \
Use nao_informado se a pessoa não disse.
- Os exemplos de classificações anteriores mostram as preferências da pessoa: siga-os.
- observacao: frase curta só se algo ficou ambíguo; senão, string vazia."""


def _schema(nomes_categorias: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "itens": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "valor": {"type": "number"},
                        "descricao": {"type": "string"},
                        "categoria": {"type": "string", "enum": nomes_categorias},
                        "data": {"type": "string"},
                        "forma_pagamento": {"type": "string", "enum": FORMAS_PAGAMENTO},
                    },
                    "required": ["valor", "descricao", "categoria", "data", "forma_pagamento"],
                    "additionalProperties": False,
                },
            },
            "observacao": {"type": "string"},
        },
        "required": ["itens", "observacao"],
        "additionalProperties": False,
    }


_cliente: anthropic.Anthropic | None = None


def _obter_cliente() -> anthropic.Anthropic:
    global _cliente
    if _cliente is None:
        _cliente = anthropic.Anthropic()
    return _cliente


def interpretar(texto: str, nomes_categorias: list[str], exemplos: list[tuple[str, str]],
                hoje: date) -> dict:
    """Retorna {"itens": [...], "observacao": str} a partir de texto livre."""
    exemplos_txt = "\n".join(f"- {d} → {c}" for d, c in exemplos) or "(nenhum ainda)"
    conteudo = (
        f"Hoje é {DIAS_SEMANA[hoje.weekday()]}, {hoje.isoformat()}.\n\n"
        f"Categorias disponíveis: {', '.join(nomes_categorias)}\n\n"
        f"Classificações anteriores da pessoa:\n{exemplos_txt}\n\n"
        f"<mensagem>\n{texto}\n</mensagem>"
    )
    params = dict(
        model=config.CLAUDE_MODEL,
        max_tokens=4000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": conteudo}],
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": _schema(nomes_categorias)},
        },
    )
    if config.CLAUDE_MODEL in _MODELOS_COM_FALLBACK:
        params.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")

    try:
        resp = _obter_cliente().beta.messages.create(**params)
    except anthropic.AuthenticationError as e:
        raise ErroIA("Chave da API do Claude inválida (ANTHROPIC_API_KEY).") from e
    except anthropic.RateLimitError as e:
        raise ErroIA("Muitas requisições ao Claude. Tente de novo em instantes.") from e
    except anthropic.APIStatusError as e:
        raise ErroIA(f"Erro do Claude ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise ErroIA("Sem conexão com o Claude.") from e

    if resp.stop_reason == "refusal":
        raise ErroIA("O Claude não conseguiu processar essa mensagem.")
    if resp.stop_reason == "max_tokens":
        raise ErroIA("Mensagem longa demais; tente dividir em partes.")
    bloco = next((b.text for b in resp.content if b.type == "text"), None)
    if not bloco:
        raise ErroIA("Resposta vazia do Claude.")
    try:
        dados = json.loads(bloco)
    except json.JSONDecodeError as e:
        raise ErroIA("Resposta inválida do Claude.") from e

    # Sanitiza: valor positivo, data válida.
    itens = []
    for item in dados.get("itens", []):
        try:
            valor = round(abs(float(item["valor"])), 2)
        except (KeyError, TypeError, ValueError):
            continue
        if not valor:
            continue
        try:
            data_item = date.fromisoformat(item.get("data", ""))
        except (TypeError, ValueError):
            data_item = hoje
        itens.append({**item, "valor": valor, "data": data_item.isoformat()})
    return {"itens": itens, "observacao": dados.get("observacao", "")}
