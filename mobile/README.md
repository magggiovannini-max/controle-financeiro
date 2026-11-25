# Quinza Mobile

App de controle de gastos para o iPhone. Você **fala** (ou digita) o que gastou e
o app transcreve, separa os itens, classifica cada um numa categoria e pede sua
confirmação antes de salvar.

> “gastei 45,90 no iFood no crédito e 25 de Uber no pix”
> → **iFood** R$ 45,90 · Alimentação · Crédito
> → **Uber** R$ 25,00 · Transporte · Pix

## Como funciona

```
iPhone (app web na tela inicial)
   │  áudio / texto
   ▼
Servidor (FastAPI)
   ├─ Whisper (Groq ou OpenAI) ─ transcreve o áudio
   ├─ Claude ─ extrai valor, descrição, data, forma de pagamento e categoria
   ├─ Memória ─ se você já classificou "iFood" antes, usa a sua escolha
   └─ Banco (Postgres na nuvem / SQLite local)
```

- **Lançar:** botão de microfone (toque para começar e toque para parar) ou campo de texto.
  Os itens aparecem em cartões editáveis. Confira e toque em **Salvar**.
- **Aprendizado:** quando você troca a categoria de um item e salva, o app memoriza
  a escolha (aparece “✓ memorizado” da próxima vez).
- **Gastos:** lista do mês agrupada por dia; toque num gasto para editar ou excluir.
- **Resumo:** total do mês, comparação com o mês anterior, gasto por categoria e
  orçamento (opcional) por categoria.
- **Ajustes:** criar, editar ou remover categorias, com emoji, cor e orçamento.

## Rodar no computador (para testar)

```bash
cd mobile
pip install -r requirements.txt
cp .env.exemplo .env        # preencha as chaves
uvicorn app.main:app --reload
```

Abra http://localhost:8000. O microfone só funciona em `localhost` ou em HTTPS.
Por isso, para usar no iPhone, publique na nuvem.

Testes: `python -m pytest` (a IA é simulada, então não gasta créditos).

## Publicar na nuvem (para usar no iPhone)

Você precisa de três contas:

1. **Chave do Claude:** em [platform.claude.com](https://platform.claude.com), crie
   uma API key e adicione créditos (US$ 5 duram muito tempo para esse uso).
2. **Chave de transcrição:** em [console.groq.com](https://console.groq.com), crie
   uma API key. Se preferir a OpenAI, veja o `.env.exemplo`.
3. **Banco Postgres grátis:** em [neon.tech](https://neon.tech), crie um projeto e
   copie a *connection string*.

Depois, hospede o servidor. Exemplo com o **Render** ([render.com](https://render.com)):

1. *New → Web Service →* conecte este repositório do GitHub.
2. *Root Directory:* `mobile` · *Runtime:* Docker.
3. Em *Environment*, cadastre as variáveis do `.env.exemplo`: `APP_SENHA`,
   `SECRET_KEY`, `ANTHROPIC_API_KEY`, `TRANSCRICAO_API_KEY` e `DATABASE_URL`
   (a do Neon).
4. Faça o deploy. O Render gera um endereço `https://seu-app.onrender.com`.

> No plano grátis do Render, o servidor "dorme" depois de 15 min sem uso, e a
> primeira abertura seguinte demora uns 50 s. O plano pago mais barato elimina isso.
> Railway ou Fly.io também servem: o Dockerfile funciona em qualquer um.

### Instalar no iPhone

1. Abra o endereço no **Safari**.
2. Toque em **Compartilhar → Adicionar à Tela de Início**.
3. Abra pelo ícone “Quinza”, digite a senha e permita o microfone.

## Configurações

| Variável | Para quê |
|---|---|
| `APP_SENHA` | Senha de acesso. Em branco, o app fica aberto (só para uso local). |
| `SECRET_KEY` | Texto aleatório usado para assinar o login. |
| `ANTHROPIC_API_KEY` | Chave do Claude. |
| `CLAUDE_MODEL` | Modelo usado na interpretação (padrão `claude-opus-5-5`). |
| `TRANSCRICAO_API_KEY` | Chave da Groq ou da OpenAI. |
| `TRANSCRICAO_BASE_URL` / `TRANSCRICAO_MODELO` | Provedor e modelo da transcrição (padrão: Groq, `whisper-large-v3-turbo`). |
| `DATABASE_URL` | Postgres na nuvem. Em branco, usa SQLite local. |
| `FUSO_HORARIO` | Fuso usado para "hoje" e "ontem" (padrão `America/Sao_Paulo`). |

## Próximos passos possíveis

- Importar o extrato do Itaú e dos cartões via Open Finance (Pluggy), sem duplicar o que já foi lançado.
- Atalho do iPhone (automação "Transação" da Wallet) que manda cada compra do cartão direto para o app.
- Gastos recorrentes e parcelados.
