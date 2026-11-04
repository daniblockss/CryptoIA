# CryptoIA

Agente educacional de análise de mercado cripto com dados somente leitura, IA LLM7, memória, lembretes, painel web e carteira 100% simulada. O programa não envia ordens à corretora, não saca e não transfere dinheiro.

## O que está incluído

- start.py: eleição atômica por lease no Firebase RTDB; mantém apenas um agente ativo.
- Fencing por geração: processos antigos perdem permissão de gravar após perder o lease.
- app/market.py: ticker público da Brasil Bitcoin e cotações CoinMarketCap.
- app/llm7.py: único provedor de IA, com limite diário e intervalo mínimo entre chamadas.
- app/portfolio.py: carteira virtual, posições, histórico, resultado e despesas fictícias.
- app/reminders.py: alertas por preço ou variação percentual e leitura da memória associada.
- app/memory.py: memórias em arquivos Markdown locais e índice no Firebase.
- painel.html: painel web com autenticação, cotações, carteira virtual, lembretes, memórias e status.
- firebase.rules.json: regras de segurança com UID autorizado.

## 1. Preparar Firebase

1. No Firebase Console do projeto cryptoai-160f4, habilite Authentication > Sign-in method > Email/Password.
2. Crie manualmente um usuário em Authentication > Users. Não existe cadastro público pelo painel.
3. Copie o UID desse usuário.
4. Em Realtime Database > Rules, publique as regras de firebase.rules.json, substituindo REPLACE_WITH_YOUR_FIREBASE_AUTH_UID pelo UID copiado.
5. Em Project settings > Service accounts, gere uma chave JSON para o servidor. Guarde-a fora da pasta do projeto e nunca a envie ao GitHub.

As regras permitem leitura apenas ao UID autorizado. O navegador só pode criar comandos de simulação e lembretes; não pode editar carteira, mercado, memórias ou estado do servidor. O SDK Admin do servidor ignora as regras do cliente, por isso proteja muito bem o JSON.

## 2. Preparar servidor Python

Requer Python 3.10+.

```bash
git clone https://github.com/daniblockss/CryptoIA.git
cd CryptoIA
python -m venv .venv
# Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

Edite .env:
- FIREBASE_DATABASE_URL: já está preenchido com o banco deste projeto.
- GOOGLE_APPLICATION_CREDENTIALS: caminho absoluto do JSON de serviço, fora do repositório.
- SERVER_ID: identificador diferente em cada máquina (ex.: pi-casa-01).
- LLM7_API_KEY: token LLM7 do servidor; não coloque no HTML nem no GitHub.
- CMC_API_KEY: opcional; a integração também tenta a API pública keyless.
- Ajuste MARKET_ASSETS, INITIAL_SIMULATED_BRL e os limites de chamadas se desejar.

Inicie com:

```bash
python start.py
```

Para outro servidor participar da eleição, instale o mesmo projeto, configure um SERVER_ID diferente e execute python start.py. Se um servidor já possuir lease válido, o outro fica em espera. Quando o lease expirar ou for liberado, outro pode assumir.

## 3. Publicar o painel

O arquivo painel.html pode ser hospedado como página estática (por exemplo, GitHub Pages). A configuração web do Firebase no HTML é pública por natureza; a proteção vem da autenticação e das regras RTDB, nunca de esconder a API key do Firebase.

## 4. Limites da IA

- LLM7 é o único provedor de IA configurado.
- Limite padrão: 8 chamadas por dia UTC e intervalo mínimo de 5 minutos.
- O agente não chama IA em cada ciclo de cotação; chama quando o usuário pede análise ou quando um lembrete é acionado.
- Sem LLM7_API_KEY, o restante do agente funciona e o painel informa que a IA não foi configurada.

## 5. Escopo e segurança

Este repositório é um simulador educacional: preços públicos são apenas informativos. Compra, venda e taxa PIX são registros fictícios em uma carteira virtual; nenhuma operação é enviada à Brasil Bitcoin ou a qualquer instituição. Não adicione chaves privadas de corretora. Não use o painel como orientação para decisões financeiras.

## Estrutura

```text
CryptoIA/
├── app/
│   ├── agent.py
│   ├── firebase_store.py
│   ├── llm7.py
│   ├── market.py
│   ├── memory.py
│   ├── portfolio.py
│   └── reminders.py
├── data/memories/       # criado em runtime; ignorado pelo Git
├── firebase.rules.json
├── painel.html
├── main.py
├── start.py
├── requirements.txt
└── .env.example
```