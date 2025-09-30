# RANKED-BOT

Bot de Discord voltado para organizar partidas ranqueadas em servidores de jogos. Ele automatiza a criação de filas 2v2, 3v3 ou 4v4, sorteia times, gerencia pontos, histórico, economia in-game e envia resumos visuais de cada partida.

## Recursos principais
- Fila com botões (slash command e comando prefixado) exigindo que os jogadores estejam em call.
- Sorteio automático de times com criação de canais de voz/texto temporários e movimentação dos jogadores.
- Painel para capitães decidirem vencedor/MVP e painel para jogadores ativarem itens (`✖2 Dobro` e `🛡️ Escudo`).
- Sistema de pontos com medalhas de streak, ranking automático e atualização de apelidos conforme a colocação.
- Economia simples com coins, loja, inventário, bônus diário e itens consumíveis.
- Histórico completo das partidas com registros em `matches.json` e envio de logs para canal dedicado.

## Pré-requisitos
- Python 3.10 ou superior.
- Um token de bot do Discord com intents **Message Content**, **Members** e **Voice States** ativadas.
- Permissões administrativas suficientes para criar/editar canais, mover membros e gerenciar apelidos.

## Instalação
1. Clone o repositório e acesse a pasta do projeto.
2. (Opcional) Crie e ative um ambiente virtual.
3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
4. Defina o token do bot:
   - Exporte a variável `DISCORD_TOKEN`, **ou**
   - Edite a constante `TOKEN` no topo de `bot.py`.

## Execução
```bash
python bot.py
```
Ao iniciar, o bot sincroniza os slash commands automaticamente. Se preferir, execute `python bot.py` em um processo supervisionado (systemd, pm2, etc.) para manter o serviço ativo.

## Persistência de dados
O bot utiliza arquivos JSON na raiz do projeto:
- `players.json`: perfil de jogadores, estatísticas, inventário e moedas.
- `matches.json`: histórico das partidas.
- `config.json`: ids dos canais configurados.

Esses arquivos são ignorados pelo Git (ver `.gitignore`). Faça backup periódico caso utilize o bot em produção.

## Comandos principais
| Comando | Descrição |
| ------- | --------- |
| `!fila [2|3|4]` ou `/fila` | Cria fila ranqueada (2v2, 3v3 ou 4v4). |
| `!perfil [@membro]` | Exibe estatísticas completas do jogador. |
| `!inventario` / `!inv` | Mostra itens disponíveis (Dobro / Escudo). |
| `!top` | Atualiza ranking e apelidos dos jogadores. |
| `!topvitorias`, `!topderrotas`, `!topstreak` | Rankings específicos. |
| `!historico` | Lista partidas recentes com detalhes. |
| `!ajuda` | Painel de ajuda resumindo os comandos disponíveis. |
| `!saldo`, `!loja`, `!comprar`, `!vender` | Economia e itens consumíveis. |
| `!daily` | Recompensa diária com moedas ou itens. |

### Administração
| Comando | Descrição |
| ------- | --------- |
| `!setcanal <tipo> #canal` | Define canais padrão (`fila`, `partida`, `ranking`, `notificacoes`, `logs`). |
| `!canais` | Exibe canais configurados. |

## Pontuação e itens
- Vitória: `+50` pontos, derrota: `-30` pontos.
- MVP concede `+25` pontos extras.
- `✖2 Dobro` dobra o resultado (vitória ou derrota) para quem usar.
- `🛡️ Escudo` protege contra perda de pontos em caso de derrota.
- Medalhas automáticas em streaks de 3, 5 e 10 vitórias consecutivas.

## Estrutura do projeto
```
.
├── bot.py          # Código principal do bot
├── README.md       # Este arquivo
├── requirements.txt
└── .gitignore
```

## Desenvolvimento
Sinta-se à vontade para abrir issues ou PRs com melhorias. Algumas ideias:
- Painéis adicionais no histórico ou dashboards web.
- Integrações com bancos de dados persistentes.
- Tradução multilíngue dos comandos/mensagens.

> 💡 Dica: mantenha o bot hospedado em um servidor com conexão estável para evitar filas interrompidas. Faça backups dos arquivos JSON para preservar o progresso dos jogadores.
