import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from dotenv import load_dotenv


from colorama import Fore, Style, init
init(autoreset=True)


load_dotenv()

RANKINGS_URL = os.getenv("RANKINGS_URL", "https://ninjasaga.cc/data/clan_rankings.json").strip()
TOP_N = int(os.getenv("TOP_N", "10"))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "60"))
MIN_DELTA = int(os.getenv("MIN_DELTA", "1"))
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "").strip()

SNAPSHOT_PATH = Path("snapshot_clanes.json")


@dataclass
class ClanRow:
    rank: int
    name: str
    rep: int


def load_snapshot() -> Dict[str, int]:
    """Base: {clan_name: rep}"""
    if not SNAPSHOT_PATH.exists():
        return {}
    try:
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_snapshot(rows: List[ClanRow]) -> None:
    """Guarda SIEMPRE el último estado y pisa el anterior."""
    data = {r.name: r.rep for r in rows}
    SNAPSHOT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def notify_ntfy(message: str) -> None:
    if not NTFY_TOPIC:
        print("⚠️ NTFY_TOPIC vacío: no envío notificación.")
        return
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=message.encode("utf-8"), timeout=15)
    except Exception as e:
        print(f"⚠️ Error enviando ntfy: {e}")


def fetch_top_clans() -> List[ClanRow]:
    params = {"t": str(int(time.time() * 1000))}
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(RANKINGS_URL, params=params, headers=headers, timeout=30)
    r.raise_for_status()

    data = r.json()
    clans = data.get("clans", [])
    if not isinstance(clans, list) or not clans:
        raise RuntimeError("JSON sin 'clans' o vacío.")

    rows: List[ClanRow] = []
    for c in clans:
        try:
            rank = int(c.get("rank"))
            name = str(c.get("name", "")).strip()
            rep = int(c.get("reputation"))
        except Exception:
            continue

        if name:
            rows.append(ClanRow(rank=rank, name=name, rep=rep))

    rows.sort(key=lambda x: x.rank)
    return rows[:TOP_N]


def build_message(attacking: List[Tuple[int, str, int]]) -> str:
    lines = ["Clanes atacando:"]
    for rank, name, delta in attacking:
        lines.append(f"{rank}) {name} (+{delta})")
    return "\n".join(lines)


def run_once() -> None:
    old = load_snapshot()
    current = fetch_top_clans()
    
    print(Fore.CYAN + "\n===== TOP 10 CLANES =====")

    for r in current:
        print(Fore.CYAN + f"{r.rank}) {r.name}  |  REP: {r.rep}")

    print(Fore.CYAN + "========================\n")

    attacking: List[Tuple[int, str, int]] = []
    for r in current:
        old_rep = old.get(r.name)
        if old_rep is not None:
            delta = r.rep - int(old_rep)
            if delta >= MIN_DELTA:
                attacking.append((r.rank, r.name, delta))

    save_snapshot(current)

    if attacking:
        attacking.sort(key=lambda x: x[0])
        msg = build_message(attacking)
        print("🚨", msg.replace("\n", " | "))
        notify_ntfy(msg)
    else:
        print("✅ Sin cambios")


def main() -> None:
    print(f"🔗 JSON: {RANKINGS_URL}")
    print(f"⏱️ Intervalo: {POLL_SECONDS}s | TOP_N={TOP_N} | MIN_DELTA={MIN_DELTA}")

    notify_ntfy("TEST: Railway envía ntfy ✅")

    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            print("🛑 Bot detenido")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
