import sqlite3
import os

# O banco de dados fica salvo na mesma pasta do projeto
CAMINHO_BANCO = os.path.join(os.path.dirname(os.path.dirname(__file__)), "quinza.db")


def obter_conexao():
    """
    Abre e retorna uma conexão com o banco de dados SQLite.
    O parâmetro check_same_thread=False permite usar a conexão em diferentes
    partes do app sem causar erros.
    """
    conexao = sqlite3.connect(CAMINHO_BANCO, check_same_thread=False)

    # Isso faz o SQLite retornar as linhas como dicionários (nome da coluna: valor)
    # em vez de tuplas simples. Muito mais fácil de trabalhar!
    conexao.row_factory = sqlite3.Row

    return conexao
