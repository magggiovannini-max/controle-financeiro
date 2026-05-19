from database.connection import obter_conexao


def listar_categorias() -> list:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categorias WHERE ativa = 1 ORDER BY id")
    cats = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return cats


def criar_categoria(nome: str, cor: str) -> int:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO categorias (nome, cor) VALUES (?, ?)",
        (nome, cor),
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


def remover_categoria(cat_id: int) -> bool:
    """Remove a categoria se não tiver lançamentos. Retorna True se removida."""
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM lancamentos WHERE categoria_id = ?",
        (cat_id,),
    )
    total = cursor.fetchone()[0]
    if total > 0:
        conn.close()
        return False
    cursor.execute("DELETE FROM categorias WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()
    return True
