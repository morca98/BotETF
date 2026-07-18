# Bot de Sinais de Trading (Telegram) — ETFs

Bot que monitoriza os tickers que escolheres e envia **sinais** (não executa
ordens reais) via Telegram, seguindo esta estratégia:

- Para cada ticker, só considera nova entrada se **não houver trade ativo**.
- **Entrada** = mínima do último dia (sessão diária completa mais recente).
- **Alvo** = máxima entre os últimos 2 dias completos.
- Se a diferença percentual `(alvo - entrada) / entrada` for **inferior a 1%**,
  não há entrada nesse dia (fica em "sem setup" até ao dia seguinte).
- **Sem stop loss**: uma vez ativo, o trade só "fecha" no bot quando o preço
  atinge o alvo — independentemente de quanto tempo isso demore.

## ⚠️ Suposições que assumi (ajusta se não for isto que querias)

1. **Fonte de dados**: uso o [yfinance](https://github.com/ranaroussi/yfinance)
   (dados da Yahoo Finance, gratuito, sem necessidade de API key). Funciona
   bem com ETFs listados nos EUA (ex: `SPY`, `QQQ`, `VOO`). Para ETFs
   europeus podes precisar de um sufixo (ex: `VUSA.L` para Londres,
   `IWDA.AS` para Amesterdão) — usa sempre o símbolo tal como aparece no
   Yahoo Finance.
2. **Sinal de saída/alvo**: pediste apenas sinais de entrada, mas sem um
   aviso quando o alvo é atingido o alvo não teria utilidade prática —
   por isso o bot também envia uma mensagem "🎯 ALVO ATINGIDO" quando o
   preço lá chega, e o ticker volta a ficar disponível para um novo setup
   no dia seguinte. Se não quiseres esta mensagem, é fácil remover
   (`strategy.py`).
3. **"Sem stop loss"** é interpretado literalmente: uma vez o trade ativo,
   o bot não fecha por perda, só por atingir o alvo. Não há limite de
   tempo/dias.
4. **Intervalo de verificação**: a cada 60 segundos por omissão
   (`CHECK_INTERVAL_SECONDS`), ajustável. O yfinance não é uma API oficial
   de streaming, por isso não faz sentido descer muito abaixo disto.
5. O bot **não executa ordens reais** — é só sinalização via Telegram.
   Integração com uma corretora teria de ser adicionada à parte.

## Como funciona por dentro

```
main.py         -> comandos do Telegram + loop periódico
strategy.py     -> lógica de decisão (quando calcular setup, entrar, sair)
market_data.py  -> obtém dados do yfinance (histórico diário + preço atual)
state.py        -> guarda o estado (tickers, chat_id) em state.json
config.py       -> lê variáveis de ambiente
```

## 1. Criar o bot no Telegram

1. Fala com o [@BotFather](https://t.me/BotFather) no Telegram.
2. Envia `/newbot` e segue as instruções.
3. Guarda o **token** que ele te dá (algo como `123456:ABC-DEF...`).

## 2. Testar localmente (opcional)

```bash
cd telegram-trading-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edita o .env e coloca o teu TELEGRAM_BOT_TOKEN

export $(cat .env | xargs)   # carrega as variáveis para a shell
python3 main.py
```

Depois no Telegram, abre uma conversa com o teu bot e envia `/start`,
depois `/add SPY QQQ` (por exemplo).

## 3. Deploy no Railway

1. Cria um repositório no GitHub com estes ficheiros (ou usa o Railway CLI
   para fazer deploy direto de uma pasta local).
2. Em [railway.app](https://railway.app), cria um **New Project** →
   **Deploy from GitHub repo** e escolhe o repositório.
3. O Railway deteta o Python automaticamente via `requirements.txt` e usa
   o `Procfile` (`worker: python main.py`) para correr o bot como processo
   de fundo — não precisa de porta HTTP.
4. Em **Variables**, adiciona:
   - `TELEGRAM_BOT_TOKEN` = o token do BotFather
   - (opcional) `CHECK_INTERVAL_SECONDS`, `MIN_PCT_DIFF`
5. **Persistência do estado (importante):** por omissão, `state.json` fica
   no sistema de ficheiros efémero do container — se o Railway reiniciar
   ou fizeres um novo deploy, perdes os tickers e trades ativos guardados.
   Para evitar isto:
   - No serviço, vai a **Settings → Volumes** e cria um Volume (ex:
     montado em `/data`).
   - Define a variável `STATE_FILE=/data/state.json`.
6. Faz deploy. Nos **Logs** do Railway deves ver `Bot a arrancar...`.

## Comandos do bot

- `/start` — regista o teu chat e mostra ajuda
- `/add TICKER [TICKER2 ...]` — começa a monitorizar ticker(s), ex: `/add SPY QQQ`
- `/remove TICKER` — para de monitorizar
- `/list` — mostra o estado atual de cada ticker (a calcular / à espera de
  entrada / ativo / sem setup hoje)
- `/help` — mostra os comandos

## Limitações a ter em conta

- O `yfinance` não é uma API oficial — em caso de mudanças na Yahoo Finance
  pode falhar ou ficar temporariamente indisponível. Para uso mais sério,
  considera trocar por uma API paga (Alpha Vantage, Twelve Data, Polygon.io).
- ETFs só negoceiam durante o horário de mercado da bolsa onde estão
  listados; fora desse horário o preço atual não muda.
- Como não há stop loss, um trade ativo pode ficar aberto durante muitos
  dias (ou nunca atingir o alvo) — isto é assumido como intencional da tua
  estratégia.
