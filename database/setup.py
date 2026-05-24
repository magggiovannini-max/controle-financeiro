from database.connection import obter_conexao


def criar_tabelas():
    """
    Cria todas as tabelas do banco de dados caso ainda não existam.
    Essa função é chamada uma vez quando o app inicia.
    O 'IF NOT EXISTS' garante que os dados nunca serão apagados ao reiniciar.
    """
    conn = obter_conexao()
    cursor = conn.cursor()

    # --- Tabela de categorias (as "ilhas" de gasto) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nome      TEXT NOT NULL,
            icone     TEXT DEFAULT 'category',
            cor       TEXT DEFAULT '#5C6BC0',
            ativa     INTEGER DEFAULT 1,
            criada_em TEXT DEFAULT (date('now'))
        )
    """)

    # --- Tabela de períodos (um registro por mês/ano) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS periodos (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            mes          INTEGER NOT NULL,
            ano          INTEGER NOT NULL,
            valor_dia_15 REAL DEFAULT 0.0,
            valor_dia_30 REAL DEFAULT 0.0,
            UNIQUE(mes, ano)
        )
    """)

    # --- Tabela de outros recebimentos (renda extra além dos salários) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS outros_recebimentos (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo_id INTEGER NOT NULL,
            descricao  TEXT NOT NULL,
            valor      REAL NOT NULL,
            ordem      INTEGER DEFAULT 0,
            FOREIGN KEY (periodo_id) REFERENCES periodos(id)
        )
    """)

    # --- Tabela de recebimentos fixos (recorrentes todo mês, ex: Caju) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recebimentos_fixos (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            valor     REAL NOT NULL,
            ordem     INTEGER DEFAULT 0
        )
    """)

    # --- Tabela de lançamentos (cada gasto ou conta) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lancamentos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo_id       INTEGER NOT NULL,
            categoria_id     INTEGER NOT NULL,
            descricao        TEXT NOT NULL,
            valor            REAL NOT NULL,
            data_lancamento  TEXT NOT NULL,
            data_vencimento  TEXT,
            origem_pagamento INTEGER NOT NULL CHECK(origem_pagamento IN (15, 30)),
            status           TEXT NOT NULL DEFAULT 'pendente' CHECK(status IN ('pendente', 'pago')),
            data_pagamento   TEXT,
            FOREIGN KEY (periodo_id)   REFERENCES periodos(id),
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        )
    """)

    conn.commit()
    conn.close()


def popular_categorias_padrao():
    """
    Insere as categorias iniciais (ilhas) se o banco ainda estiver vazio.
    Isso roda apenas na primeira vez que o app é aberto.
    """
    conn = obter_conexao()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM categorias")
    total = cursor.fetchone()[0]

    if total == 0:
        categorias = [
            ("Contas Fixas",       "home",         "#5C6BC0"),
            ("Mercado",            "shopping_cart", "#66BB6A"),
            ("Lazer",              "star",          "#AB47BC"),
            ("Cartões de Crédito", "credit_card",   "#EF5350"),
        ]
        cursor.executemany(
            "INSERT INTO categorias (nome, icone, cor) VALUES (?, ?, ?)",
            categorias
        )
        conn.commit()

    conn.close()


def migrar_banco():
    """Adiciona colunas / tabelas novas sem apagar dados existentes."""
    conn = obter_conexao()
    cursor = conn.cursor()
    # Coluna ordem em lancamentos (migração antiga)
    try:
        cursor.execute("ALTER TABLE lancamentos ADD COLUMN ordem INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass
    # Coluna ordem em categorias (para reordenação por arrastar)
    try:
        cursor.execute("ALTER TABLE categorias ADD COLUMN ordem INTEGER DEFAULT 0")
        conn.commit()
        # Inicializa a ordem com base no id atual
        cursor.execute("SELECT id FROM categorias WHERE ativa = 1 ORDER BY id")
        ids = [row[0] for row in cursor.fetchall()]
        for i, cid in enumerate(ids):
            cursor.execute("UPDATE categorias SET ordem = ? WHERE id = ?", (i, cid))
        conn.commit()
    except Exception:
        pass
    # Tabela outros_recebimentos pode não existir em bancos antigos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS outros_recebimentos (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo_id INTEGER NOT NULL,
            descricao  TEXT NOT NULL,
            valor      REAL NOT NULL,
            ordem      INTEGER DEFAULT 0,
            FOREIGN KEY (periodo_id) REFERENCES periodos(id)
        )
    """)
    conn.commit()
    conn.close()


def inicializar_banco():
    """
    Ponto de entrada único para configurar o banco.
    Chamado uma vez no main.py ao iniciar o app.
    """
    criar_tabelas()
    popular_categorias_padrao()
    migrar_banco()
