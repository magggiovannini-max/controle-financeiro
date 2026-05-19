import flet as ft
from database.setup import inicializar_banco
from screens.tela_mensal import TelaMensal


def main(page: ft.Page):
    # --- Configurações básicas da janela ---
    page.title = "Quinza — Controle Financeiro"
    page.window_maximized = True
    page.window.min_width = 900
    page.window.min_height = 600
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#1a1a2e"
    page.padding = 0

    # Instancia e exibe a tela mensal
    tela = TelaMensal(page)
    page.add(tela.construir())


if __name__ == "__main__":
    inicializar_banco()
    ft.app(target=main)
