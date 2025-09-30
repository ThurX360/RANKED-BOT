# Ranked Bot

Bot de Discord focado em organizar filas ranqueadas 2v2/3v3/4v4 com painel interativo,
controle de pontos, economia e histórico de partidas.

## Principais recursos
- Fila com botões e validação de que o jogador está em um canal de voz.
- Sorteio automático de times, criação de canais temporários e painel para capitães.
- Itens estratégicos (✖2 Dobro e 🛡️ Escudo) com inventário, loja e recompensa diária.
- Sistema de ranking com medalhas por sequência, MVP e alteração automática de apelidos.
- Histórico das últimas partidas e painéis de top vitórias/derrotas/streak.
- Feedback amigável de erros e gravação atômica dos dados em JSON.

## Requisitos
- Python 3.10+
- Biblioteca [`discord.py`](https://discordpy.readthedocs.io/en/stable/) versão 2.3 ou superior:
  ```bash
  pip install -U "discord.py>=2.3"
  ```

## Configuração rápida
1. Crie um bot no [Portal de Desenvolvedores do Discord](https://discord.com/developers/applications) e copie o token.
2. Defina a variável de ambiente `DISCORD_TOKEN` com o token criado.
3. (Opcional) Defina `RANKED_BOT_DATA` para escolher onde os arquivos `players.json`,
   `matches.json` e `config.json` serão armazenados. Por padrão eles ficam na pasta `data/`.
4. Execute o bot:
   ```bash
   python bot.py
   ```

Ao rodar pela primeira vez, use `!setcanal <tipo> #canal` para configurar os canais de fila,
partidas, ranking, notificações e logs.

## Comandos úteis
- `!fila [2|3|4]` ou `/fila`: abre uma fila interativa.
- `!perfil [@jogador]`: mostra perfil completo com medalhas e posição no ranking.
- `!rank [@jogador]`: destaca apenas a posição e estatísticas principais.
- `!inventario`, `!saldo`, `!loja`, `!comprar`, `!vender`: economia e itens.
- `!historico [@jogador]`: últimas 5 partidas do jogador.
- `!top`, `!topvitorias`, `!topderrotas`, `!topstreak`: painéis de ranking.
- `!daily`: recompensa diária com cooldown inteligente.
- `!setcanal <tipo> #canal`: define canais usados pelo bot (necessita administrador).

## Desenvolvimento
- O módulo principal é `bot.py`. Toda a persistência é feita em arquivos JSON com escrita
  atômica para evitar corrupção em quedas de energia.
- Para facilitar debugging, o bot utiliza logging com nível INFO por padrão.
- Novas estruturas de jogadores são garantidas pela função `ensure_player`, mantendo
  compatibilidade com dados antigos.

Sinta-se à vontade para adaptar pontos, recompensas e mensagens às regras do seu servidor!

