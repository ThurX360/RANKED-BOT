# RANKED-BOT

Bot de Discord pensado para organizar filas ranqueadas personalizadas para comunidades de jogos. Ele oferece gerenciamento de partidas, ranking por pontos, economia interna com itens e integração opcional com canais pré-configurados para automatizar avisos.

## ✨ Recursos principais
- **Filas ranqueadas (2v2, 3v3 ou 4v4)** com verificação automática de voz, divisão equilibrada de times e registro de partidas.
- **Sistema de pontuação e tiers** com medalhas por sequência de vitórias e histórico individual de partidas.
- **Economia in-bot**: moedas por vitória/derrota, itens _Double_ (x2 pontos) e _Shield_ (proteção contra derrota), além de loja para comprar/vender itens.
- **Comandos de relatório** para ver perfil, inventário, ranking, top vitórias/derrotas/streak e histórico.
- **Integração com canais configuráveis** para fila, notificações, logs e resultados automáticos.
- **Recompensas diárias** com cooldown configurado e sorteio de moedas ou itens.

## 📦 Requisitos
- Python 3.10 ou superior
- Token de bot do Discord com privilégios necessários (gerencie em <https://discord.com/developers/applications>)
- Biblioteca [`discord.py`](https://discordpy.readthedocs.io/en/stable/) na versão 2.x

### Instalando dependências
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install discord.py
```

## ⚙️ Configuração
1. Crie um arquivo `.env` (ou defina a variável de ambiente) com o token do bot:
   ```bash
   export DISCORD_TOKEN="seu_token_aqui"
   ```
   > Em produção, recomenda-se usar um gerenciador de segredos em vez de deixar o token exposto.
2. (Opcional) Ajuste valores de pontuação, preços e cooldowns editando as constantes no início de `bot.py`.
3. Os dados persistentes são salvos automaticamente nos arquivos JSON:
   - `players.json`: perfis dos jogadores e inventário.
   - `matches.json`: histórico completo de partidas.
   - `config.json`: IDs dos canais configurados pelo comando `!setcanal`.

## 🚀 Execução
Execute o bot após ativar o ambiente virtual:
```bash
python bot.py
```
O bot carregará os arquivos JSON existentes (ou criará novos) e ficará online aguardando comandos. Use `!ajuda` dentro do Discord para ver a lista completa de comandos prefixados e _slash_.

### 🔁 Monitoramento contínuo de mercado
O utilitário `ranking_bot/market_analyzer.py` acompanha um arquivo JSON com histórico de preços de jogadores e sugere quais atletas comprar ou vender. Para testar o fluxo rapidamente, copie o arquivo de exemplo:

```bash
cp market_data.sample.json market_data.json
python ranking_bot/market_analyzer.py --once
```

Para manter o monitoramento rodando de forma contínua:

```bash
python ranking_bot/market_analyzer.py --interval 120 --top 5
```

> Ajuste `market_data.json` com seus próprios dados (preços, demanda e oferta) para obter recomendações personalizadas.

## 📚 Comandos principais
| Comando | Descrição |
|---------|-----------|
| `!fila [2|3|4]` | Abre/entra na fila ranqueada do canal de voz atual (há versão _slash_). |
| `!perfil [@user]` | Mostra o perfil do jogador com pontos, tier e medalhas. |
| `!inventario` | Lista itens disponíveis para uso em partidas. |
| `!top`, `!topvitorias`, `!topderrotas`, `!topstreak` | Rankings por pontos, vitórias, derrotas e sequência. |
| `!historico [@user]` | Histórico recente de partidas do jogador. |
| `!setcanal <tipo>` | Configura canais de fila, ranking, notificações e logs. |
| `!loja`, `!comprar`, `!vender` | Interagem com a economia do bot. |
| `!presentear @user <coins>` | Transfere coins para outro jogador. |
| `!daily` | Resgata recompensa diária se o cooldown já expirou. |

> Todos os comandos acima possuem versões _slash_ (`/fila`, `/perfil`, `/inventario`, `/top`, `/topvitorias`, `/topderrotas`, `/topstreak`, `/historico`, `/saldo`, `/loja`, `/comprar`, `/vender`, `/presentear`, `/daily`).

## 📝 Desenvolvimento
- O código utiliza `discord.ext.commands` e comandos _slash_ via `discord.app_commands`.
- Estruturas em memória (`players`, `matches`, `active_queues`) são sincronizadas com JSON a cada alteração.
- Recomenda-se testar em um servidor privado antes de levar o bot a produção.

Contribuições são bem-vindas! Abra uma _issue_ ou envie um _pull request_ com melhorias e correções.
