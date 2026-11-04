# CryptoIA

Agente educacional de análise de mercado cripto, com painel, memória, alertas e
carteira **simulada**. O projeto não executa ordens reais, saques ou pagamentos PIX.

## Arquitetura inicial

- `start.py`: supervisor e eleição de servidor ativo via transação atômica no Firebase RTDB.
- `main.py`: processo do agente (inicialmente em modo simulado).
- Firebase RTDB: coordenação e, nas próximas etapas, estado compartilhado.
- LLM7: será o único provedor de IA; chamadas serão limitadas por orçamento, cache e eventos.
- Brasil Bitcoin e CoinMarketCap: fontes de dados de mercado em modo somente leitura, após validar os endpoints oficiais.
- `painel.html`: painel web será adicionado em uma etapa separada.

## Um agente ativo por vez

Vários servidores podem executar `start.py`, mas a transação em
`/coordination/active_lease` permite que apenas um adquira o lease válido.
O agente renova o lease periodicamente. Se perder a posse, o supervisor encerra
o processo para evitar dois agentes ativos.

## Instalação

Requer Python 3.10 ou superior.

1. Clone o repositório e entre na pasta.
2. Crie um ambiente virtual: `python -m venv .venv`.
3. Ative o ambiente virtual e instale: `pip install -r requirements.txt`.
4. Copie `.env.example` para `.env` e configure os valores.
5. Crie uma conta de serviço no Firebase e guarde o JSON fora desta pasta.
6. Aponte `GOOGLE_APPLICATION_CREDENTIALS` para esse JSON e configure as regras/permissões do RTDB.
7. Execute `python start.py`.

**Nunca** envie o JSON da conta de serviço, arquivos `.env`, chaves de API ou senhas
para o GitHub. O endereço do banco e a configuração web do Firebase não substituem
autenticação nem regras de segurança.

## Próximas etapas

1. Validar regras e autenticação do Firebase.
2. Implementar dados de mercado somente leitura (Brasil Bitcoin e CoinMarketCap).
3. Implementar carteira simulada, histórico e contabilização de taxas hipotéticas.
4. Adicionar memória e lembretes acionados por condições de mercado.
5. Integrar LLM7 com limite rígido de chamadas e custo.
6. Criar `painel.html` com métricas e estado dos servidores.

O projeto deve permanecer em modo simulado: sem negociação automática, saques ou
transferências reais.
