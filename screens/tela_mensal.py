import calendar
import time
import flet as ft
from datetime import date

from models.periodo import obter_ou_criar_periodo, atualizar_valores_periodo, calcular_resumo
from models.lancamento import (
    criar_lancamento,
    atualizar_lancamento,
    remover_lancamento,
    mover_lancamento,
    reordenar_lancamentos,
    buscar_lancamentos_por_categoria,
    copiar_lancamentos_do_periodo,
)
from utils.formatters import formatar_moeda, nome_mes
from database.connection import obter_conexao
from models.outro_recebimento import (
    criar_outro_recebimento,
    atualizar_outro_recebimento,
    remover_outro_recebimento,
    buscar_outros_recebimentos,
)
from models.categoria import (
    listar_categorias,
    criar_categoria,
    atualizar_categoria,
    remover_categoria,
    contar_lancamentos_categoria,
    reordenar_categorias,
)

# Paleta de cores disponíveis para as ilhas
_PALETA_CORES = [
    "#5C6BC0", "#7C4DFF", "#26C6DA", "#66BB6A",
    "#AB47BC", "#EF5350", "#FFA726", "#EC407A",
    "#26A69A", "#78909C", "#FFCA28", "#8D6E63",
]


def _buscar_categorias() -> list:
    return listar_categorias()


class TelaMensal:
    def __init__(self, page: ft.Page):
        self.page = page

        hoje = date.today()
        self.mes = hoje.month
        self.ano = hoje.year

        self.periodo = None
        self.resumo = None
        self.categorias = []

        self._titulo_mes = ft.Text(
            value="",
            size=22,
            weight=ft.FontWeight.BOLD,
            color="#E0E0E0",
        )
        self._campo_15 = ft.TextField(
            hint_text="0,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_color="#26C6DA",
            focused_border_color="#26C6DA",
            cursor_color="#26C6DA",
            color="#E0E0E0",
            text_size=15,
            dense=True,
        )
        self._campo_30 = ft.TextField(
            hint_text="0,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_color="#7C4DFF",
            focused_border_color="#7C4DFF",
            cursor_color="#7C4DFF",
            color="#E0E0E0",
            text_size=15,
            dense=True,
        )
        self._resumo_row = ft.Row(spacing=12)
        self._ilhas_row = ft.Row(
            spacing=12,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self._dragging_id = None      # ID do lançamento sendo arrastado
        self._dragging_cat_id = None  # ID da ilha de origem do arrasto
        self._dragging_ilha_id = None # ID da ilha sendo reordenada

        # Card de recebimentos recolhível
        self._rec_expandido = True
        self._rec_corpo = None       # ft.Column com os inputs (definido em construir())
        self._rec_card = None        # ft.Container do card inteiro
        self._rec_chevron_btn = None # ft.IconButton do toggle

        # Outros recebimentos
        self.total_outros = 0.0
        self._outros_rec_col = ft.Column(spacing=3, scroll=None)
        self._outros_rec_total_text = ft.Text(
            "", size=12, color="#66BB6A", weight=ft.FontWeight.W_500
        )
        # Container que envolve a coluna de itens — altura ajustada
        # dinamicamente para criar o "peek" quando há mais de 3 itens
        self._outros_rec_scroll_box = ft.Container(content=self._outros_rec_col)

    # ------------------------------------------------------------------ #
    #  Dados                                                               #
    # ------------------------------------------------------------------ #

    def _carregar_dados(self):
        self.periodo = obter_ou_criar_periodo(self.mes, self.ano)
        self.resumo = calcular_resumo(self.periodo["id"])
        self.categorias = _buscar_categorias()
        self._titulo_mes.value = f"{nome_mes(self.mes)} {self.ano}"
        self._campo_15.value = self._valor_str(self.periodo["valor_dia_15"])
        self._campo_30.value = self._valor_str(self.periodo["valor_dia_30"])

    def _valor_str(self, valor: float) -> str:
        if valor == 0:
            return ""
        return str(int(valor)) if valor == int(valor) else str(valor)

    # ------------------------------------------------------------------ #
    #  Salvar recebimentos                                                 #
    # ------------------------------------------------------------------ #

    def _salvar_15(self, e):
        self._salvar_valor(15, self._campo_15.value, colapsar=False)

    def _salvar_15_submit(self, e):
        self._salvar_valor(15, self._campo_15.value, colapsar=True)

    def _salvar_30(self, e):
        self._salvar_valor(30, self._campo_30.value, colapsar=False)

    def _salvar_30_submit(self, e):
        self._salvar_valor(30, self._campo_30.value, colapsar=True)

    def _salvar_valor(self, origem: int, valor_str: str, colapsar: bool = False):
        try:
            valor = float(valor_str.replace(",", ".").strip()) if valor_str.strip() else 0.0
            if origem == 15:
                atualizar_valores_periodo(self.periodo["id"], valor, self.periodo["valor_dia_30"])
            else:
                atualizar_valores_periodo(self.periodo["id"], self.periodo["valor_dia_15"], valor)
            self.periodo = obter_ou_criar_periodo(self.mes, self.ano)
            self.resumo = calcular_resumo(self.periodo["id"])
            if colapsar:
                self._recolher_rec()
            self._redesenhar()
        except ValueError:
            pass

    def _recolher_rec(self):
        if self._rec_corpo and self._rec_expandido:
            self._rec_expandido = False
            self._rec_corpo.visible = False
            if self._rec_chevron_btn:
                self._rec_chevron_btn.icon = ft.Icons.EXPAND_MORE

    def _toggle_rec(self, e):
        self._rec_expandido = not self._rec_expandido
        if self._rec_corpo:
            self._rec_corpo.visible = self._rec_expandido
        if self._rec_chevron_btn:
            self._rec_chevron_btn.icon = (
                ft.Icons.EXPAND_LESS if self._rec_expandido else ft.Icons.EXPAND_MORE
            )
        if self._rec_card:
            self._rec_card.update()

    # ------------------------------------------------------------------ #
    #  Outros recebimentos                                                 #
    # ------------------------------------------------------------------ #

    def _atualizar_outros_rec(self):
        """Busca os outros recebimentos do DB e actualiza a coluna visual."""
        outros = buscar_outros_recebimentos(self.periodo["id"])
        self.total_outros = sum(r["valor"] for r in outros)
        self._outros_rec_col.controls = self._construir_outros_items(outros)
        self._outros_rec_total_text.value = (
            formatar_moeda(self.total_outros) if self.total_outros > 0 else ""
        )
        # Altura dinâmica: ≤ 3 itens → cresce livre; > 3 → trava com peek
        # do 4º item (~40% visível), sinalizando que há mais para rolar.
        # Cada item ocupa ≈ 27px (padding 4+4, texto 13pt, spacing 3).
        if len(outros) > 3:
            self._outros_rec_col.scroll = ft.ScrollMode.AUTO
            self._outros_rec_scroll_box.height = 92   # 3 itens + peek do 4º
        else:
            self._outros_rec_col.scroll = None
            self._outros_rec_scroll_box.height = None

    def _construir_outros_items(self, outros: list) -> list:
        """Constrói as linhas de outros recebimentos com o mesmo design das ilhas."""
        if not outros:
            return [
                ft.Text("Nenhum item adicionado", size=11, color="#3a3a5c", italic=True)
            ]

        def _fmt_edit(v: float) -> str:
            return str(int(v)) if v == int(v) else f"{v:.2f}".replace(".", ",")

        def _make_controles(item):
            """Cria os controles de uma linha isolando o escopo de cada item."""
            _ultimo_clique = [0.0]

            texto_valor = ft.Text(formatar_moeda(item["valor"]), size=13, color="#E0E0E0")

            campo_inline = ft.TextField(
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#66BB6A",
                focused_border_color="#66BB6A",
                cursor_color="#66BB6A",
                text_size=13,
                color="#E0E0E0",
                width=90,
                dense=True,
                content_padding=ft.Padding(left=6, right=6, top=2, bottom=2),
            )

            valor_wrapper = ft.Container(
                content=texto_valor,
                tooltip="Duplo clique para editar o valor",
            )

            def _cancelar_inline(e):
                try:
                    valor_wrapper.content = texto_valor
                    valor_wrapper.on_click = _click_valor
                    valor_wrapper.update()
                except Exception:
                    pass

            def _salvar_inline(e):
                campo_inline.on_blur = None
                try:
                    novo_valor = float(
                        (campo_inline.value or "").replace(",", ".").strip()
                    )
                    if novo_valor <= 0:
                        raise ValueError()
                    atualizar_outro_recebimento(
                        item["id"], item["descricao"], novo_valor
                    )
                    self._atualizar_outros_rec()
                    self.resumo = calcular_resumo(self.periodo["id"])
                    self._resumo_row.controls = self._construir_resumo()
                    self.page.update()
                except ValueError:
                    campo_inline.on_blur = _cancelar_inline
                    _cancelar_inline(None)

            def _click_valor(e):
                agora = time.time()
                if agora - _ultimo_clique[0] < 0.35:
                    campo_inline.value = _fmt_edit(item["valor"])
                    valor_wrapper.content = campo_inline
                    valor_wrapper.on_click = None
                    valor_wrapper.update()
                _ultimo_clique[0] = agora

            valor_wrapper.on_click = _click_valor
            campo_inline.on_submit = _salvar_inline
            campo_inline.on_blur = _cancelar_inline

            def _hover_item(e):
                entrando = e.data == "true"
                e.control.bgcolor = "#1e2a45" if entrando else "transparent"
                e.control.border = ft.Border(
                    left=ft.BorderSide(1, "#ffffff18" if entrando else "transparent"),
                    right=ft.BorderSide(1, "#ffffff18" if entrando else "transparent"),
                    top=ft.BorderSide(1, "#ffffff18" if entrando else "transparent"),
                    bottom=ft.BorderSide(1, "#ffffff18" if entrando else "transparent"),
                )
                e.control.update()

            linha_row = ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=8,
                        expand=True,
                        controls=[
                            ft.Container(
                                width=6, height=6, bgcolor="#66BB6A", border_radius=3
                            ),
                            ft.Text(
                                item["descricao"],
                                size=13,
                                color="#C0C0C0",
                                expand=True,
                                no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                    ft.Row(
                        spacing=4,
                        controls=[
                            valor_wrapper,
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.EDIT_OUTLINED, color="#66BB6A60", size=15
                                ),
                                padding=ft.Padding(left=4, right=2, top=4, bottom=4),
                                border_radius=4,
                                tooltip="Editar",
                                on_click=lambda e, it=dict(item): self._abrir_form_edicao_outro_rec(it),
                            ),
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.DELETE_OUTLINE, color="#EF535060", size=15
                                ),
                                padding=ft.Padding(left=2, right=4, top=4, bottom=4),
                                border_radius=4,
                                tooltip="Remover",
                                on_click=lambda e, iid=item["id"]: self._remover_outro_rec(iid),
                            ),
                        ],
                    ),
                ],
            )

            return ft.Container(
                padding=ft.Padding(left=8, right=4, top=4, bottom=4),
                border_radius=8,
                border=ft.Border(
                    left=ft.BorderSide(1, "transparent"),
                    right=ft.BorderSide(1, "transparent"),
                    top=ft.BorderSide(1, "transparent"),
                    bottom=ft.BorderSide(1, "transparent"),
                ),
                on_hover=_hover_item,
                content=linha_row,
            )

        return [_make_controles(item) for item in outros]

    def _abrir_form_outro_rec(self):
        """Abre o modal para adicionar um novo outro recebimento."""
        campo_desc = ft.TextField(
            label="Descrição",
            hint_text="Ex: Freelance, bônus, aluguel…",
            autofocus=True,
            border_color="#66BB6A",
            focused_border_color="#66BB6A",
            cursor_color="#66BB6A",
        )
        campo_valor = ft.TextField(
            label="Valor",
            prefix=ft.Text("R$ "),
            keyboard_type=ft.KeyboardType.NUMBER,
            hint_text="0,00",
            border_color="#66BB6A",
            focused_border_color="#66BB6A",
            cursor_color="#66BB6A",
        )

        modal_ref = [None]

        def _fechar():
            if modal_ref[0]:
                self._fechar_modal(modal_ref[0])

        def salvar(e):
            erros = False

            if not campo_desc.value or not campo_desc.value.strip():
                campo_desc.error_text = "Campo obrigatório"
                erros = True
            else:
                campo_desc.error_text = None

            valor = 0.0
            try:
                valor = float((campo_valor.value or "").replace(",", ".").strip())
                if valor <= 0:
                    raise ValueError()
                campo_valor.error_text = None
            except ValueError:
                campo_valor.error_text = "Digite um valor válido"
                erros = True

            if erros:
                self.page.update()
                return

            try:
                criar_outro_recebimento(
                    self.periodo["id"], campo_desc.value.strip(), valor
                )
            except Exception as ex:
                campo_desc.error_text = f"Erro: {ex}"
                self.page.update()
                return

            _fechar()
            self._atualizar_outros_rec()
            self.resumo = calcular_resumo(self.periodo["id"])
            self._resumo_row.controls = self._construir_resumo()
            self.page.update()

        def cancelar(e):
            _fechar()

        painel = ft.Container(
            width=380,
            bgcolor="#1e2235",
            border_radius=16,
            padding=ft.Padding(left=24, right=24, top=20, bottom=20),
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(spacing=10, controls=[
                                ft.Container(
                                    width=10, height=10,
                                    bgcolor="#66BB6A", border_radius=5,
                                ),
                                ft.Text(
                                    "Novo recebimento",
                                    size=16,
                                    weight=ft.FontWeight.W_500,
                                    color="#E0E0E0",
                                ),
                            ]),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color="#9E9E9E",
                                icon_size=18,
                                on_click=cancelar,
                            ),
                        ],
                    ),
                    ft.Divider(color="#ffffff10", height=1),
                    campo_desc,
                    campo_valor,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        spacing=12,
                        controls=[
                            ft.TextButton("Cancelar", on_click=cancelar),
                            ft.FilledButton("Salvar", on_click=salvar),
                        ],
                    ),
                ],
            ),
        )

        modal = ft.Container(
            expand=True,
            bgcolor="#000000bb",
            alignment=ft.Alignment(x=0, y=0),
            content=painel,
        )
        modal_ref[0] = modal
        self._abrir_modal(modal)

    def _abrir_form_edicao_outro_rec(self, item: dict):
        """Abre o modal de edição pré-preenchido para um outro recebimento."""
        campo_desc = ft.TextField(
            label="Descrição",
            value=item["descricao"],
            autofocus=True,
            border_color="#66BB6A",
            focused_border_color="#66BB6A",
            cursor_color="#66BB6A",
        )
        campo_valor = ft.TextField(
            label="Valor",
            prefix=ft.Text("R$ "),
            keyboard_type=ft.KeyboardType.NUMBER,
            value=str(item["valor"]).replace(".", ","),
            border_color="#66BB6A",
            focused_border_color="#66BB6A",
            cursor_color="#66BB6A",
        )

        modal_ref = [None]

        def _fechar():
            if modal_ref[0]:
                self._fechar_modal(modal_ref[0])

        def salvar(e):
            erros = False

            if not campo_desc.value or not campo_desc.value.strip():
                campo_desc.error_text = "Campo obrigatório"
                erros = True
            else:
                campo_desc.error_text = None

            valor = 0.0
            try:
                valor = float((campo_valor.value or "").replace(",", ".").strip())
                if valor <= 0:
                    raise ValueError()
                campo_valor.error_text = None
            except ValueError:
                campo_valor.error_text = "Digite um valor válido"
                erros = True

            if erros:
                self.page.update()
                return

            try:
                atualizar_outro_recebimento(
                    item["id"], campo_desc.value.strip(), valor
                )
            except Exception as ex:
                campo_desc.error_text = f"Erro: {ex}"
                self.page.update()
                return

            _fechar()
            self._atualizar_outros_rec()
            self.resumo = calcular_resumo(self.periodo["id"])
            self._resumo_row.controls = self._construir_resumo()
            self.page.update()

        def cancelar(e):
            _fechar()

        painel = ft.Container(
            width=380,
            bgcolor="#1e2235",
            border_radius=16,
            padding=ft.Padding(left=24, right=24, top=20, bottom=20),
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(spacing=10, controls=[
                                ft.Container(
                                    width=10, height=10,
                                    bgcolor="#66BB6A", border_radius=5,
                                ),
                                ft.Text(
                                    "Editar recebimento",
                                    size=16,
                                    weight=ft.FontWeight.W_500,
                                    color="#E0E0E0",
                                ),
                            ]),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color="#9E9E9E",
                                icon_size=18,
                                on_click=cancelar,
                            ),
                        ],
                    ),
                    ft.Divider(color="#ffffff10", height=1),
                    campo_desc,
                    campo_valor,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        spacing=12,
                        controls=[
                            ft.TextButton("Cancelar", on_click=cancelar),
                            ft.FilledButton("Salvar", on_click=salvar),
                        ],
                    ),
                ],
            ),
        )

        modal = ft.Container(
            expand=True,
            bgcolor="#000000bb",
            alignment=ft.Alignment(x=0, y=0),
            content=painel,
        )
        modal_ref[0] = modal
        self._abrir_modal(modal)

    def _remover_outro_rec(self, rec_id: int):
        remover_outro_recebimento(rec_id)
        self._atualizar_outros_rec()
        self.resumo = calcular_resumo(self.periodo["id"])
        self._resumo_row.controls = self._construir_resumo()
        self.page.update()

    # ------------------------------------------------------------------ #
    #  Gestão de modais (foco)                                             #
    # ------------------------------------------------------------------ #

    def _abrir_modal(self, modal: ft.Control):
        """Registra o modal no overlay e remove _campo_15/_campo_30 do
        ciclo de Tab enquanto o modal está aberto."""
        self._campo_15.disabled = True
        self._campo_30.disabled = True
        self.page.overlay.append(modal)
        self.page.update()

    def _fechar_modal(self, modal: ft.Control):
        """Oculta o modal e devolve o foco aos campos de recebimento."""
        modal.visible = False
        self._campo_15.disabled = False
        self._campo_30.disabled = False
        self.page.update()

    # ------------------------------------------------------------------ #
    #  Navegação de mês                                                    #
    # ------------------------------------------------------------------ #

    def _mes_anterior(self, e):
        if self.mes == 1:
            self.mes = 12
            self.ano -= 1
        else:
            self.mes -= 1
        self._atualizar_tela()

    def _mes_proximo(self, e):
        if self.mes == 12:
            self.mes = 1
            self.ano += 1
        else:
            self.mes += 1
        self._atualizar_tela()

    def _atualizar_tela(self):
        self._carregar_dados()
        self._redesenhar()

    def _redesenhar(self):
        self._atualizar_outros_rec()
        self._resumo_row.controls = self._construir_resumo()
        self._ilhas_row.controls = self._construir_ilhas()
        self.page.update()

    def _remover_lancamento(self, lancamento_id: int):
        remover_lancamento(lancamento_id)
        self.resumo = calcular_resumo(self.periodo["id"])
        self._redesenhar()

    def _toggle_status(self, lancamento_id: int, ldata: dict):
        """Alterna pago ↔ pendente com um clique no bullet."""
        novo_status = "pendente" if ldata["status"] == "pago" else "pago"
        atualizar_lancamento(
            lancamento_id=lancamento_id,
            descricao=ldata["descricao"],
            valor=ldata["valor"],
            data_vencimento=ldata.get("data_vencimento"),
            origem_pagamento=ldata["origem_pagamento"],
            status=novo_status,
        )
        self.resumo = calcular_resumo(self.periodo["id"])
        self._resumo_row.controls = self._construir_resumo()
        self._ilhas_row.controls = self._construir_ilhas()
        self.page.update()

    def _set_dragging(self, lid: int, cid: int):
        """Registra a fonte do arrasto — chamado pelo on_drag_start do Draggable."""
        self._dragging_id = lid
        self._dragging_cat_id = cid

    def _mover_lancamento(self, nova_cat_id: int):
        """Move o item arrastado para outra ilha."""
        if self._dragging_id is None or self._dragging_cat_id == nova_cat_id:
            return
        src_id = self._dragging_id
        self._dragging_id = None
        self._dragging_cat_id = None
        mover_lancamento(src_id, nova_cat_id)
        self.resumo = calcular_resumo(self.periodo["id"])
        self._redesenhar()

    def _reordenar(self, id_alvo: int, cat_id: int):
        """Insere o item arrastado antes do alvo (mesma ilha) ou move para outra ilha."""
        if self._dragging_id is None or self._dragging_id == id_alvo:
            return
        if self._dragging_cat_id != cat_id:
            self._mover_lancamento(cat_id)
            return
        src_id = self._dragging_id
        self._dragging_id = None
        self._dragging_cat_id = None
        reordenar_lancamentos(src_id, id_alvo)
        self._redesenhar()

    # ------------------------------------------------------------------ #
    #  Formulário de novo lançamento                                       #
    # ------------------------------------------------------------------ #

    def _abrir_form_lancamento(self, cat: dict):
        campo_desc = ft.TextField(
            label="Descrição",
            hint_text="Ex: Conta de luz",
            autofocus=True,
            border_color="#7C4DFF",
            focused_border_color="#7C4DFF",
            cursor_color="#7C4DFF",
        )
        campo_valor = ft.TextField(
            label="Valor",
            prefix=ft.Text("R$ "),
            keyboard_type=ft.KeyboardType.NUMBER,
            hint_text="0,00",
            border_color="#7C4DFF",
            focused_border_color="#7C4DFF",
            cursor_color="#7C4DFF",
        )
        campo_venc = ft.TextField(
            label="Vencimento (opcional)",
            hint_text="DD/MM ou DD/MM/AAAA",
            border_color="#7C4DFF",
            focused_border_color="#7C4DFF",
            cursor_color="#7C4DFF",
        )
        origem_group = ft.RadioGroup(
            value="15",
            content=ft.Row([
                ft.Radio(value="15", label="Dia 15"),
                ft.Radio(value="30", label="Dia 30"),
            ]),
        )
        status_label = ft.Text("Status:", size=12, color="#9E9E9E")
        status_group = ft.RadioGroup(
            value="pendente",
            content=ft.Row([
                ft.Radio(value="pendente", label="Pendente"),
                ft.Radio(value="pago",     label="Pago"),
            ]),
        )

        # ── Parcelado ───────────────────────────────────────────────────
        parcelado_ativo = [False]

        campo_parcelas = ft.TextField(
            value="2",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_color="#7C4DFF",
            focused_border_color="#7C4DFF",
            cursor_color="#7C4DFF",
            width=64,
            dense=True,
            text_align=ft.TextAlign.CENTER,
            content_padding=ft.Padding(left=8, right=8, top=6, bottom=6),
            visible=False,
        )
        sufixo_parcelas = ft.Text("parcelas", size=12, color="#9E9E9E", visible=False)

        def _toggle_parcelado(e):
            parcelado_ativo[0] = e.control.value
            campo_parcelas.visible = parcelado_ativo[0]
            sufixo_parcelas.visible = parcelado_ativo[0]
            # parcelado → status sempre pendente (oculta opção)
            status_label.visible = not parcelado_ativo[0]
            status_group.visible = not parcelado_ativo[0]
            campo_parcelas.update()
            sufixo_parcelas.update()
            status_label.update()
            status_group.update()

        parcelado_row = ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Checkbox(
                    label="Parcelado em",
                    value=False,
                    check_color="#7C4DFF",
                    active_color="#7C4DFF",
                    label_style=ft.TextStyle(size=12, color="#9E9E9E"),
                    on_change=_toggle_parcelado,
                ),
                campo_parcelas,
                sufixo_parcelas,
            ],
        )
        # ── fim parcelado ───────────────────────────────────────────────

        modal_ref = [None]

        def _fechar():
            if modal_ref[0]:
                self._fechar_modal(modal_ref[0])

        def _converter_data(texto: str) -> str:
            partes = texto.strip().split("/")
            if len(partes) == 2:
                dia, mes = int(partes[0]), int(partes[1])
                return f"{self.ano}-{mes:02d}-{dia:02d}"
            elif len(partes) == 3:
                dia, mes, ano = int(partes[0]), int(partes[1]), int(partes[2])
                return f"{ano}-{mes:02d}-{dia:02d}"
            raise ValueError("Formato inválido")

        def _mes_mais_n(mes_base: int, ano_base: int, n: int):
            """Retorna (mes, ano) após n meses a partir de mes_base/ano_base."""
            total = mes_base - 1 + n        # base 0
            return (total % 12) + 1, ano_base + total // 12

        def _ajustar_venc_para_mes(data_iso: str, mes: int, ano: int) -> str:
            """Mantém o dia do vencimento mas ajusta para outro mês/ano."""
            if not data_iso:
                return None
            try:
                dia = int(str(data_iso).split("-")[2])
                dia = min(dia, calendar.monthrange(ano, mes)[1])
                return f"{ano:04d}-{mes:02d}-{dia:02d}"
            except (IndexError, ValueError):
                return None

        def salvar(e):
            erros = False

            if not campo_desc.value or not campo_desc.value.strip():
                campo_desc.error_text = "Campo obrigatório"
                erros = True
            else:
                campo_desc.error_text = None

            valor = 0.0
            try:
                valor = float((campo_valor.value or "").replace(",", ".").strip())
                if valor <= 0:
                    raise ValueError()
                campo_valor.error_text = None
            except ValueError:
                campo_valor.error_text = "Digite um valor válido"
                erros = True

            n_parcelas = 1
            if parcelado_ativo[0]:
                try:
                    n_parcelas = int((campo_parcelas.value or "").strip())
                    if n_parcelas < 2:
                        raise ValueError()
                    campo_parcelas.error_text = None
                except ValueError:
                    campo_parcelas.error_text = "Mín. 2"
                    erros = True

            data_venc = None
            if campo_venc.value and campo_venc.value.strip():
                try:
                    data_venc = _converter_data(campo_venc.value)
                    campo_venc.error_text = None
                except Exception:
                    campo_venc.error_text = "Use DD/MM ou DD/MM/AAAA"
                    erros = True

            if erros:
                self.page.update()
                return

            origem = int(origem_group.value or "15")
            desc_base = campo_desc.value.strip()

            try:
                if n_parcelas == 1:
                    # Lançamento simples
                    criar_lancamento(
                        periodo_id=self.periodo["id"],
                        categoria_id=cat["id"],
                        descricao=desc_base,
                        valor=valor,
                        data_vencimento=data_venc,
                        origem_pagamento=origem,
                        status=status_group.value or "pendente",
                    )
                else:
                    # Cria N lançamentos distribuídos nos próximos N meses
                    mes_base = self.periodo["mes"]
                    ano_base = self.periodo["ano"]
                    for i in range(n_parcelas):
                        mes_i, ano_i = _mes_mais_n(mes_base, ano_base, i)
                        periodo_i = obter_ou_criar_periodo(mes_i, ano_i)
                        venc_i = _ajustar_venc_para_mes(data_venc, mes_i, ano_i)
                        # Só a parcela 1 pode ser "pago"; as demais são pendente
                        st = (status_group.value or "pendente") if i == 0 else "pendente"
                        criar_lancamento(
                            periodo_id=periodo_i["id"],
                            categoria_id=cat["id"],
                            descricao=f"{desc_base} ({i + 1}/{n_parcelas})",
                            valor=valor,
                            data_vencimento=venc_i,
                            origem_pagamento=origem,
                            status=st,
                        )
            except Exception as ex:
                campo_desc.error_text = f"Erro ao salvar: {ex}"
                self.page.update()
                return

            _fechar()
            self.resumo = calcular_resumo(self.periodo["id"])
            self._resumo_row.controls = self._construir_resumo()
            self._ilhas_row.controls = self._construir_ilhas()
            self.page.update()

        def cancelar(e):
            _fechar()

        painel = ft.Container(
            width=420,
            bgcolor="#1e2235",
            border_radius=16,
            padding=ft.Padding(left=24, right=24, top=20, bottom=20),
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(spacing=10, controls=[
                                ft.Container(width=10, height=10, bgcolor=cat["cor"], border_radius=5),
                                ft.Text(f"Nova conta — {cat['nome']}", size=16, weight=ft.FontWeight.W_500, color="#E0E0E0"),
                            ]),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color="#9E9E9E",
                                icon_size=18,
                                on_click=cancelar,
                            ),
                        ],
                    ),
                    ft.Divider(color="#ffffff10", height=1),
                    campo_desc,
                    campo_valor,
                    campo_venc,
                    parcelado_row,
                    ft.Text("Pagar com:", size=12, color="#9E9E9E"),
                    origem_group,
                    status_label,
                    status_group,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        spacing=12,
                        controls=[
                            ft.TextButton("Cancelar", on_click=cancelar),
                            ft.FilledButton("Salvar", on_click=salvar),
                        ],
                    ),
                ],
            ),
        )

        modal = ft.Container(
            expand=True,
            bgcolor="#000000bb",
            alignment=ft.Alignment(x=0, y=0),
            content=painel,
        )
        modal_ref[0] = modal
        self._abrir_modal(modal)

    def _abrir_form_edicao(self, lancamento: dict, cat: dict):
        """Abre o modal de edição pré-preenchido com os dados do lançamento."""

        def _iso_para_br(data_iso) -> str:
            """Converte 'AAAA-MM-DD' → 'DD/MM/AAAA' para exibir no campo."""
            if not data_iso:
                return ""
            p = str(data_iso).split("-")
            return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else ""

        campo_desc = ft.TextField(
            label="Descrição",
            value=lancamento["descricao"],
            autofocus=True,
            border_color="#26C6DA",
            focused_border_color="#26C6DA",
            cursor_color="#26C6DA",
        )
        campo_valor = ft.TextField(
            label="Valor",
            prefix=ft.Text("R$ "),
            keyboard_type=ft.KeyboardType.NUMBER,
            value=str(lancamento["valor"]).replace(".", ","),
            border_color="#26C6DA",
            focused_border_color="#26C6DA",
            cursor_color="#26C6DA",
        )
        campo_venc = ft.TextField(
            label="Vencimento (opcional)",
            hint_text="DD/MM ou DD/MM/AAAA",
            value=_iso_para_br(lancamento.get("data_vencimento")),
            border_color="#26C6DA",
            focused_border_color="#26C6DA",
            cursor_color="#26C6DA",
        )
        origem_group = ft.RadioGroup(
            value=str(lancamento["origem_pagamento"]),
            content=ft.Row([
                ft.Radio(value="15", label="Dia 15"),
                ft.Radio(value="30", label="Dia 30"),
            ]),
        )
        status_group = ft.RadioGroup(
            value=lancamento["status"],
            content=ft.Row([
                ft.Radio(value="pendente", label="Pendente"),
                ft.Radio(value="pago",     label="Pago"),
            ]),
        )

        modal_ref = [None]

        def _fechar():
            if modal_ref[0]:
                self._fechar_modal(modal_ref[0])

        def _converter_data(texto: str) -> str:
            partes = texto.strip().split("/")
            if len(partes) == 2:
                dia, mes = int(partes[0]), int(partes[1])
                return f"{self.ano}-{mes:02d}-{dia:02d}"
            elif len(partes) == 3:
                dia, mes, ano = int(partes[0]), int(partes[1]), int(partes[2])
                return f"{ano}-{mes:02d}-{dia:02d}"
            raise ValueError("Formato inválido")

        def salvar(e):
            erros = False

            if not campo_desc.value or not campo_desc.value.strip():
                campo_desc.error_text = "Campo obrigatório"
                erros = True
            else:
                campo_desc.error_text = None

            valor = 0.0
            try:
                valor = float((campo_valor.value or "").replace(",", ".").strip())
                if valor <= 0:
                    raise ValueError()
                campo_valor.error_text = None
            except ValueError:
                campo_valor.error_text = "Digite um valor válido"
                erros = True

            data_venc = None
            if campo_venc.value and campo_venc.value.strip():
                try:
                    data_venc = _converter_data(campo_venc.value)
                    campo_venc.error_text = None
                except Exception:
                    campo_venc.error_text = "Use DD/MM ou DD/MM/AAAA"
                    erros = True

            if erros:
                self.page.update()
                return

            try:
                atualizar_lancamento(
                    lancamento_id=lancamento["id"],
                    descricao=campo_desc.value.strip(),
                    valor=valor,
                    data_vencimento=data_venc,
                    origem_pagamento=int(origem_group.value or "15"),
                    status=status_group.value or "pendente",
                )
            except Exception as ex:
                campo_desc.error_text = f"Erro ao salvar: {ex}"
                self.page.update()
                return

            _fechar()
            self.resumo = calcular_resumo(self.periodo["id"])
            self._resumo_row.controls = self._construir_resumo()
            self._ilhas_row.controls = self._construir_ilhas()
            self.page.update()

        def cancelar(e):
            _fechar()

        painel = ft.Container(
            width=420,
            bgcolor="#1e2235",
            border_radius=16,
            padding=ft.Padding(left=24, right=24, top=20, bottom=20),
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(spacing=10, controls=[
                                ft.Container(width=10, height=10, bgcolor=cat["cor"], border_radius=5),
                                ft.Text(f"Editar — {cat['nome']}", size=16, weight=ft.FontWeight.W_500, color="#E0E0E0"),
                            ]),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color="#9E9E9E",
                                icon_size=18,
                                on_click=cancelar,
                            ),
                        ],
                    ),
                    ft.Divider(color="#ffffff10", height=1),
                    campo_desc,
                    campo_valor,
                    campo_venc,
                    ft.Text("Pagar com:", size=12, color="#9E9E9E"),
                    origem_group,
                    ft.Text("Status:", size=12, color="#9E9E9E"),
                    status_group,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        spacing=12,
                        controls=[
                            ft.TextButton("Cancelar", on_click=cancelar),
                            ft.FilledButton("Salvar", on_click=salvar),
                        ],
                    ),
                ],
            ),
        )

        modal = ft.Container(
            expand=True,
            bgcolor="#000000bb",
            alignment=ft.Alignment(x=0, y=0),
            content=painel,
        )
        modal_ref[0] = modal
        self._abrir_modal(modal)

    # ------------------------------------------------------------------ #
    #  Copiar lançamentos do mês anterior                                  #
    # ------------------------------------------------------------------ #

    def _abrir_copiar_mes_anterior(self):
        # Calcula mês/ano anterior
        if self.periodo["mes"] == 1:
            mes_ant, ano_ant = 12, self.periodo["ano"] - 1
        else:
            mes_ant, ano_ant = self.periodo["mes"] - 1, self.periodo["ano"]

        # Busca período anterior SEM criá-lo se não existir
        conn = obter_conexao()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM periodos WHERE mes = ? AND ano = ?",
            (mes_ant, ano_ant),
        )
        row = cursor.fetchone()
        periodo_ant = dict(row) if row else None

        qtd = 0
        if periodo_ant:
            cursor.execute(
                "SELECT COUNT(*) FROM lancamentos WHERE periodo_id = ?",
                (periodo_ant["id"],),
            )
            qtd = cursor.fetchone()[0]
        conn.close()

        _MESES = [
            "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
        ]
        nome_ant = f"{_MESES[mes_ant]} {ano_ant}"

        modal_ref = [None]

        def _fechar(e=None):
            if modal_ref[0]:
                self._fechar_modal(modal_ref[0])

        def _confirmar(e):
            if not periodo_ant:
                _fechar()
                return
            copiar_lancamentos_do_periodo(
                periodo_ant["id"],
                self.periodo["id"],
                self.periodo["mes"],
                self.periodo["ano"],
            )
            self.resumo = calcular_resumo(self.periodo["id"])
            self._resumo_row.controls = self._construir_resumo()
            self._ilhas_row.controls = self._construir_ilhas()
            _fechar()
            self.page.update()

        # Conteúdo varia: sem lançamentos anteriores vs. com
        if not periodo_ant or qtd == 0:
            corpo = ft.Column(
                tight=True,
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, color="#9E9E9E", size=32),
                    ft.Text(
                        f"Nenhum lançamento encontrado em {nome_ant}.",
                        size=13,
                        color="#9E9E9E",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.TextButton("Fechar", on_click=_fechar),
                ],
            )
        else:
            corpo = ft.Column(
                tight=True,
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.CONTENT_COPY, color="#26C6DA", size=32),
                    ft.Text(
                        f"Copiar {qtd} lançamento{'s' if qtd != 1 else ''} de {nome_ant}?",
                        size=14,
                        weight=ft.FontWeight.W_500,
                        color="#E0E0E0",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "Todos chegarão como pendente.\nVencimentos serão ajustados para este mês.",
                        size=11,
                        color="#9E9E9E",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.TextButton("Cancelar", on_click=_fechar),
                            ft.FilledButton(
                                "Copiar",
                                style=ft.ButtonStyle(
                                    bgcolor={"": "#26C6DA"},
                                    color={"": "#000000"},
                                ),
                                on_click=_confirmar,
                            ),
                        ],
                    ),
                ],
            )

        painel = ft.Container(
            width=360,
            bgcolor="#1e2235",
            border_radius=16,
            padding=ft.Padding(left=24, right=24, top=24, bottom=24),
            content=corpo,
        )
        modal = ft.Container(
            expand=True,
            bgcolor="#000000bb",
            alignment=ft.Alignment(x=0, y=0),
            content=painel,
        )
        modal_ref[0] = modal
        self._abrir_modal(modal)

    # ------------------------------------------------------------------ #
    #  Gerenciar categorias                                                #
    # ------------------------------------------------------------------ #

    def _abrir_gerenciar_categorias(self, novo: bool = False):
        editando  = [-1 if novo else None]  # cat_id em edição, -1 = nova, None = nenhuma
        cor_sel   = [_PALETA_CORES[0]]
        aviso_txt = ft.Text("", size=11, color="#EF5350", visible=False)

        campo_nome = ft.TextField(
            hint_text="Nome da ilha",
            autofocus=True,
            border_color="#7C4DFF",
            focused_border_color="#7C4DFF",
            cursor_color="#7C4DFF",
            dense=True,
            color="#E0E0E0",
        )

        lista_col = ft.Column(spacing=4)
        modal_ref = [None]

        # ── helpers ────────────────────────────────────────────────────

        def _fechar(e=None):
            if modal_ref[0]:
                self._fechar_modal(modal_ref[0])
            self.categorias = _buscar_categorias()
            self._ilhas_row.controls = self._construir_ilhas()
            self.page.update()

        def _cor_picker():
            dots = []
            for c in _PALETA_CORES:
                sel = c == cor_sel[0]
                dots.append(
                    ft.Container(
                        width=20, height=20,
                        bgcolor=c,
                        border_radius=10,
                        border=ft.Border(
                            left=ft.BorderSide(2, "#E0E0E0" if sel else "transparent"),
                            right=ft.BorderSide(2, "#E0E0E0" if sel else "transparent"),
                            top=ft.BorderSide(2, "#E0E0E0" if sel else "transparent"),
                            bottom=ft.BorderSide(2, "#E0E0E0" if sel else "transparent"),
                        ),
                        on_click=lambda e, cor=c: _selecionar_cor(cor),
                    )
                )
            return ft.Row(spacing=6, controls=dots)

        def _form_edicao():
            return ft.Container(
                bgcolor="#0d1726",
                border_radius=8,
                padding=ft.Padding(left=12, right=12, top=10, bottom=10),
                content=ft.Column(
                    spacing=8,
                    tight=True,
                    controls=[
                        campo_nome,
                        _cor_picker(),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            spacing=8,
                            controls=[
                                ft.TextButton("Cancelar", on_click=lambda e: _cancelar()),
                                ft.FilledButton("Salvar",   on_click=lambda e: _salvar()),
                            ],
                        ),
                    ],
                ),
            )

        def _selecionar_cor(cor):
            cor_sel[0] = cor
            _rebuild()

        def _iniciar_edicao(cat_id, nome, cor):
            editando[0]   = cat_id
            cor_sel[0]    = cor
            campo_nome.value       = nome
            campo_nome.error_text  = None
            aviso_txt.visible = False
            _rebuild()

        def _iniciar_novo():
            editando[0]   = -1
            cor_sel[0]    = _PALETA_CORES[0]
            campo_nome.value       = ""
            campo_nome.error_text  = None
            aviso_txt.visible = False
            _rebuild()

        def _cancelar():
            editando[0] = None
            aviso_txt.visible = False
            _rebuild()

        def _salvar():
            nome = (campo_nome.value or "").strip()
            if not nome:
                campo_nome.error_text = "Campo obrigatório"
                lista_col.update()
                return
            campo_nome.error_text = None
            if editando[0] == -1:
                criar_categoria(nome, cor_sel[0])
            else:
                atualizar_categoria(editando[0], nome, cor_sel[0])
            editando[0] = None
            aviso_txt.visible = False
            _rebuild()

        def _remover(cat_id):
            ok = remover_categoria(cat_id)
            if not ok:
                aviso_txt.value   = "Esta ilha tem lançamentos — remova-os antes de excluí-la."
                aviso_txt.visible = True
            else:
                aviso_txt.visible = False
            _rebuild()

        def _rebuild(atualizar=True):
            cats = listar_categorias()
            rows = []
            for cat in cats:
                if editando[0] == cat["id"]:
                    rows.append(_form_edicao())
                else:
                    rows.append(
                        ft.Container(
                            padding=ft.Padding(left=10, right=4, top=6, bottom=6),
                            border_radius=8,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(spacing=10, controls=[
                                        ft.Container(
                                            width=12, height=12,
                                            bgcolor=cat["cor"],
                                            border_radius=6,
                                        ),
                                        ft.Text(cat["nome"], size=13, color="#D0D0D0"),
                                    ]),
                                    ft.Row(spacing=0, controls=[
                                        ft.Container(
                                            content=ft.Icon(ft.Icons.EDIT_OUTLINED, color="#26C6DA60", size=15),
                                            padding=ft.Padding(left=4, right=2, top=4, bottom=4),
                                            border_radius=4,
                                            tooltip="Editar",
                                            on_click=lambda e, c=cat: _iniciar_edicao(c["id"], c["nome"], c["cor"]),
                                        ),
                                        ft.Container(
                                            content=ft.Icon(ft.Icons.DELETE_OUTLINE, color="#EF535060", size=15),
                                            padding=ft.Padding(left=2, right=4, top=4, bottom=4),
                                            border_radius=4,
                                            tooltip="Remover",
                                            on_click=lambda e, cid=cat["id"]: _remover(cid),
                                        ),
                                    ]),
                                ],
                            ),
                        )
                    )
            if editando[0] == -1:
                rows.append(_form_edicao())
            lista_col.controls = rows
            if atualizar:
                lista_col.update()

        # build inicial — controle ainda não está na página, sem .update()
        _rebuild(atualizar=False)

        painel = ft.Container(
            width=440,
            bgcolor="#1e2235",
            border_radius=16,
            padding=ft.Padding(left=24, right=24, top=20, bottom=20),
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                "Gerenciar Ilhas",
                                size=16,
                                weight=ft.FontWeight.W_500,
                                color="#E0E0E0",
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color="#9E9E9E",
                                icon_size=18,
                                on_click=_fechar,
                            ),
                        ],
                    ),
                    ft.Divider(color="#ffffff10", height=1),
                    lista_col,
                    aviso_txt,
                    ft.Divider(color="#ffffff08", height=1),
                    ft.Container(
                        border_radius=8,
                        padding=ft.Padding(left=8, right=8, top=6, bottom=6),
                        on_click=lambda e: _iniciar_novo(),
                        content=ft.Row(spacing=6, controls=[
                            ft.Icon(ft.Icons.ADD, color="#7C4DFF", size=14),
                            ft.Text("Adicionar ilha", size=12, color="#7C4DFF"),
                        ]),
                    ),
                ],
            ),
        )

        modal = ft.Container(
            expand=True,
            bgcolor="#000000bb",
            alignment=ft.Alignment(x=0, y=0),
            content=painel,
        )
        modal_ref[0] = modal
        self._abrir_modal(modal)

    # ------------------------------------------------------------------ #
    #  Construção visual                                                   #
    # ------------------------------------------------------------------ #

    def _chip_resumo(self, label: str, valor: str, cor: str) -> ft.Control:
        return ft.Container(
            expand=True,
            bgcolor="#16213e",
            border_radius=10,
            padding=ft.Padding(left=14, right=14, top=12, bottom=12),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                controls=[
                    ft.Text(valor, size=15, weight=ft.FontWeight.BOLD, color=cor),
                    ft.Text(label, size=11, color="#9E9E9E"),
                ],
            ),
        )

    def _construir_resumo(self) -> list:
        v15 = self.periodo["valor_dia_15"]
        v30 = self.periodo["valor_dia_30"]
        total_recebido = v15 + v30 + self.total_outros
        gasto = self.resumo["gasto_15"] + self.resumo["gasto_30"]
        s15 = v15 - self.resumo["gasto_15"]
        s30 = v30 - self.resumo["gasto_30"]
        return [
            self._chip_resumo("Total recebido", formatar_moeda(total_recebido), "#E0E0E0"),
            self._chip_resumo("Comprometido",   formatar_moeda(gasto),     "#EF5350"),
            self._chip_resumo("Livre dia 15",   formatar_moeda(s15), "#26C6DA" if s15 >= 0 else "#EF5350"),
            self._chip_resumo("Livre dia 30",   formatar_moeda(s30), "#7C4DFF" if s30 >= 0 else "#EF5350"),
        ]

    def _card_ilha(self, cat: dict) -> ft.Control:
        """
        Cada ilha é um DragTarget — aceita lançamentos arrastados de outras ilhas.
        Cada lançamento é um Draggable com hover escuro e borda sutil.
        """
        lancamentos = buscar_lancamentos_por_categoria(self.periodo["id"], cat["id"])
        total = sum(l["valor"] for l in lancamentos)
        todos_pagos = bool(lancamentos) and all(l["status"] == "pago" for l in lancamentos)

        header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    bgcolor="#1a2848",
                    border_radius=6,
                    padding=ft.Padding(left=10, right=12, top=5, bottom=5),
                    border=ft.Border(
                        left=ft.BorderSide(3, cat["cor"]),
                        right=ft.BorderSide(0, "transparent"),
                        top=ft.BorderSide(0, "transparent"),
                        bottom=ft.BorderSide(0, "transparent"),
                    ),
                    content=ft.Text(
                        cat["nome"],
                        size=12,
                        weight=ft.FontWeight.W_600,
                        color=cat["cor"],
                    ),
                ),
                ft.Row(
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            visible=todos_pagos,
                            content=ft.Icon(
                                ft.Icons.CHECK_CIRCLE_OUTLINE,
                                color="#66BB6A",
                                size=14,
                            ),
                        ),
                        ft.Text(
                            formatar_moeda(total),
                            size=13,
                            color="#66BB6A" if todos_pagos else "#9E9E9E",
                            weight=ft.FontWeight.W_500,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                            icon_color=cat["cor"],
                            icon_size=20,
                            tooltip="Adicionar lançamento",
                            on_click=lambda e, c=cat: self._abrir_form_lancamento(c),
                        ),
                    ],
                ),
            ],
        )

        # Mapa id → índice para determinar direção do arrasto no indicador visual
        id_to_idx = {l["id"]: i for i, l in enumerate(lancamentos)}

        # Helpers de formatação
        def _fmt_edit(v: float) -> str:
            return str(int(v)) if v == int(v) else f"{v:.2f}".replace(".", ",")

        def _fmt_venc(data_iso) -> str:
            """YYYY-MM-DD → DD/MM para exibição discreta no item."""
            if not data_iso:
                return ""
            p = str(data_iso).split("-")
            return f"{p[2]}/{p[1]}" if len(p) == 3 else ""

        linhas = []
        for i, l in enumerate(lancamentos):
            pago    = l["status"] == "pago"
            vencido = (
                not pago
                and bool(l.get("data_vencimento"))
                and l["data_vencimento"] < date.today().isoformat()
            )
            # Paleta visual: pendente = chamativo, pago = discreto
            cor_bullet = "#66BB6A" if pago else "#FFA726"
            tam_bullet = 5 if pago else 9
            cor_desc   = "#455260" if pago else "#D0D0D0"
            cor_valor  = "#455260" if pago else ("#EF5350" if vencido else "#FFA726")
            cor_venc   = "#3d4d55" if pago else ("#EF5350" if vencido else "#5a7080")

            # ── Edição inline de valor ──────────────────────────────────────
            _ultimo_clique = [0.0]

            texto_valor = ft.Text(formatar_moeda(l["valor"]), size=13, color=cor_valor)

            campo_inline = ft.TextField(
                keyboard_type=ft.KeyboardType.NUMBER,
                border_color="#26C6DA",
                focused_border_color="#26C6DA",
                cursor_color="#26C6DA",
                text_size=13,
                color="#E0E0E0",
                width=90,
                dense=True,
                content_padding=ft.Padding(left=6, right=6, top=2, bottom=2),
            )

            # Wrapper que alterna entre texto e campo
            valor_wrapper = ft.Container(
                content=texto_valor,
                tooltip="Duplo clique para editar o valor",
            )

            def _cancelar_inline(e):
                try:
                    valor_wrapper.content = texto_valor
                    valor_wrapper.on_click = _click_valor
                    valor_wrapper.update()
                except Exception:
                    pass  # widget pode ter sido desmontado por um redesenho

            def _salvar_inline(
                e,
                lid=l["id"], desc=l["descricao"],
                dv=l.get("data_vencimento"),
                orig=l["origem_pagamento"], st=l["status"],
            ):
                campo_inline.on_blur = None  # evita _cancelar disparar após on_submit
                try:
                    novo_valor = float(
                        (campo_inline.value or "").replace(",", ".").strip()
                    )
                    if novo_valor <= 0:
                        raise ValueError()
                    atualizar_lancamento(
                        lancamento_id=lid,
                        descricao=desc,
                        valor=novo_valor,
                        data_vencimento=dv,
                        origem_pagamento=orig,
                        status=st,
                    )
                    self.resumo = calcular_resumo(self.periodo["id"])
                    self._resumo_row.controls = self._construir_resumo()
                    self._ilhas_row.controls = self._construir_ilhas()
                    self.page.update()
                except ValueError:
                    campo_inline.on_blur = _cancelar_inline
                    _cancelar_inline(None)

            def _click_valor(e, lval=l["valor"]):
                agora = time.time()
                if agora - _ultimo_clique[0] < 0.35:
                    campo_inline.value = _fmt_edit(lval)
                    valor_wrapper.content = campo_inline
                    valor_wrapper.on_click = None
                    valor_wrapper.update()
                _ultimo_clique[0] = agora

            valor_wrapper.on_click = _click_valor
            campo_inline.on_submit = _salvar_inline
            campo_inline.on_blur  = _cancelar_inline
            # ── fim edição inline ───────────────────────────────────────────

            linha_row = ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            # Bullet clicável — área de toque 22×22, ponto centralizado
                            ft.Container(
                                width=22, height=22,
                                alignment=ft.Alignment(x=0, y=0),
                                border_radius=4,
                                tooltip=(
                                    "Marcar como pendente" if pago
                                    else "Marcar como pago"
                                ),
                                on_click=lambda e, lid=l["id"], ld=dict(l): self._toggle_status(lid, ld),
                                content=ft.Container(
                                    width=tam_bullet, height=tam_bullet,
                                    bgcolor=cor_bullet,
                                    border_radius=tam_bullet,
                                ),
                            ),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                controls=[
                                    ft.Text(l["descricao"], size=13, color=cor_desc),
                                    ft.Text(
                                        _fmt_venc(l.get("data_vencimento")),
                                        size=10,
                                        color=cor_venc,
                                        visible=bool(l.get("data_vencimento")),
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.Row(
                        spacing=4,
                        controls=[
                            ft.Container(
                                bgcolor="#0f3460",
                                border_radius=4,
                                padding=ft.Padding(left=6, right=6, top=2, bottom=2),
                                content=ft.Text(f"dia {l['origem_pagamento']}", size=10, color="#9E9E9E"),
                            ),
                            valor_wrapper,
                            ft.Container(
                                content=ft.Icon(ft.Icons.EDIT_OUTLINED, color="#26C6DA60", size=15),
                                padding=ft.Padding(left=4, right=2, top=4, bottom=4),
                                border_radius=4,
                                tooltip="Editar",
                                on_click=lambda e, ldata=dict(l), c=cat: self._abrir_form_edicao(ldata, c),
                            ),
                            ft.Container(
                                content=ft.Icon(ft.Icons.DELETE_OUTLINE, color="#EF535060", size=15),
                                padding=ft.Padding(left=2, right=4, top=4, bottom=4),
                                border_radius=4,
                                tooltip="Remover",
                                on_click=lambda e, lid=l["id"]: self._remover_lancamento(lid),
                            ),
                        ],
                    ),
                ],
            )

            def _hover_item(e, lid=l["id"], cid=cat["id"]):
                entrando = e.data == "true"
                if entrando:
                    # Garante que _dragging_id aponta para este item enquanto o
                    # cursor está sobre ele — funciona como fallback caso
                    # on_drag_start não dispare (comportamento do Flet 0.85).
                    # Durante o arrasto ativo o Flutter captura o ponteiro,
                    # então hover de outros itens NÃO dispara — a fonte não vaza.
                    self._set_dragging(lid, cid)
                e.control.bgcolor = "#1e2a45" if entrando else "transparent"
                e.control.border = ft.Border(
                    left=ft.BorderSide(1, "#ffffff18" if entrando else "transparent"),
                    right=ft.BorderSide(1, "#ffffff18" if entrando else "transparent"),
                    top=ft.BorderSide(1, "#ffffff18" if entrando else "transparent"),
                    bottom=ft.BorderSide(1, "#ffffff18" if entrando else "transparent"),
                )
                e.control.update()

            conteudo_linha = ft.Container(
                padding=ft.Padding(left=8, right=4, top=4, bottom=4),
                border_radius=8,
                border=ft.Border(
                    left=ft.BorderSide(1, "transparent"),
                    right=ft.BorderSide(1, "transparent"),
                    top=ft.BorderSide(1, "transparent"),
                    bottom=ft.BorderSide(1, "transparent"),
                ),
                on_hover=_hover_item,
                content=linha_row,
            )

            fantasma = ft.Container(
                padding=ft.Padding(left=8, right=4, top=4, bottom=4),
                border_radius=8,
                bgcolor="#1a1a2e",
                content=ft.Row(spacing=8, controls=[
                    ft.Container(width=6, height=6, bgcolor="#3a3a5c", border_radius=3),
                    ft.Text(l["descricao"], size=13, color="#3a3a5c"),
                ]),
            )

            # Dois indicadores: topo (move para cima) e base (move para baixo)
            ind_top = ft.Container(height=2, bgcolor="transparent", border_radius=1)
            ind_bot = ft.Container(height=2, bgcolor="transparent", border_radius=1)

            def _drag_start(e, src_lid=l["id"], src_cid=cat["id"]):
                self._set_dragging(src_lid, src_cid)

            def _item_will_accept(e, my_idx=i, it=ind_top, ib=ind_bot):
                src_id = self._dragging_id
                src_idx_in_list = id_to_idx.get(src_id)
                # Mesmo source_idx < my_idx significa que vem de cima → vai para baixo
                going_down = (src_idx_in_list is not None) and (src_idx_in_list < my_idx)
                if going_down:
                    ib.bgcolor = "#7C4DFF"
                    ib.update()
                else:
                    it.bgcolor = "#7C4DFF"
                    it.update()

            def _item_leave(e, it=ind_top, ib=ind_bot):
                it.bgcolor = "transparent"
                ib.bgcolor = "transparent"
                it.update()
                ib.update()

            def _item_accept(e, tid=l["id"], cid=cat["id"], it=ind_top, ib=ind_bot):
                it.bgcolor = "transparent"
                ib.bgcolor = "transparent"
                it.update()
                ib.update()
                self._reordenar(tid, cid)

            linhas.append(
                ft.DragTarget(
                    group="lancamento",
                    on_will_accept=_item_will_accept,
                    on_leave=_item_leave,
                    on_accept=_item_accept,
                    content=ft.Column(
                        spacing=0,
                        controls=[
                            ind_top,
                            ft.Draggable(
                                group="lancamento",
                                data=str(l["id"]),
                                on_drag_start=_drag_start,
                                content=conteudo_linha,
                                content_when_dragging=fantasma,
                            ),
                            ind_bot,
                        ],
                    ),
                )
            )

        # Área de itens: scrollável e ocupa todo o espaço disponível
        area_itens = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=4,
            controls=linhas if linhas else [
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment(x=0, y=0),
                    content=ft.Text("Nenhum lançamento", size=12, color="#3a3a5c", italic=True),
                ),
            ],
        )

        card_body = ft.Container(
            expand=True,
            bgcolor="#16213e",
            border_radius=12,
            padding=ft.Padding(left=14, right=14, top=14, bottom=14),
            content=ft.Column(
                expand=True,
                spacing=8,
                controls=[
                    header,
                    ft.Divider(color="#ffffff10", height=1),
                    area_itens,
                ],
            ),
        )

        # ── Overlay de confirmação de exclusão ──────────────────────────
        qtd_lanc = contar_lancamentos_categoria(cat["id"])
        aviso_excluir = ft.Text(
            f"Atenção: {qtd_lanc} lançamento{'s' if qtd_lanc != 1 else ''} também será{'o' if qtd_lanc != 1 else ''} excluído{'s' if qtd_lanc != 1 else ''}.",
            size=11,
            color="#FFA726",
            text_align=ft.TextAlign.CENTER,
            visible=qtd_lanc > 0,
        )

        confirm_overlay = ft.Container(
            expand=True,
            visible=False,
            bgcolor="#16213eee",
            border_radius=12,
            alignment=ft.Alignment(x=0, y=0),
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    ft.Text(
                        "Excluir ilha?",
                        size=13,
                        weight=ft.FontWeight.W_600,
                        color="#E0E0E0",
                    ),
                    aviso_excluir,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.TextButton(
                                "Cancelar",
                                on_click=lambda e: _fechar_confirm(),
                            ),
                            ft.FilledButton(
                                "Excluir",
                                style=ft.ButtonStyle(
                                    bgcolor={"": "#EF5350"},
                                    color={"": "#FFFFFF"},
                                ),
                                on_click=lambda e, cid=cat["id"]: _confirmar_excluir(cid),
                            ),
                        ],
                    ),
                ],
            ),
        )

        def _abrir_confirm():
            confirm_overlay.visible = True
            confirm_overlay.update()

        def _fechar_confirm():
            confirm_overlay.visible = False
            confirm_overlay.update()

        def _confirmar_excluir(cid):
            remover_categoria(cid, forcar=True)
            self.categorias = _buscar_categorias()
            self.resumo = calcular_resumo(self.periodo["id"])
            self._resumo_row.controls = self._construir_resumo()
            self._ilhas_row.controls = self._construir_ilhas()
            self.page.update()

        # X discreto no canto superior direito da ilha
        delete_btn = ft.Container(
            right=6,
            top=6,
            width=22,
            height=22,
            border_radius=11,
            bgcolor="transparent",
            alignment=ft.Alignment(x=0, y=0),
            tooltip="Excluir ilha",
            on_click=lambda e: _abrir_confirm(),
            content=ft.Icon(ft.Icons.CLOSE, size=11, color="#2e3f55"),
        )

        def _on_will_accept(e):
            card_body.bgcolor = "#1a2744"
            card_body.update()

        def _on_leave(e):
            card_body.bgcolor = "#16213e"
            card_body.update()

        def _on_accept(e, cid=cat["id"]):
            card_body.bgcolor = "#16213e"
            card_body.update()
            self._mover_lancamento(cid)

        return ft.DragTarget(
            group="lancamento",
            expand=True,
            on_will_accept=_on_will_accept,
            on_accept=_on_accept,
            on_leave=_on_leave,
            content=ft.Stack(
                expand=True,
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                controls=[card_body, confirm_overlay, delete_btn],
            ),
        )

    def _construir_ilhas(self) -> list:
        resultado = []

        for cat in self.categorias:
            card = self._card_ilha(cat)   # DragTarget group="lancamento", expand=True

            # Placeholder que ocupa o slot enquanto a ilha está sendo arrastada
            fantasma_ilha = ft.Container(
                expand=True,
                bgcolor="#0a1525",
                border_radius=12,
                border=ft.Border(
                    left=ft.BorderSide(2, cat["cor"] + "55"),
                    right=ft.BorderSide(2, cat["cor"] + "55"),
                    top=ft.BorderSide(2, cat["cor"] + "55"),
                    bottom=ft.BorderSide(2, cat["cor"] + "55"),
                ),
            )

            # Indicador de inserção: linha vertical à esquerda da ilha alvo
            ind = ft.Container(width=3, border_radius=2, bgcolor="transparent")

            def _drag_start_ilha(e, cid=cat["id"]):
                self._dragging_ilha_id = cid

            draggable = ft.Draggable(
                group="ilha",
                data=str(cat["id"]),
                expand=True,
                on_drag_start=_drag_start_ilha,
                content=card,
                content_when_dragging=fantasma_ilha,
            )

            def _will_accept(e, i=ind):
                i.bgcolor = "#7C4DFF"
                i.update()

            def _leave(e, i=ind):
                i.bgcolor = "transparent"
                i.update()

            def _accept(e, target_cid=cat["id"], i=ind):
                i.bgcolor = "transparent"
                i.update()
                src_id = self._dragging_ilha_id
                self._dragging_ilha_id = None
                if src_id is not None and src_id != target_cid:
                    reordenar_categorias(src_id, target_cid)
                    self.categorias = _buscar_categorias()
                    self._ilhas_row.controls = self._construir_ilhas()
                    self.page.update()

            target = ft.DragTarget(
                group="ilha",
                expand=True,
                on_will_accept=_will_accept,
                on_leave=_leave,
                on_accept=_accept,
                content=ft.Row(
                    spacing=0,
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[ind, draggable],
                ),
            )
            resultado.append(target)

        btn_nova_ilha = ft.Container(
            width=36,
            border_radius=12,
            bgcolor="#16213e",
            alignment=ft.Alignment(x=0, y=0),
            tooltip="Adicionar nova ilha",
            on_click=lambda e: self._abrir_gerenciar_categorias(novo=True),
            content=ft.Icon(ft.Icons.ADD, color="#7C4DFF70", size=20),
        )
        return resultado + [btn_nova_ilha]

    # ------------------------------------------------------------------ #
    #  Construção da tela completa                                         #
    # ------------------------------------------------------------------ #

    def construir(self) -> ft.Control:
        self._carregar_dados()
        self._atualizar_outros_rec()
        self._resumo_row.controls = self._construir_resumo()
        self._ilhas_row.controls = self._construir_ilhas()

        self._campo_15.on_submit = self._salvar_15_submit
        self._campo_15.on_blur   = self._salvar_15
        self._campo_30.on_submit = self._salvar_30_submit
        self._campo_30.on_blur   = self._salvar_30

        self._rec_chevron_btn = ft.IconButton(
            icon=ft.Icons.EXPAND_LESS,
            icon_color="#9E9E9E",
            icon_size=20,
            tooltip="Recolher",
            on_click=self._toggle_rec,
        )

        self._rec_corpo = ft.Column(
            visible=True,
            spacing=0,
            controls=[
                ft.Row(
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        # ── Esquerda: pagamentos dia 15 e dia 30 ─────────────────
                        ft.Column(
                            width=195,
                            spacing=10,
                            controls=[
                                ft.Column(spacing=5, controls=[
                                    ft.Row(spacing=6, controls=[
                                        ft.Container(width=7, height=7, bgcolor="#26C6DA", border_radius=4),
                                        ft.Text("Pagamento dia 15", size=11, color="#9E9E9E"),
                                    ]),
                                    ft.Row(
                                        spacing=6,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            ft.Text("R$", size=13, color="#26C6DA", weight=ft.FontWeight.BOLD),
                                            ft.Container(expand=True, content=self._campo_15),
                                        ],
                                    ),
                                ]),
                                ft.Column(spacing=5, controls=[
                                    ft.Row(spacing=6, controls=[
                                        ft.Container(width=7, height=7, bgcolor="#7C4DFF", border_radius=4),
                                        ft.Text("Pagamento dia 30", size=11, color="#9E9E9E"),
                                    ]),
                                    ft.Row(
                                        spacing=6,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            ft.Text("R$", size=13, color="#7C4DFF", weight=ft.FontWeight.BOLD),
                                            ft.Container(expand=True, content=self._campo_30),
                                        ],
                                    ),
                                ]),
                                ft.Text(
                                    "Enter para salvar e recolher",
                                    size=9,
                                    color="#3a3a5c",
                                    italic=True,
                                ),
                            ],
                        ),
                        # ── Divisor vertical ─────────────────────────────────────
                        ft.VerticalDivider(color="#ffffff18", width=33, thickness=1),
                        # ── Direita: outros recebimentos ─────────────────────────
                        ft.Column(
                            expand=True,
                            spacing=6,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Row(spacing=8, controls=[
                                            ft.Container(
                                                width=7, height=7,
                                                bgcolor="#66BB6A", border_radius=4,
                                            ),
                                            ft.Text(
                                                "Outros recebimentos",
                                                size=11,
                                                color="#9E9E9E",
                                            ),
                                        ]),
                                        ft.Row(
                                            spacing=2,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            controls=[
                                                self._outros_rec_total_text,
                                                ft.Container(
                                                    content=ft.Icon(
                                                        ft.Icons.ADD_CIRCLE_OUTLINE,
                                                        color="#66BB6A",
                                                        size=18,
                                                    ),
                                                    padding=ft.Padding(left=6, right=0, top=4, bottom=4),
                                                    border_radius=4,
                                                    tooltip="Adicionar recebimento",
                                                    on_click=lambda e: self._abrir_form_outro_rec(),
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Divider(color="#243355", height=1),
                                self._outros_rec_scroll_box,
                            ],
                        ),
                    ],
                ),
            ],
        )

        self._rec_card = ft.Container(
            bgcolor="#16213e",
            border_radius=14,
            padding=ft.Padding(left=20, right=20, top=16, bottom=16),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text("Recebimentos do mês", size=12, color="#9E9E9E", weight=ft.FontWeight.W_500),
                            self._rec_chevron_btn,
                        ],
                    ),
                    self._rec_corpo,
                ],
            ),
        )

        return ft.Column(
            expand=True,
            spacing=0,
            controls=[

                # Barra do mês
                ft.Container(
                    bgcolor="#0f3460",
                    padding=ft.Padding(left=20, right=20, top=14, bottom=14),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.CHEVRON_LEFT,
                                icon_color="#E0E0E0",
                                icon_size=28,
                                on_click=self._mes_anterior,
                            ),
                            ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=2,
                                controls=[
                                    self._titulo_mes,
                                    ft.Text("Controle Mensal", size=11, color="#9E9E9E"),
                                ],
                            ),
                            ft.Row(
                                spacing=0,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.CHEVRON_RIGHT,
                                        icon_color="#E0E0E0",
                                        icon_size=28,
                                        on_click=self._mes_proximo,
                                    ),
                                    ft.Container(
                                        content=ft.Icon(
                                            ft.Icons.CONTENT_COPY,
                                            color="#9E9E9E70",
                                            size=14,
                                        ),
                                        padding=ft.Padding(left=0, right=6, top=4, bottom=4),
                                        border_radius=4,
                                        tooltip="Copiar lançamentos do mês anterior",
                                        on_click=lambda e: self._abrir_copiar_mes_anterior(),
                                    ),
                                    ft.Container(
                                        content=ft.Icon(
                                            ft.Icons.TUNE,
                                            color="#9E9E9E70",
                                            size=15,
                                        ),
                                        padding=ft.Padding(left=0, right=6, top=4, bottom=4),
                                        border_radius=4,
                                        tooltip="Gerenciar ilhas",
                                        on_click=lambda e: self._abrir_gerenciar_categorias(),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),

                # Topo fixo: recebimentos + resumo
                ft.Container(
                    padding=ft.Padding(left=20, right=20, top=20, bottom=12),
                    content=ft.Column(
                        spacing=12,
                        controls=[self._rec_card, self._resumo_row],
                    ),
                ),

                # Ilhas: ocupam todo o espaço restante até o fundo
                ft.Container(
                    expand=True,
                    padding=ft.Padding(left=20, right=20, top=0, bottom=20),
                    content=self._ilhas_row,
                ),
            ],
        )
