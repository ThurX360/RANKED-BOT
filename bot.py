
import os
import json
import random
import datetime as dt
from typing import Dict, List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

# =========================
#           CONFIG
# =========================
TOKEN = os.getenv("DISCORD_TOKEN") or "COLE_SEU_TOKEN_AQUI"
PREFIX = "!"

# Pontos
WIN_POINTS = 50
LOSS_POINTS = -30
MVP_BONUS = 25  # não dobra

# Itens
ITEM_DOUBLE = "double"   # ✖2
ITEM_SHIELD = "shield"   # 🛡️

# Medalhas por streak
STREAK_MEDALS = {3: "🔥 3-streak", 5: "⚡ 5-streak", 10: "🏆 10-streak"}

# Economia / Loja
COINS_WIN = 20
COINS_LOSS = 5
ITEM_PRICE = {ITEM_SHIELD: 5, ITEM_DOUBLE: 5}
DAILY_REWARDS = [
    ("coins", 1), ("coins", 2), ("coins", 5), ("coins", 10),
    ("item", ITEM_SHIELD), ("item", ITEM_DOUBLE),
]
DAILY_COOLDOWN_HOURS = 20

# Arquivos
PLAYERS_FILE = "players.json"
MATCHES_FILE = "matches.json"
CONFIG_FILE  = "config.json"

# =========================
#        STORAGE
# =========================
def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

players: Dict[str, dict] = load_json(PLAYERS_FILE, {})
matches: List[dict] = load_json(MATCHES_FILE, [])
config  = load_json(CONFIG_FILE, {
    "channels": {
        "fila": None,
        "partida": None,
        "ranking": None,
        "notificacoes": None,
        "logs": None
    }
})

def ensure_player(pid: str):
    if pid not in players:
        players[pid] = {
            "points": 0,
            "wins": 0,
            "losses": 0,
            "mvps": 0,
            "streak": 0,
            "max_streak": 0,
            "medals": [],
            "items": {ITEM_DOUBLE: 1, ITEM_SHIELD: 1},
            "history": [],
            "coins": 0,
            "last_daily": None
        }

# =========================
#           BOT
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True  # para checar/mover em calls
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# estado temporário
active_queues: Dict[int, dict] = {}   # por canal
active_matches: Dict[int, dict] = {}  # por canal

# =========================
#        HELPERS
# =========================
def tier_of(points: int) -> Tuple[str, str]:
    if points < 100:  return "Bronze", "🥉"
    if points < 250:  return "Prata", "🥈"
    if points < 500:  return "Ouro", "🥇"
    if points < 800:  return "Platina", "💎"
    return "Diamante", "🔷"

def mention_list(ids: List[int]) -> str:
    return "\n".join(f"• <@{i}>" for i in ids) if ids else "—"

def pretty_team(guild: discord.Guild, team_ids: List[int]) -> str:
    lines = []
    for i in team_ids:
        m = guild.get_member(i)
        name = m.display_name if m else f"{i}"
        lines.append(f"• {name} (<@{i}>)")
    return "\n".join(lines) if lines else "—"

def rank_emoji_name(guild: discord.Guild, member: discord.Member, rank_number: int) -> str:
    # formato: "RANK X NomeDeUsuario"
    return f"RANK {rank_number} {member.name}"

def can_daily(last_iso: Optional[str], hours: int = DAILY_COOLDOWN_HOURS) -> Tuple[bool, int]:
    if not last_iso:
        return True, 0
    try:
        last = dt.datetime.fromisoformat(last_iso)
    except Exception:
        return True, 0
    now = dt.datetime.utcnow()
    diff = now - last
    if diff.total_seconds() >= hours * 3600:
        return True, 0
    restante = hours - int(diff.total_seconds() // 3600)
    return False, max(restante, 0)

def ch_id(kind: str) -> Optional[int]:
    return config.get("channels", {}).get(kind)

def ch_obj(guild: discord.Guild, kind: str) -> Optional[discord.TextChannel]:
    cid = ch_id(kind)
    return guild.get_channel(cid) if cid else None

async def send_in(guild: discord.Guild, kind: str, **send_kwargs):
    ch = ch_obj(guild, kind)
    if ch:
        return await ch.send(**send_kwargs)
    return None

def valid_team_size(n: Optional[int]) -> int:
    try:
        n = int(n or 4)
    except Exception:
        n = 4
    return 2 if n == 2 else (3 if n == 3 else 4)

# =========================
#   RANKING / APELIDOS
# =========================
async def refresh_leaderboard_and_nicks(ctx: commands.Context):
    ranking = sorted(players.items(), key=lambda kv: kv[1]["points"], reverse=True)

    # atualiza apelidos conforme ranking
    for i, (pid, pdata) in enumerate(ranking, start=1):
        member = ctx.guild.get_member(int(pid))
        if not member:
            continue
        try:
            await member.edit(nick=rank_emoji_name(ctx.guild, member, i))
        except Exception:
            pass

    # embed top 10
    embed = discord.Embed(
        title="🏆 Ranking Atual",
        color=discord.Color.gold(),
        timestamp=dt.datetime.utcnow()
    )
    desc = []
    for i, (pid, pdata) in enumerate(ranking[:10], start=1):
        m = ctx.guild.get_member(int(pid))
        name = m.display_name if m else f"Jogador {pid}"
        tname, temoji = tier_of(pdata["points"])
        desc.append(f"**{i}. {name}** — {pdata['points']} pts {temoji} `{tname}`")
    embed.description = "\n".join(desc) if desc else "Sem jogadores ainda."

    target = ch_obj(ctx.guild, "ranking") or ctx.channel
    await target.send(embed=embed)

# =========================
#        HISTÓRICO
# =========================
def record_match(guild_id: int, channel_id: int, data: dict) -> str:
    mid = f"M{len(matches)+1}"
    entry = {"id": mid, "guild": guild_id, "channel": channel_id, **data}
    matches.append(entry)
    save_json(MATCHES_FILE, matches)
    return mid

def award_streak_medals(pid: str, new_streak: int):
    for s, medal in STREAK_MEDALS.items():
        if new_streak == s and medal not in players[pid]["medals"]:
            players[pid]["medals"].append(medal)

# =========================
#         UI: FILA
# =========================
class QueueView(discord.ui.View):
    def __init__(self, ctx: commands.Context, owner_id: int, team_size: int):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.owner_id = owner_id
        self.players: List[int] = []
        self.ctx_message: Optional[discord.Message] = None
        self.team_size = valid_team_size(team_size)
        self.needed = self.team_size * 2

    def title(self) -> str:
        return f"🎮 Fila {self.team_size}v{self.team_size}"

    async def send(self):
        embed = discord.Embed(
            title=self.title(),
            description=f"Clique **Entrar** para participar. Objetivo: **{self.needed} jogadores**.",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Somente o criador pode fechar/iniciar.")
        self.ctx_message = await self.ctx.send(embed=embed, view=self)

    async def update_message(self, interaction: Optional[discord.Interaction] = None):
        joined = len(self.players)
        needed = self.needed
        embed = discord.Embed(
            title=self.title(),
            description=f"Entre para formar **{needed} jogadores**.\n\n**Na fila ({joined}/{needed}):**\n{mention_list(self.players)}",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Use os botões abaixo para entrar/sair. Apenas o criador pode fechar/iniciar.")
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.ctx_message.edit(embed=embed, view=self)

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.success, emoji="✅")
    async def btn_join(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id

        # Precisa estar em call para entrar
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "🎧 Para entrar na fila você precisa estar **em um canal de voz**.", ephemeral=True
            )

        if uid in self.players:
            return await interaction.response.send_message("⚠️ Você já está na fila!", ephemeral=True)
        if len(self.players) >= self.needed:
            return await interaction.response.send_message("⚠️ A fila já está cheia!", ephemeral=True)

        self.players.append(uid)
        await self.update_message(interaction)
        if len(self.players) == self.needed:
            await send_in(self.ctx.guild, "notificacoes", content=f"🎉 **Fila completa! ({self.team_size}v{self.team_size})** Iniciando sorteio de times…")
            await self.start_match()

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.secondary, emoji="🚪")
    async def btn_leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in self.players:
            return await interaction.response.send_message("⚠️ Você não está na fila.", ephemeral=True)
        self.players.remove(uid)
        await self.update_message(interaction)

    @discord.ui.button(label="Fechar", style=discord.ButtonStyle.danger, emoji="🔒")
    async def btn_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Apenas o criador pode fechar a fila.", ephemeral=True)
        self.stop()
        active_queues.pop(interaction.channel_id, None)
        await interaction.response.edit_message(content="🛑 **Fila fechada pelo criador.**", embed=None, view=None)

    @discord.ui.button(label="Iniciar", style=discord.ButtonStyle.primary, emoji="▶️")
    async def btn_start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Apenas o criador pode iniciar.", ephemeral=True)
        if len(self.players) < self.needed:
            return await interaction.response.send_message(f"⚠️ É preciso {self.needed} jogadores para iniciar.", ephemeral=True)
        await interaction.response.defer()
        await self.start_match()

    async def start_match(self):
        # fecha a fila
        self.stop()
        active_queues.pop(self.ctx.channel.id, None)

        # sorteio
        pool = self.players.copy()
        random.shuffle(pool)
        team_blue = pool[:self.team_size]
        team_red  = pool[self.team_size:self.team_size*2]
        cap_blue = random.choice(team_blue)
        cap_red  = random.choice(team_red)

        match = {
            "team_blue": team_blue,
            "team_red": team_red,
            "cap_blue": cap_blue,
            "cap_red": cap_red,
            "winner": None,
            "mvp": None,
            "used_items": {},           # pid -> {double, shield}
            "confirm_finish": set(),    # ids dos capitães que confirmaram
            "team_size": self.team_size
        }
        active_matches[self.ctx.channel.id] = match

        guild = self.ctx.guild
        base_text_channel = self.ctx.channel
        parent = base_text_channel.category  # cria embaixo da mesma categoria, se houver

        # cria canais de voz e texto
        team1_vc = await guild.create_voice_channel("TEAM 1", category=parent, reason="Partida - Team 1")
        team2_vc = await guild.create_voice_channel("TEAM 2", category=parent, reason="Partida - Team 2")
        vote_tc  = await guild.create_text_channel("votacao-partida", category=parent, reason="Votação dos Capitães")

        match["team1_vc_id"] = team1_vc.id
        match["team2_vc_id"] = team2_vc.id
        match["vote_tc_id"]  = vote_tc.id

        # mover jogadores (precisa Move Members)
        async def safe_move(uid, dest_vc):
            member = guild.get_member(uid)
            try:
                if member and member.voice and member.voice.channel:
                    await member.move_to(dest_vc, reason="Alocação de times")
            except Exception:
                pass

        for uid in team_blue:
            await safe_move(uid, team1_vc)
        for uid in team_red:
            await safe_move(uid, team2_vc)

        await vote_tc.send(
            f"🗳️ **Votação dos Capitães ({self.team_size}v{self.team_size})**\n"
            f"Capitão Azul: <@{cap_blue}>\n"
            f"Capitão Vermelho: <@{cap_red}>\n\n"
            "Use os botões do painel da partida para definir **Vencedor** e **MVP**.\n"
            "Este canal é para discussão entre capitães."
        )

        partida_ch = ch_obj(self.ctx.guild, "partida") or self.ctx.channel

        # painel de itens (todos)
        item_view = ItemUseView(self.ctx, match)
        item_embed = discord.Embed(
            title="🧰 Itens da Partida",
            description=(
                "Cada jogador pode **usar antes de finalizar**:\n"
                "• ✖2 **Dobro de Pontos** (dobra o **resultado** da partida – vitória ou derrota)\n"
                "• 🛡️ **Escudo** (se perder, **não** perde pontos)\n\n"
                "Clique nos botões abaixo para usar. Você só pode usar **uma vez por partida** cada item."
            ),
            color=discord.Color.teal()
        )
        item_embed.add_field(name="🔵 Time Azul", value=mention_list(team_blue), inline=True)
        item_embed.add_field(name="🔴 Time Vermelho", value=mention_list(team_red), inline=True)
        await partida_ch.send(embed=item_embed, view=item_view)

        # painel principal (capitães)
        panel = MatchPanelView(self.ctx, match)
        panel_embed = discord.Embed(title=f"⚔️ Partida {self.team_size}v{self.team_size} Formada", color=discord.Color.orange())
        panel_embed.add_field(name="🔵 Time Azul", value=pretty_team(self.ctx.guild, team_blue), inline=True)
        panel_embed.add_field(name="🔴 Time Vermelho", value=pretty_team(self.ctx.guild, team_red), inline=True)
        panel_embed.add_field(name="👑 Capitães", value=f"Azul: <@{cap_blue}>\nVermelho: <@{cap_red}>", inline=False)
        panel_embed.set_footer(text="Apenas os capitães definem Vencedor/MVP e Finalizam.")
        await partida_ch.send(embed=panel_embed, view=panel)

# =========================
#      UI: ITENS (VIEW)
# =========================
class ItemUseView(discord.ui.View):
    def __init__(self, ctx: commands.Context, match: dict):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.match = match

    @discord.ui.button(label="Usar ✖2 (Dobro)", style=discord.ButtonStyle.primary, emoji="✖️")
    async def btn_double(self, interaction: discord.Interaction, button: discord.ui.Button):
        pid = str(interaction.user.id)
        ensure_player(pid)
        inv = players[pid]["items"]
        if inv.get(ITEM_DOUBLE, 0) <= 0:
            return await interaction.response.send_message("❌ Você não possui **✖2 Dobro**.", ephemeral=True)
        used = self.match["used_items"].setdefault(pid, {"double": False, "shield": False})
        if used["double"]:
            return await interaction.response.send_message("⚠️ Você já usou **✖2** nesta partida.", ephemeral=True)
        used["double"] = True
        inv[ITEM_DOUBLE] -= 1
        save_json(PLAYERS_FILE, players)
        await interaction.response.send_message("✅ **✖2 Dobro** ativado para esta partida!", ephemeral=True)

    @discord.ui.button(label="Usar 🛡️ (Escudo)", style=discord.ButtonStyle.success, emoji="🛡️")
    async def btn_shield(self, interaction: discord.Interaction, button: discord.ui.Button):
        pid = str(interaction.user.id)
        ensure_player(pid)
        inv = players[pid]["items"]
        if inv.get(ITEM_SHIELD, 0) <= 0:
            return await interaction.response.send_message("❌ Você não possui **🛡️ Escudo**.", ephemeral=True)
        used = self.match["used_items"].setdefault(pid, {"double": False, "shield": False})
        if used["shield"]:
            return await interaction.response.send_message("⚠️ Você já usou **Escudo** nesta partida.", ephemeral=True)
        used["shield"] = True
        inv[ITEM_SHIELD] -= 1
        save_json(PLAYERS_FILE, players)
        await interaction.response.send_message("✅ **🛡️ Escudo** ativado para esta partida!", ephemeral=True)

# =========================
#   UI: PAINEL DA PARTIDA
# =========================
class MVPSelect(discord.ui.Select):
    def __init__(self, match: dict, guild: discord.Guild):
        options = []
        for uid in match["team_blue"] + match["team_red"]:
            m = guild.get_member(uid)
            label = m.display_name if m else str(uid)
            options.append(discord.SelectOption(label=label, value=str(uid)))
        super().__init__(placeholder="Escolher MVP…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        channel_id = interaction.channel_id
        match = active_matches.get(channel_id)
        if not match:
            return await interaction.response.send_message("❌ Nenhuma partida ativa aqui.", ephemeral=True)
        if interaction.user.id not in (match["cap_blue"], match["cap_red"]):
            return await interaction.response.send_message("❌ Apenas **capitães** podem definir MVP.", ephemeral=True)
        match["mvp"] = int(self.values[0])
        await interaction.response.send_message(f"⭐ MVP definido: <@{match['mvp']}>", ephemeral=False)

class MatchPanelView(discord.ui.View):
    def __init__(self, ctx: commands.Context, match: dict):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.match = match
        self.add_item(MVPSelect(match, ctx.guild))

    def is_captain(self, uid: int) -> bool:
        return uid in (self.match["cap_blue"], self.match["cap_red"])

    @discord.ui.button(label="Venceu AZUL", style=discord.ButtonStyle.primary, emoji="🔵")
    async def btn_win_blue(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_captain(interaction.user.id):
            return await interaction.response.send_message("❌ Apenas capitães podem definir o vencedor.", ephemeral=True)
        self.match["winner"] = "blue"
        await interaction.response.send_message("✅ **Vencedor: AZUL**", ephemeral=False)

    @discord.ui.button(label="Venceu VERMELHO", style=discord.ButtonStyle.danger, emoji="🔴")
    async def btn_win_red(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_captain(interaction.user.id):
            return await interaction.response.send_message("❌ Apenas capitães podem definir o vencedor.", ephemeral=True)
        self.match["winner"] = "red"
        await interaction.response.send_message("✅ **Vencedor: VERMELHO**", ephemeral=False)

    @discord.ui.button(label="Finalizar (Capitão)", style=discord.ButtonStyle.success, emoji="✅")
    async def btn_finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_captain(interaction.user.id):
            return await interaction.response.send_message("❌ Apenas capitães podem **finalizar**.", ephemeral=True)
        if self.match["winner"] not in ("blue", "red"):
            return await interaction.response.send_message("⚠️ Defina o **vencedor** primeiro.", ephemeral=True)
        if not self.match["mvp"]:
            return await interaction.response.send_message("⚠️ Defina o **MVP** primeiro.", ephemeral=True)

        self.match["confirm_finish"].add(interaction.user.id)
        remaining = {self.match["cap_blue"], self.match["cap_red"]} - self.match["confirm_finish"]
        if remaining:
            other = list(remaining)[0]
            return await interaction.response.send_message(
                f"📝 Confirmação registrada. Aguardando o outro capitão: <@{other}>",
                ephemeral=False
            )
        await self.close_and_score()

    async def close_and_score(self):
        ch_id = self.ctx.channel.id
        match = self.match
        blue = match["team_blue"]
        red = match["team_red"]
        winner = match["winner"]
        mvp = match["mvp"]
        used = match["used_items"]

        for uid in blue + red:
            ensure_player(str(uid))

        winners = blue if winner == "blue" else red
        losers  = red if winner == "blue" else blue

        delta_points: Dict[int, int] = {}

        def applied_delta_for(uid: int, base: int) -> int:
            pid = str(uid)
            flags = used.get(pid, {"double": False, "shield": False})
            delta = base
            # escudo anula perda
            if base < 0 and flags.get("shield"):
                delta = 0
            # ✖2 dobra o resultado
            if flags.get("double"):
                if base > 0:
                    delta = base * 2
                elif base < 0:
                    delta = 0 if flags.get("shield") else base * 2
            return delta

        # winners
        for uid in winners:
            pid = str(uid)
            d = applied_delta_for(uid, WIN_POINTS)
            players[pid]["points"] += d
            players[pid]["wins"] += 1
            players[pid]["streak"] += 1
            players[pid]["max_streak"] = max(players[pid]["max_streak"], players[pid]["streak"])
            award_streak_medals(pid, players[pid]["streak"])
            delta_points[uid] = d

        # losers
        for uid in losers:
            pid = str(uid)
            d = applied_delta_for(uid, LOSS_POINTS)
            players[pid]["points"] += d
            players[pid]["losses"] += 1
            players[pid]["streak"] = 0
            delta_points[uid] = d

        # MVP
        if mvp:
            pid = str(mvp)
            players[pid]["points"] += MVP_BONUS
            players[pid]["mvps"] += 1
            delta_points[mvp] = delta_points.get(mvp, 0) + MVP_BONUS

        # moedas por resultado
        for uid in winners:
            players[str(uid)]["coins"] = players[str(uid)].get("coins", 0) + COINS_WIN
        for uid in losers:
            players[str(uid)]["coins"] = players[str(uid)].get("coins", 0) + COINS_LOSS

        # histórico
        mid = record_match(
            guild_id=self.ctx.guild.id,
            channel_id=self.ctx.channel.id,
            data={
                "time": dt.datetime.utcnow().isoformat(),
                "team_blue": blue,
                "team_red": red,
                "cap_blue": match["cap_blue"],
                "cap_red": match["cap_red"],
                "winner": winner,
                "mvp": mvp,
                "used_items": used,
                "points_delta": {str(k): v for k, v in delta_points.items()},
                "team_size": match.get("team_size", 4),
            }
        )
        for uid in blue + red:
            players[str(uid)]["history"].append(mid)

        save_json(PLAYERS_FILE, players)

        # resumo visual
        def block(ids):
            lines = []
            for uid in ids:
                member = self.ctx.guild.get_member(uid)
                name = member.display_name if member else str(uid)
                delta = delta_points.get(uid, 0)
                sign = "➕" if delta > 0 else ("➖" if delta < 0 else "➖ 0")
                tname, temoji = tier_of(players[str(uid)]["points"])
                lines.append(f"• **{name}** — {sign} {delta} pts | total: **{players[str(uid)]['points']}** {temoji} `{tname}`")
            return "\n".join(lines) if lines else "—"

        winner_text = "🔵 **AZUL**" if winner == "blue" else "🔴 **VERMELHO**"
        size = match.get("team_size", 4)
        embed = discord.Embed(
            title=f"📑 Partida {size}v{size} {mid} finalizada",
            color=discord.Color.green(),
            timestamp=dt.datetime.utcnow()
        )
        embed.add_field(name="Resultado", value=f"Vencedor: {winner_text}\n⭐ MVP: <@{mvp}>" if mvp else f"Vencedor: {winner_text}\n⭐ MVP: —", inline=False)
        embed.add_field(name="🔵 Time Azul (deltas)", value=block(blue), inline=True)
        embed.add_field(name="🔴 Time Vermelho (deltas)", value=block(red), inline=True)

        used_lines = []
        for pid, flags in match["used_items"].items():
            if flags.get("double") or flags.get("shield"):
                u = self.ctx.guild.get_member(int(pid))
                name = u.display_name if u else pid
                flag_text = []
                if flags.get("double"): flag_text.append("✖2")
                if flags.get("shield"): flag_text.append("🛡️")
                used_lines.append(f"• {name}: {', '.join(flag_text)}")
        embed.add_field(name="Itens usados", value="\n".join(used_lines) if used_lines else "—", inline=False)

        await (ch_obj(self.ctx.guild, "partida") or self.ctx.channel).send(embed=embed)

        # log
        log_lines = [
            f"Match {mid} | Winner: {'AZUL' if winner=='blue' else 'VERMELHO'} | MVP: {mvp and self.ctx.guild.get_member(mvp).display_name}",
            f"Blue: {', '.join(str(u) for u in blue)}",
            f"Red:  {', '.join(str(u) for u in red)}",
            f"Delta: { {str(k): v for k, v in delta_points.items()} }",
            f"TeamSize: {size}"
        ]
        await send_in(self.ctx.guild, "logs", content="```\n" + "\n".join(log_lines) + "\n```")

        # apagar canais criados
        try:
            team1_vc = self.ctx.guild.get_channel(match.get("team1_vc_id"))
            team2_vc = self.ctx.guild.get_channel(match.get("team2_vc_id"))
            vote_tc  = self.ctx.guild.get_channel(match.get("vote_tc_id"))
            if team1_vc: await team1_vc.delete(reason=f"Fim da partida {mid}")
            if team2_vc: await team2_vc.delete(reason=f"Fim da partida {mid}")
            if vote_tc:  await vote_tc.delete(reason=f"Fim da partida {mid}")
        except Exception:
            pass

        # encerra
        active_matches.pop(self.ctx.channel.id, None)
        self.stop()
        await refresh_leaderboard_and_nicks(self.ctx)

# =========================
#          EVENTOS
# =========================
@bot.event
async def on_ready():
    print(f"🤖 Online como {bot.user} (discord.py {discord.__version__})")
    # sincroniza slash commands
    try:
        await bot.tree.sync()
        print("✅ Slash commands sincronizados.")
    except Exception as e:
        print(f"⚠️ Erro ao sync slash commands: {e}")

# =========================
#         COMANDOS
# =========================
# Prefix command: !fila [2|3|4]
@bot.command(name="fila")
async def create_queue(ctx: commands.Context, tamanho: Optional[int] = 4):
    """Cria uma fila 2v2 / 3v3 / 4v4 com botões (precisa estar em call para entrar)."""
    size = valid_team_size(tamanho)
    cfg_ch = ch_obj(ctx.guild, "fila")
    if cfg_ch and ctx.channel.id != cfg_ch.id:
        return await ctx.send(f"⚠️ Use o comando **neste canal**: {cfg_ch.mention}")

    if ctx.channel.id in active_queues:
        return await ctx.send("⚠️ Já existe uma fila ativa neste canal.")

    view = QueueView(ctx, owner_id=ctx.author.id, team_size=size)
    active_queues[ctx.channel.id] = {"owner": ctx.author.id, "view": view}

    target_ch = cfg_ch or ctx.channel
    view.ctx = await bot.get_context(await target_ch.send("🧩 Criando fila…"))
    await view.send()

    await send_in(ctx.guild, "notificacoes", content=f"🔔 **Fila criada! ({size}v{size})** Clique em **Entrar** para participar. 🕹️")         or await ctx.send(f"🔔 **Fila criada! ({size}v{size})** Clique em **Entrar** para participar. 🕹️")

# Slash command: /fila tamanho: 2|3|4
@bot.tree.command(name="fila", description="Cria uma fila 2v2 / 3v3 / 4v4 (precisa estar em call para entrar).")
@app_commands.describe(tamanho="Tamanho do time (2, 3 ou 4). Padrão: 4")
@app_commands.choices(tamanho=[
    app_commands.Choice(name="2v2", value=2),
    app_commands.Choice(name="3v3", value=3),
    app_commands.Choice(name="4v4", value=4),
])
async def slash_fila(interaction: discord.Interaction, tamanho: Optional[app_commands.Choice[int]] = None):
    size = valid_team_size(tamanho.value if tamanho else 4)

    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message("❌ Use este comando dentro de um servidor.", ephemeral=True)

    channel = interaction.channel
    cfg_ch = ch_obj(guild, "fila")
    if cfg_ch and channel.id != cfg_ch.id:
        return await interaction.response.send_message(f"⚠️ Use o comando **neste canal**: {cfg_ch.mention}", ephemeral=True)

    if channel.id in active_queues:
        return await interaction.response.send_message("⚠️ Já existe uma fila ativa neste canal.", ephemeral=True)

    await interaction.response.defer(ephemeral=False, thinking=False)
    # Criar contexto manualmente para reutilizar a mesma View/fluxo
    ctx = await bot.get_context(await channel.send("🧩 Criando fila…"))
    view = QueueView(ctx, owner_id=interaction.user.id, team_size=size)
    active_queues[channel.id] = {"owner": interaction.user.id, "view": view}
    await view.send()

    await send_in(guild, "notificacoes", content=f"🔔 **Fila criada! ({size}v{size})** Clique em **Entrar** para participar. 🕹️")         or await channel.send(f"🔔 **Fila criada! ({size}v{size})** Clique em **Entrar** para participar. 🕹️")

@bot.command(name="perfil")
async def cmd_perfil(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    pid = str(member.id)
    ensure_player(pid)
    p = players[pid]
    tname, temoji = tier_of(p["points"])
    embed = discord.Embed(title=f"📊 Perfil de {member.display_name}", color=discord.Color.blue())
    embed.add_field(name="Pontos / Tier", value=f"**{p['points']}** {temoji} `{tname}`", inline=True)
    embed.add_field(name="Vitórias / Derrotas", value=f"**{p['wins']}** / **{p['losses']}**", inline=True)
    embed.add_field(name="MVPs", value=str(p["mvps"]), inline=True)
    embed.add_field(name="Streak (máx.)", value=f"{p['streak']} (**máx:** {p['max_streak']})", inline=True)
    embed.add_field(name="Moedas", value=str(p.get("coins", 0)), inline=True)
    medals = ", ".join(p["medals"]) if p["medals"] else "—"
    embed.add_field(name="Medalhas", value=medals, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="inventario", aliases=["inv"])
async def cmd_inventory(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    pid = str(member.id)
    ensure_player(pid)
    inv = players[pid]["items"]
    embed = discord.Embed(title=f"🧰 Inventário de {member.display_name}", color=discord.Color.teal())
    embed.add_field(name="✖2 Dobro", value=str(inv.get(ITEM_DOUBLE, 0)), inline=True)
    embed.add_field(name="🛡️ Escudo", value=str(inv.get(ITEM_SHIELD, 0)), inline=True)
    await ctx.send(embed=embed)

@bot.command(name="top")
async def cmd_top(ctx: commands.Context):
    await refresh_leaderboard_and_nicks(ctx)

# ---- TOPs por estatística ----
def _format_top_list(pairs, guild, key_label):
    lines = []
    for i, (pid, pdata) in enumerate(pairs, start=1):
        m = guild.get_member(int(pid))
        name = m.display_name if m else f"Jogador {pid}"
        lines.append(f"**{i}.** {name} — **{pdata[key_label]}**")
    return "\n".join(lines) if lines else "—"

@bot.command(name="topvitorias")
async def cmd_top_vitorias(ctx: commands.Context):
    ranking = sorted(players.items(), key=lambda kv: kv[1].get("wins", 0), reverse=True)[:10]
    desc = _format_top_list(ranking, ctx.guild, "wins")
    await ctx.send(embed=discord.Embed(title="🏆 Top Vitórias", description=desc, color=discord.Color.gold()))

@bot.command(name="topderrotas")
async def cmd_top_derrotas(ctx: commands.Context):
    ranking = sorted(players.items(), key=lambda kv: kv[1].get("losses", 0), reverse=True)[:10]
    desc = _format_top_list(ranking, ctx.guild, "losses")
    await ctx.send(embed=discord.Embed(title="💀 Top Derrotas", description=desc, color=discord.Color.red()))

@bot.command(name="topstreak")
async def cmd_top_streak(ctx: commands.Context):
    ranking = sorted(players.items(), key=lambda kv: kv[1].get("max_streak", 0), reverse=True)[:10]
    lines = []
    for i, (pid, pdata) in enumerate(ranking, start=1):
        m = ctx.guild.get_member(int(pid))
        name = m.display_name if m else f"Jogador {pid}"
        lines.append(f"**{i}.** {name} — **{pdata.get('max_streak',0)}** (máx)")
    desc = "\n".join(lines) if lines else "—"
    await ctx.send(embed=discord.Embed(title="🔥 Top Streak Máxima", description=desc, color=discord.Color.orange()))

# ---- Histórico ----
@bot.command(name="historico")
async def cmd_history(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    pid = str(member.id)
    ensure_player(pid)
    hist_ids = players[pid]["history"][-5:]
    if not hist_ids:
        return await ctx.send("📭 Sem histórico ainda.")

    embed = discord.Embed(title=f"🗂️ Últimas partidas de {member.display_name}", color=discord.Color.purple())
    for mid in reversed(hist_ids):
        m = next((x for x in matches if x["id"] == mid), None)
        if not m:
            continue
        when = m.get("time", "")[:19].replace("T", " ")
        winner = "AZUL" if m["winner"] == "blue" else "VERMELHO"
        delta_me = m.get("points_delta", {}).get(str(member.id), 0)
        size = m.get("team_size", 4)
        embed.add_field(
            name=f"{mid} • {when} • {size}v{size}",
            value=f"Vencedor: **{winner}** | MVP: <@{m.get('mvp')}> | Seu delta: **{delta_me}**",
            inline=False
        )
    await ctx.send(embed=embed)

# ---- Ajuda ----
@bot.command(name="ajuda")
async def cmd_help(ctx: commands.Context):
    embed = discord.Embed(
        title="📖 Ajuda — Bot 2v2/3v3/4v4",
        description=(
            f"**{PREFIX}fila [2|3|4]** — cria uma fila (precisa estar em call)\n"
            f"**/fila** — mesma coisa, com opção de tamanho\n"
            f"**{PREFIX}perfil [@user]** — mostra perfil\n"
            f"**{PREFIX}inventario** — mostra itens\n"
            f"**{PREFIX}top** — ranking geral + atualiza apelidos (RANK X Nome)\n"
            f"**{PREFIX}topvitorias** / **{PREFIX}topderrotas** / **{PREFIX}topstreak**\n"
            f"**{PREFIX}historico [@user]** — últimas partidas\n\n"
            f"**{PREFIX}daily** — resgate diário (1/2/5/10 coins ou 1x item)\n"
            f"**{PREFIX}saldo** — suas coins\n"
            f"**{PREFIX}loja** — ver itens e preços\n"
            f"**{PREFIX}comprar [double|shield] [qtd]** — compra item\n"
            f"**{PREFIX}vender [double|shield] [qtd]** — vende item\n\n"
            "Admin:\n"
            f"**{PREFIX}setcanal** fila/partida/ranking/notificacoes/logs #canal\n"
            f"**{PREFIX}canais** — mostra configuração de canais\n"
        ),
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

# ---- ADMIN: canais ----
@bot.command(name="setcanal")
@commands.has_permissions(administrator=True)
async def cmd_setcanal(ctx: commands.Context, tipo: str, canal: Optional[discord.TextChannel]):
    tipo = tipo.lower()
    valid = {"fila", "partida", "ranking", "notificacoes", "logs"}
    if tipo not in valid:
        return await ctx.send("Tipos válidos: `fila`, `partida`, `ranking`, `notificacoes`, `logs`.")
    if not canal:
        return await ctx.send("Marque um canal. Ex.: `!setcanal fila #fila-jogos`")
    config["channels"][tipo] = canal.id
    save_json(CONFIG_FILE, config)
    await ctx.send(f"✅ Canal de **{tipo}** definido para {canal.mention}")

@bot.command(name="canais")
@commands.has_permissions(administrator=True)
async def cmd_canais(ctx: commands.Context):
    chs = config.get("channels", {})
    def fmt(kind):
        cid = chs.get(kind)
        return f"<#{cid}>" if cid else "`não configurado`"
    embed = discord.Embed(title="🔧 Canais Configurados", color=discord.Color.orange())
    embed.add_field(name="Fila", value=fmt("fila"))
    embed.add_field(name="Partida", value=fmt("partida"))
    embed.add_field(name="Ranking", value=fmt("ranking"))
    embed.add_field(name="Notificações", value=fmt("notificacoes"))
    embed.add_field(name="Logs", value=fmt("logs"))
    await ctx.send(embed=embed)

# ---- Loja / Economia ----
@bot.command(name="saldo")
async def cmd_saldo(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    pid = str(member.id)
    ensure_player(pid)
    coins = players[pid].get("coins", 0)
    await ctx.send(f"💰 **{member.display_name}** tem **{coins}** coins.")

@bot.command(name="loja")
async def cmd_loja(ctx):
    linhas = []
    for key, preco in ITEM_PRICE.items():
        nome = "🛡️ Escudo" if key == ITEM_SHIELD else "✖2 Dobro"
        linhas.append(f"• **{nome}** (`{key}`) — **{preco}** coins (comprar/vender)")
    await ctx.send(embed=discord.Embed(title="🛒 Loja", description="\n".join(linhas)))

@bot.command(name="comprar")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_comprar(ctx, item: str, qtd: int = 1):
    item = item.lower()
    if item not in ITEM_PRICE:
        return await ctx.send("❌ Item inválido. Use `!loja` para ver os itens.")
    if qtd < 1 or qtd > 50:
        return await ctx.send("⚠️ Quantidade inválida (1–50).")

    pid = str(ctx.author.id)
    ensure_player(pid)
    custo = ITEM_PRICE[item] * qtd
    if players[pid].get("coins", 0) < custo:
        return await ctx.send(f"💸 Coins insuficientes. Precisa de **{custo}**.")

    players[pid]["coins"] -= custo
    inv = players[pid]["items"]
    inv[item] = inv.get(item, 0) + qtd
    save_json(PLAYERS_FILE, players)
    nome = "🛡️ Escudo" if item == ITEM_SHIELD else "✖2 Dobro"
    await ctx.send(f"✅ Comprou **{qtd}x {nome}** por **{custo}** coins.")

@bot.command(name="vender")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_vender(ctx, item: str, qtd: int = 1):
    item = item.lower()
    if item not in ITEM_PRICE:
        return await ctx.send("❌ Item inválido. Use `!loja` para ver os itens.")
    if qtd < 1 or qtd > 50:
        return await ctx.send("⚠️ Quantidade inválida (1–50).")

    pid = str(ctx.author.id)
    ensure_player(pid)
    inv = players[pid]["items"]
    if inv.get(item, 0) < qtd:
        return await ctx.send("⚠️ Você não tem itens suficientes pra vender.")

    ganho = ITEM_PRICE[item] * qtd
    inv[item] -= qtd
    players[pid]["coins"] = players[pid].get("coins", 0) + ganho
    save_json(PLAYERS_FILE, players)
    nome = "🛡️ Escudo" if item == ITEM_SHIELD else "✖2 Dobro"
    await ctx.send(f"💱 Vendeu **{qtd}x {nome}** e recebeu **{ganho}** coins.")

# ---- Daily ----
@bot.command(name="daily")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_daily(ctx):
    pid = str(ctx.author.id)
    ensure_player(pid)
    ok, hrs = can_daily(players[pid].get("last_daily"))
    if not ok:
        return await ctx.send(f"⏳ Você já pegou seu daily. Tente novamente em ~**{hrs}h**.")

    reward = random.choice(DAILY_REWARDS)
    if reward[0] == "coins":
        amount = int(reward[1])
        players[pid]["coins"] = players[pid].get("coins", 0) + amount
        text = f"🎁 Você recebeu **{amount}** coin(s) no daily!"
    else:
        item = reward[1]
        players[pid]["items"][item] = players[pid]["items"].get(item, 0) + 1
        pretty = "🛡️ Escudo" if item == ITEM_SHIELD else "✖2 Dobro"
        text = f"🎁 Você recebeu **1x {pretty}** no daily!"

    players[pid]["last_daily"] = dt.datetime.utcnow().isoformat()
    save_json(PLAYERS_FILE, players)
    await ctx.send(text)

# =========================
#          RUN
# =========================
if __name__ == "__main__":
    if TOKEN == "COLE_SEU_TOKEN_AQUI":
        print("⚠️ ATENÇÃO: Defina a variável de ambiente DISCORD_TOKEN ou substitua TOKEN no topo do arquivo.")
    bot.run(TOKEN)
