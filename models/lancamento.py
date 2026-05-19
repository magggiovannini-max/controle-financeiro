from database.connection import obter_conexao
from datetime import date


def criar_lancamento(
    periodo_id: int,
    categoria_id: int,
    descricao: str,
    valor: float,
    data_vencimento: str,
    origem_pagamento: int,
    status: str,
) -> int:
    conn = obter_conexao()
    cursor = conn.cursor()
    hoje = date.today().isoformat()
    data_pagamento = hoje if status == "pago" else None

    cursor.execute("""
        INSERT INTO lancamentos
            (periodo_id, categoria_id, descricao, valor, data_lancamento,
             data_vencimento, origem_pagamento, status, data_pagamento)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (periodo_id, categoria_id, descricao, valor, hoje,
          data_vencimento, origem_pagamento, status, data_pagamento))

    conn.commit()
    novo_id = cursor.lastrowid
    conn.close()
    return novo_id


def remover_lancamento(lancamento_id: int):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lancamentos WHERE id = ?", (lancamento_id,))
    conn.commit()
    conn.close()


def mover_lancamento(lancamento_id: int, nova_categoria_id: int):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE lancamentos SET categoria_id = ? WHERE id = ?",
        (nova_categoria_id, lancamento_id)
    )
    conn.commit()
    conn.close()


def buscar_lancamentos_por_categoria(periodo_id: int, categoria_id: int) -> list:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM lancamentos
        WHERE periodo_id = ? AND categoria_id = ?
        ORDER BY ordem, id
    """, (periodo_id, categoria_id))
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items


def reordenar_lancamentos(id_arrastado: int, id_alvo: int):
    """Move id_arrastado para antes de id_alvo, deslocando os itens intermediários."""
    conn = obter_conexao()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT categoria_id, periodo_id FROM lancamentos WHERE id = ?",
        (id_arrastado,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    cat_id, per_id = row["categoria_id"], row["periodo_id"]

    cursor.execute("""
        SELECT id FROM lancamentos
        WHERE categoria_id = ? AND periodo_id = ?
        ORDER BY ordem, id
    """, (cat_id, per_id))
    ids = [r["id"] for r in cursor.fetchall()]

    if id_arrastado not in ids or id_alvo not in ids:
        conn.close()
        return

    src_idx = ids.index(id_arrastado)
    tgt_idx = ids.index(id_alvo)

    ids.remove(id_arrastado)
    new_tgt_idx = ids.index(id_alvo)

    if src_idx < tgt_idx:
        # Movendo para baixo: inserir DEPOIS do alvo
        ids.insert(new_tgt_idx + 1, id_arrastado)
    else:
        # Movendo para cima: inserir ANTES do alvo
        ids.insert(new_tgt_idx, id_arrastado)

    for ordem, item_id in enumerate(ids):
        cursor.execute("UPDATE lancamentos SET ordem = ? WHERE id = ?", (ordem, item_id))

    conn.commit()
    conn.close()
