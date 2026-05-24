from database.connection import obter_conexao


def listar_gastos_caju(periodo_id: int) -> list:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM gastos_caju WHERE periodo_id = ? ORDER BY data, id",
        (periodo_id,),
    )
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items


def criar_gasto_caju(periodo_id: int, descricao: str, valor: float, data: str) -> int:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO gastos_caju (periodo_id, descricao, valor, data) VALUES (?, ?, ?, ?)",
        (periodo_id, descricao, valor, data),
    )
    conn.commit()
    novo_id = cursor.lastrowid
    conn.close()
    return novo_id


def remover_gasto_caju(gasto_id: int):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gastos_caju WHERE id = ?", (gasto_id,))
    conn.commit()
    conn.close()
