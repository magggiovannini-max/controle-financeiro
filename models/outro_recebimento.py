from database.connection import obter_conexao


def criar_outro_recebimento(periodo_id: int, descricao: str, valor: float) -> int:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO outros_recebimentos (periodo_id, descricao, valor) VALUES (?, ?, ?)",
        (periodo_id, descricao, valor),
    )
    conn.commit()
    novo_id = cursor.lastrowid
    conn.close()
    return novo_id


def atualizar_outro_recebimento(rec_id: int, descricao: str, valor: float):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE outros_recebimentos SET descricao = ?, valor = ? WHERE id = ?",
        (descricao, valor, rec_id),
    )
    conn.commit()
    conn.close()


def remover_outro_recebimento(rec_id: int):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM outros_recebimentos WHERE id = ?", (rec_id,))
    conn.commit()
    conn.close()


def buscar_outro_recebimento(rec_id: int) -> dict:
    """Retorna os dados de um outro_recebimento pelo ID, ou None."""
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM outros_recebimentos WHERE id = ?", (rec_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def buscar_outros_recebimentos(periodo_id: int) -> list:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM outros_recebimentos WHERE periodo_id = ? ORDER BY ordem, id",
        (periodo_id,),
    )
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items
