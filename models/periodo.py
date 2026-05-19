from database.connection import obter_conexao


def obter_ou_criar_periodo(mes: int, ano: int) -> dict:
    """
    Busca o período (mês/ano) no banco. Se não existir, cria um novo com
    valores zerados e retorna ele. Assim, o app nunca vai "crashar" ao
    navegar para um mês que ainda não tem dados.
    """
    conn = obter_conexao()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM periodos WHERE mes = ? AND ano = ?",
        (mes, ano)
    )
    periodo = cursor.fetchone()

    if periodo is None:
        cursor.execute(
            "INSERT INTO periodos (mes, ano, valor_dia_15, valor_dia_30) VALUES (?, ?, 0, 0)",
            (mes, ano)
        )
        conn.commit()
        cursor.execute(
            "SELECT * FROM periodos WHERE mes = ? AND ano = ?",
            (mes, ano)
        )
        periodo = cursor.fetchone()

    resultado = dict(periodo)
    conn.close()
    return resultado


def atualizar_valores_periodo(periodo_id: int, valor_dia_15: float, valor_dia_30: float):
    """Salva os valores de salário/recebimento do mês."""
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE periodos SET valor_dia_15 = ?, valor_dia_30 = ? WHERE id = ?",
        (valor_dia_15, valor_dia_30, periodo_id)
    )
    conn.commit()
    conn.close()


def calcular_resumo(periodo_id: int) -> dict:
    """
    Calcula os totais do mês: quanto foi pago, quanto está pendente,
    quantos lançamentos existem e quanto foi gasto de cada pagamento.
    COALESCE(SUM(...), 0) retorna 0 se não houver nenhum lançamento,
    em vez de retornar NULL (que causaria erros de soma).
    """
    conn = obter_conexao()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COALESCE(SUM(valor), 0) FROM lancamentos WHERE periodo_id = ? AND status = 'pago'",
        (periodo_id,)
    )
    total_pago = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COALESCE(SUM(valor), 0) FROM lancamentos WHERE periodo_id = ? AND status = 'pendente'",
        (periodo_id,)
    )
    total_pendente = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM lancamentos WHERE periodo_id = ?",
        (periodo_id,)
    )
    total_lancamentos = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COALESCE(SUM(valor), 0) FROM lancamentos WHERE periodo_id = ? AND origem_pagamento = 15",
        (periodo_id,)
    )
    gasto_15 = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COALESCE(SUM(valor), 0) FROM lancamentos WHERE periodo_id = ? AND origem_pagamento = 30",
        (periodo_id,)
    )
    gasto_30 = cursor.fetchone()[0]

    conn.close()

    return {
        "total_pago": total_pago,
        "total_pendente": total_pendente,
        "total_lancamentos": total_lancamentos,
        "gasto_15": gasto_15,
        "gasto_30": gasto_30,
    }
