def formatar_moeda(valor: float) -> str:
    """Converte 1500.5 em 'R$ 1.500,50'"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_data(data_iso: str) -> str:
    """Converte '2025-06-15' em '15/06/2025'"""
    if not data_iso:
        return "—"
    partes = data_iso.split("-")
    return f"{partes[2]}/{partes[1]}/{partes[0]}"


def nome_mes(mes: int) -> str:
    """Converte o número do mês no nome por extenso em português."""
    nomes = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    return nomes[mes]
