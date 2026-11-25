"use strict";

// ------------------------------------------------------------------ estado
const estado = {
  token: lerLocal("quinza_token") || "",
  categorias: [],
  mes: mesAtual(),
  propostas: [],          // itens aguardando confirmação
  origemPropostas: "manual",
  transcricao: null,
};

const FORMAS = [
  ["", "Não informado"], ["pix", "Pix"], ["debito", "Débito"],
  ["credito", "Crédito"], ["dinheiro", "Dinheiro"], ["caju", "Caju"],
];
const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const $ = (sel) => document.querySelector(sel);

// ---------------------------------------------------------------- utilidades
function lerLocal(k) { try { return localStorage.getItem(k); } catch { return null; } }
function gravarLocal(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch {} }

function hojeISO() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
function mesAtual() { return hojeISO().slice(0, 7); }
function deslocarMes(mes, delta) {
  const [a, m] = mes.split("-").map(Number);
  const d = new Date(a, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function maiuscula(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
function nomeMes(mes) {
  const [a, m] = mes.split("-").map(Number);
  return maiuscula(new Date(a, m - 1, 1).toLocaleDateString("pt-BR", { month: "long", year: "numeric" }));
}
function nomeDia(iso) {
  const hoje = hojeISO();
  const ontem = new Date(Date.now() - 864e5 - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  if (iso === hoje) return "Hoje";
  if (iso === ontem) return "Ontem";
  const [a, m, d] = iso.split("-").map(Number);
  return maiuscula(new Date(a, m - 1, d).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "short" }));
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function lerValor(txt) {
  let t = String(txt).replace(/[^\d,.-]/g, "");
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  const v = parseFloat(t);
  return Number.isFinite(v) ? Math.round(Math.abs(v) * 100) / 100 : 0;
}
function valorParaCampo(v) { return v ? v.toFixed(2).replace(".", ",") : ""; }
function categoria(id) {
  return estado.categorias.find((c) => c.id === id) || { nome: "—", emoji: "📦", cor: "#78909C" };
}

let avisoTimer;
function avisar(msg, erro = false) {
  const el = $("#aviso");
  el.textContent = msg;
  el.className = "aviso" + (erro ? " erro" : "");
  el.hidden = false;
  clearTimeout(avisoTimer);
  avisoTimer = setTimeout(() => (el.hidden = true), erro ? 5000 : 2500);
}
function carregando(on, txt = "Processando…") {
  $("#carregando-txt").textContent = txt;
  $("#carregando").hidden = !on;
}

// ----------------------------------------------------------------------- API
async function api(caminho, { metodo = "GET", corpo, form } = {}) {
  const headers = {};
  if (estado.token) headers.Authorization = "Bearer " + estado.token;
  let body;
  if (form) body = form;
  else if (corpo !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(corpo); }
  let resp;
  try {
    resp = await fetch(caminho, { method: metodo, headers, body });
  } catch {
    throw new Error("Sem conexão com o servidor.");
  }
  if (resp.status === 401 && caminho !== "/api/login") { sair(); throw new Error("Faça login novamente."); }
  const dados = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const det = dados.detail;
    throw new Error(typeof det === "string" ? det : "Algo deu errado. Confira os campos.");
  }
  return dados;
}

// --------------------------------------------------------------------- login
function sair() {
  estado.token = "";
  gravarLocal("quinza_token", null);
  $("#app").hidden = true;
  $("#tela-login").hidden = false;
}

$("#form-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const erro = $("#erro-login");
  erro.hidden = true;
  try {
    const { token } = await api("/api/login", { metodo: "POST", corpo: { senha: $("#senha").value } });
    estado.token = token;
    gravarLocal("quinza_token", token);
    $("#senha").value = "";
    await iniciarApp();
  } catch (err) {
    erro.textContent = err.message;
    erro.hidden = false;
  }
});

$("#btn-sair").addEventListener("click", sair);

// --------------------------------------------------------------------- abas
let telaAtual = "lancar";
function mostrarTela(nome) {
  telaAtual = nome;
  for (const t of ["lancar", "gastos", "resumo", "ajustes"]) $("#tela-" + t).hidden = t !== nome;
  document.querySelectorAll(".abas button").forEach((b) => b.classList.toggle("ativa", b.dataset.tela === nome));
  window.scrollTo(0, 0);
  atualizarTela();
}
document.querySelectorAll(".abas button").forEach((b) => b.addEventListener("click", () => mostrarTela(b.dataset.tela)));
document.querySelectorAll(".nav-mes").forEach((b) => b.addEventListener("click", () => {
  estado.mes = deslocarMes(estado.mes, Number(b.dataset.delta));
  atualizarTela();
}));

function atualizarTela() {
  document.querySelectorAll(".titulo-mes").forEach((h) => (h.textContent = nomeMes(estado.mes)));
  const acoes = { lancar: carregarRecentes, gastos: carregarGastos, resumo: carregarResumo, ajustes: renderCategorias };
  acoes[telaAtual]().catch((e) => avisar(e.message, true));
}

// ------------------------------------------------------------------ gravação
let gravador = null, pedacos = [], inicioGravacao = 0, timerGravacao = null;

function formatoSuportado() {
  if (!window.MediaRecorder) return null;
  for (const t of ["audio/mp4", "audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"]) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return "";
}

async function iniciarGravacao() {
  const formato = formatoSuportado();
  if (formato === null || !navigator.mediaDevices?.getUserMedia) {
    avisar("Este navegador não grava áudio. Digite o gasto no campo abaixo.", true);
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    avisar("Permita o acesso ao microfone nas configurações do Safari.", true);
    return;
  }
  pedacos = [];
  gravador = formato ? new MediaRecorder(stream, { mimeType: formato }) : new MediaRecorder(stream);
  gravador.ondataavailable = (e) => e.data.size && pedacos.push(e.data);
  gravador.onstop = async () => {
    stream.getTracks().forEach((t) => t.stop());
    clearInterval(timerGravacao);
    $("#btn-mic").classList.remove("gravando");
    $("#status-mic").textContent = "Toque e fale seus gastos";
    const tipo = gravador.mimeType || formato || "audio/mp4";
    const blob = new Blob(pedacos, { type: tipo });
    gravador = null;
    if (Date.now() - inicioGravacao < 700 || blob.size < 1000) {
      avisar("Áudio muito curto.", true);
      return;
    }
    await enviarAudio(blob, tipo);
  };
  gravador.start();
  inicioGravacao = Date.now();
  $("#btn-mic").classList.add("gravando");
  const atualizar = () => {
    const s = Math.floor((Date.now() - inicioGravacao) / 1000);
    $("#status-mic").textContent = `Gravando… ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")} — toque para parar`;
    if (s >= 120) gravador?.stop();
  };
  atualizar();
  timerGravacao = setInterval(atualizar, 500);
}

$("#btn-mic").addEventListener("click", () => {
  if (gravador && gravador.state === "recording") gravador.stop();
  else iniciarGravacao();
});

async function enviarAudio(blob, tipo) {
  const ext = tipo.includes("webm") ? "webm" : tipo.includes("ogg") ? "ogg" : "m4a";
  const form = new FormData();
  form.append("audio", blob, `gasto.${ext}`);
  carregando(true, "Ouvindo e classificando…");
  try {
    const r = await api("/api/interpretar/audio", { metodo: "POST", form });
    mostrarPropostas(r, "audio");
  } catch (e) {
    avisar(e.message, true);
  } finally {
    carregando(false);
  }
}

$("#form-texto").addEventListener("submit", async (e) => {
  e.preventDefault();
  const texto = $("#texto").value.trim();
  if (!texto) return;
  $("#texto").blur();
  carregando(true, "Classificando…");
  try {
    const r = await api("/api/interpretar/texto", { metodo: "POST", corpo: { texto } });
    $("#texto").value = "";
    mostrarPropostas(r, "texto");
  } catch (err) {
    avisar(err.message, true);
  } finally {
    carregando(false);
  }
});

// ---------------------------------------------------------------- propostas
function novaPropostaVazia() {
  const outros = estado.categorias.find((c) => c.nome === "Outros") || estado.categorias[0];
  return { valor: 0, descricao: "", categoria_id: outros?.id, data: hojeISO(), forma_pagamento: null };
}

function mostrarPropostas(r, origem) {
  estado.propostas = r.itens.length ? r.itens : [];
  estado.origemPropostas = origem;
  estado.transcricao = r.transcricao;
  $("#transcricao").textContent = r.transcricao;
  $("#transcricao").hidden = !r.transcricao;
  $("#observacao").textContent = r.observacao || (r.itens.length ? "" : "Não encontrei nenhum valor. Adicione o item manualmente.");
  $("#observacao").hidden = !$("#observacao").textContent;
  if (!estado.propostas.length) estado.propostas = [novaPropostaVazia()];
  renderPropostas();
}

function chipsCategorias(selecionada, attrs = "") {
  return `<div class="chips" ${attrs}>${estado.categorias.map((c) => `
    <button type="button" class="chip ${c.id === selecionada ? "ativo" : ""}" data-cat="${c.id}"
      style="${c.id === selecionada ? `background:${esc(c.cor)}` : ""}">${esc(c.emoji)} ${esc(c.nome)}</button>`).join("")}</div>`;
}
function selectFormas(valor) {
  return `<select data-campo="forma_pagamento">${FORMAS.map(([v, n]) =>
    `<option value="${v}" ${(valor || "") === v ? "selected" : ""}>${n}</option>`).join("")}</select>`;
}

function renderPropostas() {
  const lista = $("#lista-propostas");
  $("#propostas").hidden = estado.propostas.length === 0;
  $("#recentes-box").hidden = estado.propostas.length > 0;
  lista.innerHTML = estado.propostas.map((p, i) => `
    <div class="proposta" data-i="${i}">
      <div class="linha">
        <input class="valor-input" data-campo="valor" type="text" inputmode="decimal" placeholder="0,00" value="${valorParaCampo(p.valor)}">
        ${p.categoria_aprendida ? '<span class="selo-aprendido">✓ memorizado</span>' : ""}
        <button type="button" class="remover" data-remover="${i}" aria-label="Remover">✕</button>
      </div>
      <input type="text" data-campo="descricao" placeholder="Descrição" value="${esc(p.descricao)}" maxlength="120">
      ${chipsCategorias(p.categoria_id)}
      <div class="linha">
        <input type="date" data-campo="data" value="${esc(p.data)}">
        ${selectFormas(p.forma_pagamento)}
      </div>
    </div>`).join("");

  lista.querySelectorAll(".proposta").forEach((card) => {
    const i = Number(card.dataset.i);
    card.querySelectorAll("[data-campo]").forEach((el) => {
      el.addEventListener("input", () => {
        const campo = el.dataset.campo;
        const p = estado.propostas[i];
        if (campo === "valor") p.valor = lerValor(el.value);
        else if (campo === "forma_pagamento") p.forma_pagamento = el.value || null;
        else p[campo] = el.value;
      });
    });
    card.querySelectorAll("[data-cat]").forEach((b) => b.addEventListener("click", () => {
      estado.propostas[i].categoria_id = Number(b.dataset.cat);
      estado.propostas[i].categoria_aprendida = false;
      renderPropostas();
    }));
  });
  lista.querySelectorAll("[data-remover]").forEach((b) => b.addEventListener("click", () => {
    estado.propostas.splice(Number(b.dataset.remover), 1);
    renderPropostas();
  }));
}

$("#btn-add-manual").addEventListener("click", () => {
  estado.propostas.push(novaPropostaVazia());
  renderPropostas();
});

function limparPropostas() {
  estado.propostas = [];
  estado.transcricao = null;
  renderPropostas();
}
$("#btn-descartar").addEventListener("click", limparPropostas);

$("#btn-confirmar").addEventListener("click", async () => {
  const invalido = estado.propostas.findIndex((p) => !p.valor || !p.descricao.trim() || !p.data);
  if (invalido >= 0) { avisar(`Preencha valor, descrição e data do item ${invalido + 1}.`, true); return; }
  try {
    const itens = estado.propostas.map((p) => ({
      valor: p.valor, descricao: p.descricao.trim(), categoria_id: p.categoria_id,
      data: p.data, forma_pagamento: p.forma_pagamento || null,
    }));
    await api("/api/gastos", { metodo: "POST", corpo: { itens, origem: estado.origemPropostas, transcricao: estado.transcricao } });
    const total = itens.reduce((s, i) => s + i.valor, 0);
    avisar(`✅ ${itens.length > 1 ? itens.length + " gastos salvos" : "Gasto salvo"} · ${brl.format(total)}`);
    limparPropostas();
    carregarRecentes().catch(() => {});
  } catch (e) {
    avisar(e.message, true);
  }
});

// -------------------------------------------------------------- lista gastos
function htmlItemGasto(g) {
  const c = categoria(g.categoria_id);
  const forma = FORMAS.find(([v]) => v === g.forma_pagamento)?.[1];
  return `<button class="item-gasto" data-id="${g.id}">
    <span class="icone" style="background:${esc(c.cor)}33">${esc(c.emoji)}</span>
    <span class="info"><strong>${esc(g.descricao)}</strong><small>${esc(c.nome)}${g.forma_pagamento ? " · " + esc(forma) : ""}</small></span>
    <span class="valor">${brl.format(g.valor)}</span></button>`;
}

function ligarItens(container, gastos, aoMudar) {
  container.querySelectorAll(".item-gasto").forEach((b) => b.addEventListener("click", () => {
    const g = gastos.find((x) => x.id === Number(b.dataset.id));
    if (g) abrirEdicaoGasto(g, aoMudar);
  }));
}

async function carregarRecentes() {
  const atual = await api("/api/gastos?mes=" + mesAtual());
  const recentes = atual.slice(0, 5);
  const el = $("#recentes");
  el.innerHTML = recentes.length ? recentes.map(htmlItemGasto).join("") : '<p class="vazio">Nenhum gasto neste mês ainda.</p>';
  ligarItens(el, recentes, carregarRecentes);
}

async function carregarGastos() {
  const gastos = await api("/api/gastos?mes=" + estado.mes);
  $("#total-gastos").textContent = brl.format(gastos.reduce((s, g) => s + g.valor, 0));
  const el = $("#lista-gastos");
  if (!gastos.length) { el.innerHTML = '<p class="vazio">Nenhum gasto neste mês.</p>'; return; }
  const porDia = {};
  for (const g of gastos) (porDia[g.data] ||= []).push(g);
  el.innerHTML = Object.entries(porDia).map(([dia, lista]) => `
    <div class="dia-titulo"><span>${esc(nomeDia(dia))}</span><span>${brl.format(lista.reduce((s, g) => s + g.valor, 0))}</span></div>
    ${lista.map(htmlItemGasto).join("")}`).join("");
  ligarItens(el, gastos, carregarGastos);
}

// -------------------------------------------------------------- folha (sheet)
function abrirFolha(html) {
  $("#folha").innerHTML = html;
  $("#folha").hidden = false;
  $("#folha-fundo").hidden = false;
}
function fecharFolha() {
  $("#folha").hidden = true;
  $("#folha-fundo").hidden = true;
}
$("#folha-fundo").addEventListener("click", fecharFolha);

function abrirEdicaoGasto(g, aoMudar) {
  let catSel = g.categoria_id;
  abrirFolha(`
    <h2>Editar gasto</h2>
    <label>Valor<input id="e-valor" type="text" inputmode="decimal" value="${valorParaCampo(g.valor)}"></label>
    <label>Descrição<input id="e-desc" type="text" value="${esc(g.descricao)}" maxlength="120"></label>
    <label>Categoria${chipsCategorias(catSel, 'id="e-cats"')}</label>
    <label>Data<input id="e-data" type="date" value="${esc(g.data)}"></label>
    <label>Pagamento${selectFormas(g.forma_pagamento).replace("<select", '<select id="e-forma"')}</label>
    <div class="folha-acoes"><button class="btn perigo" id="e-excluir">Excluir</button><button class="btn primario" id="e-salvar">Salvar</button></div>`);

  $("#e-cats").addEventListener("click", (e) => {
    const b = e.target.closest("[data-cat]");
    if (!b) return;
    catSel = Number(b.dataset.cat);
    $("#e-cats").querySelectorAll(".chip").forEach((c) => {
      const ativo = Number(c.dataset.cat) === catSel;
      c.classList.toggle("ativo", ativo);
      c.style.background = ativo ? categoria(catSel).cor : "";
    });
  });
  $("#e-salvar").addEventListener("click", async () => {
    try {
      await api("/api/gastos/" + g.id, { metodo: "PUT", corpo: {
        valor: lerValor($("#e-valor").value), descricao: $("#e-desc").value.trim(),
        categoria_id: catSel, data: $("#e-data").value, forma_pagamento: $("#e-forma").value || null,
      } });
      fecharFolha();
      avisar("Gasto atualizado");
      aoMudar().catch(() => {});
    } catch (e) { avisar(e.message, true); }
  });
  $("#e-excluir").addEventListener("click", async () => {
    if (!confirm(`Excluir "${g.descricao}"?`)) return;
    try {
      await api("/api/gastos/" + g.id, { metodo: "DELETE" });
      fecharFolha();
      avisar("Gasto excluído");
      aoMudar().catch(() => {});
    } catch (e) { avisar(e.message, true); }
  });
}

// -------------------------------------------------------------------- resumo
async function carregarResumo() {
  const r = await api("/api/resumo?mes=" + estado.mes);
  $("#resumo-total").textContent = brl.format(r.total);
  const comp = $("#resumo-comparacao");
  if (r.total_mes_anterior > 0) {
    const dif = ((r.total - r.total_mes_anterior) / r.total_mes_anterior) * 100;
    comp.textContent = `${dif >= 0 ? "▲" : "▼"} ${Math.abs(dif).toFixed(0)}% vs. mês anterior (${brl.format(r.total_mes_anterior)})`;
  } else comp.textContent = "";
  const max = Math.max(...r.categorias.map((c) => Math.max(c.total, c.orcamento || 0)), 1);
  $("#resumo-categorias").innerHTML = r.categorias.map((c) => {
    const ref = c.orcamento || max;
    const pct = Math.min(100, (c.total / ref) * 100);
    let nota = "";
    if (c.orcamento) {
      const resta = c.orcamento - c.total;
      nota = resta >= 0
        ? `<small>Orçamento ${brl.format(c.orcamento)} · restam ${brl.format(resta)}</small>`
        : `<small class="estourou">Orçamento ${brl.format(c.orcamento)} · passou ${brl.format(-resta)}</small>`;
    } else if (c.total_mes_anterior) {
      nota = `<small>Mês anterior: ${brl.format(c.total_mes_anterior)}</small>`;
    }
    const cor = c.orcamento && c.total > c.orcamento ? "var(--perigo)" : esc(c.cor);
    return `<div class="cat-resumo">
      <div class="cabeca"><span>${esc(c.emoji)} ${esc(c.nome)}</span><span>${brl.format(c.total)}</span></div>
      <div class="barra"><div style="width:${pct}%;background:${cor}"></div></div>${nota}</div>`;
  }).join("");
}

// ---------------------------------------------------------------- categorias
async function carregarCategorias() {
  estado.categorias = await api("/api/categorias");
}

async function renderCategorias() {
  await carregarCategorias();
  const el = $("#lista-categorias");
  el.innerHTML = estado.categorias.map((c) => `
    <button class="item-cat" data-id="${c.id}">
      <span class="bolinha" style="background:${esc(c.cor)}"></span>
      <span>${esc(c.emoji)} ${esc(c.nome)}</span>
      <small>${c.orcamento ? "Orçamento " + brl.format(c.orcamento) : ""}</small>
    </button>`).join("");
  el.querySelectorAll(".item-cat").forEach((b) => b.addEventListener("click", () =>
    abrirEdicaoCategoria(estado.categorias.find((c) => c.id === Number(b.dataset.id)))));
}

function abrirEdicaoCategoria(c) {
  const nova = !c;
  c = c || { nome: "", emoji: "📦", cor: "#7c6cff", orcamento: null };
  abrirFolha(`
    <h2>${nova ? "Nova categoria" : "Editar categoria"}</h2>
    <label>Nome<input id="c-nome" type="text" value="${esc(c.nome)}" maxlength="60"></label>
    <div class="linha" style="display:flex;gap:10px">
      <label style="flex:1">Emoji<input id="c-emoji" type="text" value="${esc(c.emoji)}" maxlength="4"></label>
      <label style="flex:1">Cor<input id="c-cor" type="color" value="${esc(c.cor)}" style="width:100%;height:48px;border:0;background:none"></label>
    </div>
    <label>Orçamento mensal (opcional)<input id="c-orc" type="text" inputmode="decimal" value="${valorParaCampo(c.orcamento)}" placeholder="Sem limite"></label>
    <div class="folha-acoes">
      ${nova ? "" : '<button class="btn perigo" id="c-excluir">Remover</button>'}
      <button class="btn primario" id="c-salvar">Salvar</button>
    </div>`);
  $("#c-salvar").addEventListener("click", async () => {
    const corpo = {
      nome: $("#c-nome").value.trim(), emoji: $("#c-emoji").value.trim() || "📦",
      cor: $("#c-cor").value, orcamento: lerValor($("#c-orc").value) || null,
    };
    if (!corpo.nome) { avisar("Dê um nome à categoria.", true); return; }
    try {
      await api(nova ? "/api/categorias" : "/api/categorias/" + c.id, { metodo: nova ? "POST" : "PUT", corpo });
      fecharFolha();
      await renderCategorias();
    } catch (e) { avisar(e.message, true); }
  });
  $("#c-excluir")?.addEventListener("click", async () => {
    if (!confirm(`Remover "${c.nome}"? Os gastos antigos continuam no histórico.`)) return;
    try {
      await api("/api/categorias/" + c.id, { metodo: "DELETE" });
      fecharFolha();
      await renderCategorias();
    } catch (e) { avisar(e.message, true); }
  });
}
$("#btn-nova-categoria").addEventListener("click", () => abrirEdicaoCategoria(null));

// ---------------------------------------------------------------------- início
async function iniciarApp() {
  await carregarCategorias();
  $("#tela-login").hidden = true;
  $("#app").hidden = false;
  mostrarTela("lancar");
}

(async () => {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  try {
    await iniciarApp();
  } catch (e) {
    if (!$("#tela-login").hidden) return; // já foi para o login (401)
    $("#tela-login").hidden = false;
    avisar(e.message, true);
  }
})();
