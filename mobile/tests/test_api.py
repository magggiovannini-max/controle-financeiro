"""Testes da API com a IA simulada (não gasta créditos nem precisa de chave)."""
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'teste.db'}"
    os.environ["APP_SENHA"] = "segredo"
    for mod in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
        del sys.modules[mod]
    from fastapi.testclient import TestClient
    from app import ia, main

    chamadas = {}

    def falso_interpretar(texto, nomes, exemplos, hoje):
        chamadas["exemplos"] = exemplos
        assert "Alimentação" in nomes
        return {"itens": [
            {"valor": 45.9, "descricao": "iFood", "categoria": "Alimentação",
             "data": hoje.isoformat(), "forma_pagamento": "credito"},
            {"valor": 25, "descricao": "Uber", "categoria": "Transporte",
             "data": "2026-11-20", "forma_pagamento": "nao_informado"},
        ], "observacao": ""}

    monkeypatch.setattr(ia, "interpretar", falso_interpretar)
    monkeypatch.setattr(ia, "transcrever", lambda *a: "gastei quarenta e cinco e noventa no ifood e 25 de uber")
    with TestClient(main.app) as c:
        c.chamadas = chamadas
        yield c


def _login(c):
    token = c.post("/api/login", json={"senha": "segredo"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_exige_login(cliente):
    assert cliente.get("/api/categorias").status_code == 401
    assert cliente.post("/api/login", json={"senha": "errada"}).status_code == 401


def test_fluxo_audio_confirmar_e_aprender(cliente):
    h = _login(cliente)
    cats = {c["nome"]: c["id"] for c in cliente.get("/api/categorias", headers=h).json()}

    r = cliente.post("/api/interpretar/audio", headers=h,
                     files={"audio": ("gasto.m4a", b"x" * 2000, "audio/mp4")})
    assert r.status_code == 200, r.text
    dados = r.json()
    assert dados["transcricao"].startswith("gastei")
    assert [i["categoria_id"] for i in dados["itens"]] == [cats["Alimentação"], cats["Transporte"]]
    assert dados["itens"][1]["forma_pagamento"] is None

    # Usuário corrige o iFood para "Lazer" e salva
    itens = dados["itens"]
    itens[0]["categoria_id"] = cats["Lazer"]
    r = cliente.post("/api/gastos", headers=h, json={"itens": itens, "origem": "audio",
                                                     "transcricao": dados["transcricao"]})
    assert r.status_code == 200 and len(r.json()) == 2

    # Na próxima vez, a memória vence o palpite da IA
    r = cliente.post("/api/interpretar/texto", headers=h, json={"texto": "ifood 30"})
    item = r.json()["itens"][0]
    assert item["categoria_id"] == cats["Lazer"] and item["categoria_aprendida"]
    assert ("ifood", "Lazer") in cliente.chamadas["exemplos"]


def test_listagem_resumo_edicao(cliente):
    h = _login(cliente)
    cats = {c["nome"]: c["id"] for c in cliente.get("/api/categorias", headers=h).json()}
    cliente.post("/api/gastos", headers=h, json={"itens": [
        {"valor": 100, "descricao": "Mercado Extra", "categoria_id": cats["Mercado"], "data": "2026-11-05"},
        {"valor": 50, "descricao": "Cinema", "categoria_id": cats["Lazer"], "data": "2026-11-06"},
        {"valor": 80, "descricao": "Mercado", "categoria_id": cats["Mercado"], "data": "2026-10-10"},
    ]})
    gastos = cliente.get("/api/gastos?mes=2026-11", headers=h).json()
    assert [g["descricao"] for g in gastos] == ["Cinema", "Mercado Extra"]

    res = cliente.get("/api/resumo?mes=2026-11", headers=h).json()
    assert res["total"] == 150 and res["total_mes_anterior"] == 80
    assert res["categorias"][0]["nome"] == "Mercado"

    g = gastos[0]
    r = cliente.put(f"/api/gastos/{g['id']}", headers=h, json={**g, "valor": 55.5})
    assert r.json()["valor"] == 55.5
    assert cliente.delete(f"/api/gastos/{g['id']}", headers=h).status_code == 200
    assert len(cliente.get("/api/gastos?mes=2026-11", headers=h).json()) == 1


def test_categorias_crud(cliente):
    h = _login(cliente)
    nova = cliente.post("/api/categorias", headers=h,
                        json={"nome": "Pets", "emoji": "🐶", "cor": "#00ff00", "orcamento": 300}).json()
    assert nova["orcamento"] == 300
    cliente.put(f"/api/categorias/{nova['id']}", headers=h,
                json={"nome": "Pet", "emoji": "🐱", "cor": "#00ff00"})
    nomes = [c["nome"] for c in cliente.get("/api/categorias", headers=h).json()]
    assert "Pet" in nomes
    cliente.delete(f"/api/categorias/{nova['id']}", headers=h)
    assert "Pet" not in [c["nome"] for c in cliente.get("/api/categorias", headers=h).json()]


def test_normalizar_descricao():
    from app.ia import normalizar_descricao
    assert normalizar_descricao("  iFood - Almoço 2 ") == "ifood almoco"


def test_paginas_estaticas(cliente):
    assert "Quinza" in cliente.get("/").text
    assert cliente.get("/manifest.webmanifest").status_code == 200
    assert cliente.get("/sw.js").status_code == 200
