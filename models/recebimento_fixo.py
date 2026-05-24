from database.connection import obter_conexao


def listar_recebimentos_fixos() -> list:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM recebimentos_fixos ORDER BY ordem, id")
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items


def criar_recebimento_fixo(descricao: str, valor: float) -> int:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(ordem), -1) FROM recebimentos_fixos")
    proxima_ordem = cursor.fetchone()[0] + 1
    cursor.execute(
        "INSERT INTO recebimentos_fixos (descricao, valor, ordem) VALUES (?, ?, ?)",
        (descricao, valor, proxima_ordem),
    )
    conn.commit()
    novo_id = cursor.lastrowid
    conn.close()
    return novo_id


def atualizar_recebimento_fixo(fix_id: int, descricao: str, valor: float):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE recebimentos_fixos SET descricao = ?, valor = ? WHERE id = ?",
        (descricao, valor, fix_id),
    )
    conn.commit()
    conn.close()


def remover_recebimento_fixo(fix_id: int):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recebimentos_fixos WHERE id = ?", (fix_id,))
    conn.commit()
    conn.close()
