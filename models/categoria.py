from database.connection import obter_conexao


def listar_categorias() -> list:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categorias WHERE ativa = 1 ORDER BY ordem, id")
    cats = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return cats


def criar_categoria(nome: str, cor: str) -> int:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(ordem), -1) FROM categorias WHERE ativa = 1")
    proxima_ordem = cursor.fetchone()[0] + 1
    cursor.execute(
        "INSERT INTO categorias (nome, cor, ordem) VALUES (?, ?, ?)",
        (nome, cor, proxima_ordem),
    )
    conn.commit()
    novo_id = cursor.lastrowid
    conn.close()
    return novo_id


def atualizar_categoria(cat_id: int, nome: str, cor: str):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE categorias SET nome = ?, cor = ? WHERE id = ?",
        (nome, cor, cat_id),
    )
    conn.commit()
    conn.close()


def reordenar_categorias(src_id: int, target_id: int):
    """Move a categoria src_id para antes de target_id na ordem horizontal."""
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM categorias WHERE ativa = 1 ORDER BY ordem, id"
    )
    ids = [row[0] for row in cursor.fetchall()]

    if src_id not in ids or target_id not in ids or src_id == target_id:
        conn.close()
        return

    ids.remove(src_id)
    tgt_idx = ids.index(target_id)
    ids.insert(tgt_idx, src_id)

    for ordem, cid in enumerate(ids):
        cursor.execute("UPDATE categorias SET ordem = ? WHERE id = ?", (ordem, cid))

    conn.commit()
    conn.close()


def contar_lancamentos_categoria(cat_id: int) -> int:
    """Retorna a quantidade de lançamentos vinculados à categoria."""
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM lancamentos WHERE categoria_id = ?",
        (cat_id,),
    )
    total = cursor.fetchone()[0]
    conn.close()
    return total


def remover_categoria(cat_id: int, forcar: bool = False) -> bool:
    """Remove a categoria.
    Se forcar=False (padrão), retorna False se houver lançamentos.
    Se forcar=True, exclui os lançamentos vinculados antes de remover.
    Retorna True se a categoria foi removida."""
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM lancamentos WHERE categoria_id = ?",
        (cat_id,),
    )
    total = cursor.fetchone()[0]
    if total > 0 and not forcar:
        conn.close()
        return False
    if total > 0:
        cursor.execute("DELETE FROM lancamentos WHERE categoria_id = ?", (cat_id,))
    cursor.execute("DELETE FROM categorias WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()
    return True
