"""Ferramentas para analisar oportunidades no mercado de jogadores.

Este módulo foi projetado para ser executado continuamente. Ele lê um
arquivo JSON com o histórico de preços e métricas de liquidez/demanda dos
jogadores e sugere quais atletas comprar ou vender com base em um conjunto
simples de indicadores heurísticos.

O formato esperado do arquivo JSON é:

```
{
  "players": [
    {
      "name": "Jogador X",
      "team": "Time Azul",
      "position": "ADC",
      "prices": [102.5, 105.0, 103.0, 108.0, 110.0],
      "demand_index": 0.65,
      "supply_index": 0.30
    },
    ...
  ]
}
```

O arquivo `market_data.sample.json` pode ser usado como referência.

Para executar apenas uma análise:

```
python ranking_bot/market_analyzer.py --once
```

Para executar continuamente (intervalo padrão de 60s):

```
python ranking_bot/market_analyzer.py --data market_data.json --interval 120
```
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from statistics import mean
from typing import Dict, Iterable, List, Optional, Tuple

LOGGER = logging.getLogger("ranking_bot.market_analyzer")


@dataclass
class PlayerSnapshot:
    """Representa o estado do jogador em um instante."""

    name: str
    team: Optional[str]
    position: Optional[str]
    prices: List[float]
    demand_index: float
    supply_index: float

    @property
    def last_price(self) -> float:
        return self.prices[-1]

    @property
    def previous_price(self) -> float:
        return self.prices[-2] if len(self.prices) >= 2 else self.prices[-1]

    def moving_average(self, window: int) -> float:
        window = max(1, min(window, len(self.prices)))
        return mean(self.prices[-window:])

    def price_variation(self) -> float:
        if len(self.prices) < 2:
            return 0.0
        return self.last_price - self.previous_price

    def price_momentum(self) -> float:
        if len(self.prices) < 3:
            return self.price_variation()
        recent_avg = mean(self.prices[-3:])
        older_avg = mean(self.prices[-6:-3]) if len(self.prices) >= 6 else mean(self.prices[:-3])
        return recent_avg - older_avg


@dataclass
class Recommendation:
    """Sugestão de compra ou venda."""

    player: PlayerSnapshot
    action: str  # "buy" ou "sell"
    score: float
    summary: str

    def to_console(self) -> str:
        badge = "🟢" if self.action == "buy" else "🔴"
        header = f"{badge} {self.player.name} ({self.player.position or '?'} - {self.player.team or '?'})"
        return f"{header}: {self.summary} | score={self.score:.2f}"


def load_market_data(path: str) -> List[PlayerSnapshot]:
    """Carrega dados do mercado a partir de um arquivo JSON."""

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Arquivo de dados '{path}' não encontrado. Crie-o ou copie o exemplo 'market_data.sample.json'."
        )

    with open(path, "r", encoding="utf-8") as handler:
        payload = json.load(handler)

    players_raw = payload.get("players", [])
    players: List[PlayerSnapshot] = []
    for raw in players_raw:
        try:
            prices = [float(value) for value in raw["prices"] if value is not None]
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.warning("Ignorando jogador por dados de preço inválidos: %s", exc)
            continue

        if len(prices) == 0:
            LOGGER.warning("Ignorando jogador '%s' por não possuir histórico de preços.", raw.get("name", "?"))
            continue

        player = PlayerSnapshot(
            name=str(raw.get("name", "Desconhecido")),
            team=raw.get("team"),
            position=raw.get("position"),
            prices=prices,
            demand_index=float(raw.get("demand_index", 0.5)),
            supply_index=float(raw.get("supply_index", 0.5)),
        )
        players.append(player)

    return players


def _score_buy(player: PlayerSnapshot) -> Tuple[float, str]:
    """Calcula pontuação de compra e descrição resumida."""

    last = player.last_price
    sma_short = player.moving_average(3)
    sma_long = player.moving_average(7)

    discount_vs_long = (sma_long - last) / sma_long if sma_long else 0.0
    momentum = player.price_momentum()
    demand_boost = player.demand_index - player.supply_index

    score = max(discount_vs_long, 0.0) * 5 + max(momentum, 0.0) * 0.5 + demand_boost
    summary = (
        f"preço atual {last:.2f}, SMA3 {sma_short:.2f}, SMA7 {sma_long:.2f}, "
        f"desconto {discount_vs_long*100:.1f}%, momentum {momentum:.2f}"
    )
    return score, summary


def _score_sell(player: PlayerSnapshot) -> Tuple[float, str]:
    last = player.last_price
    sma_short = player.moving_average(3)
    sma_long = player.moving_average(7)

    premium_vs_short = (last - sma_short) / sma_short if sma_short else 0.0
    drop_risk = -player.price_momentum()
    oversupply = player.supply_index - player.demand_index

    score = max(premium_vs_short, 0.0) * 5 + max(drop_risk, 0.0) * 0.5 + oversupply
    summary = (
        f"preço atual {last:.2f}, SMA3 {sma_short:.2f}, SMA7 {sma_long:.2f}, "
        f"prêmio {premium_vs_short*100:.1f}%, momentum {drop_risk*-1:.2f}"
    )
    return score, summary


def build_recommendations(players: Iterable[PlayerSnapshot], top_n: int = 3) -> List[Recommendation]:
    """Gera listas de recomendações de compra e venda."""

    buy_rec: List[Recommendation] = []
    sell_rec: List[Recommendation] = []

    for player in players:
        buy_score, buy_summary = _score_buy(player)
        if buy_score > 0:
            buy_rec.append(Recommendation(player, "buy", buy_score, buy_summary))

        sell_score, sell_summary = _score_sell(player)
        if sell_score > 0:
            sell_rec.append(Recommendation(player, "sell", sell_score, sell_summary))

    ranked = sorted(buy_rec, key=lambda rec: rec.score, reverse=True)[:top_n]
    ranked += sorted(sell_rec, key=lambda rec: rec.score, reverse=True)[:top_n]
    return ranked


def display_report(recommendations: List[Recommendation]) -> None:
    if not recommendations:
        print("Nenhuma oportunidade detectada no momento.")
        return

    print("\n=== Sugestões de mercado ===")
    for rec in recommendations:
        print(rec.to_console())
    print("===========================\n")


def run_loop(data_path: str, interval: int, top_n: int) -> None:
    def _handle_signal(signum, _frame):
        raise KeyboardInterrupt

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handle_signal)

    LOGGER.info("Iniciando monitoramento contínuo. Intervalo: %ss", interval)
    try:
        while True:
            players = load_market_data(data_path)
            recommendations = build_recommendations(players, top_n=top_n)
            display_report(recommendations)
            time.sleep(interval)
    except KeyboardInterrupt:
        LOGGER.info("Encerrando monitoramento a pedido do usuário.")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analisador contínuo de mercado de jogadores.")
    parser.add_argument(
        "--data",
        default="market_data.json",
        help="Arquivo JSON com os dados de mercado (padrão: market_data.json)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Intervalo em segundos entre cada análise (padrão: 60)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=3,
        help="Quantidade de recomendações de compra e venda a exibir (padrão: 3)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executa apenas uma análise e encerra.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Define o nível de log para stdout.",
    )
    return parser.parse_args(argv)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    try:
        players = load_market_data(args.data)
    except FileNotFoundError as exc:
        LOGGER.error(str(exc))
        return 1
    except json.JSONDecodeError as exc:
        LOGGER.error("Falha ao interpretar o arquivo de dados: %s", exc)
        return 1

    recommendations = build_recommendations(players, top_n=args.top)
    display_report(recommendations)

    if args.once:
        return 0

    run_loop(args.data, interval=args.interval, top_n=args.top)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
