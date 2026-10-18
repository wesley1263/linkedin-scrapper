"""Limite de ritmo por conta (ADR-0005): intervalo mínimo entre perfis e teto diário, com estado em arquivo. Só stdlib."""
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone

log = logging.getLogger("scraper.ratelimit")

DEFAULT_STATE_FILE = "./output/.ratelimit.json"


def _utc_day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def _seconds_to_next_utc_midnight(ts):
    return 86400 - (ts % 86400)


class AccountLimiter:
    """`min_interval` segundos entre perfis e `max_per_day` por dia UTC, por conta; 0 desliga cada limite.

    O estado fica em `state_path` (sobrevive a reinício); arquivo ausente ou corrompido vale como estado vazio.
    Pensado para um único coletor por conta (ADR-0005: uma sessão, um coletor por vez), sem lock entre processos.
    """

    def __init__(self, state_path, min_interval=30, max_per_day=100, clock=None):
        self.state_path = state_path
        self.min_interval = min_interval
        self.max_per_day = max_per_day
        self.clock = clock or time.time

    @classmethod
    def from_env(cls, env, clock=None):
        def number(name, default):
            raw = env.get(name)
            if raw in (None, ""):
                return default
            try:
                value = int(raw)
            except ValueError:
                raise ValueError(f"{name} deve ser um inteiro, recebeu {raw!r}") from None
            if value < 0:
                raise ValueError(f"{name} não pode ser negativo")
            return value

        return cls(env.get("RATE_STATE_FILE") or DEFAULT_STATE_FILE,
                   min_interval=number("MIN_SECONDS_BETWEEN_PROFILES", 30),
                   max_per_day=number("MAX_PROFILES_PER_DAY", 100), clock=clock)

    def _load(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                data = json.load(f)
            accounts = data["accounts"]
            if isinstance(accounts, dict):
                return accounts
        except FileNotFoundError:
            pass
        except (ValueError, KeyError, TypeError, OSError):
            log.warning("Estado de ritmo ilegível em %s: recomeçando do zero", self.state_path)
        return {}

    def _save(self, accounts):
        directory = os.path.dirname(os.path.abspath(self.state_path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"accounts": accounts}, f)
            os.replace(tmp, self.state_path)  # troca atômica: nunca fica meio escrito
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def check(self, account):
        """Segundos até a conta poder coletar outro perfil (0 = liberado)."""
        state = self._load().get(account)
        if not state:
            return 0
        now = self.clock()
        wait = max(0.0, state["last_start"] + self.min_interval - now) if self.min_interval else 0.0
        if self.max_per_day and state.get("day") == _utc_day(now) and state.get("count", 0) >= self.max_per_day:
            wait = max(wait, _seconds_to_next_utc_midnight(now))
        return wait

    def record_start(self, account):
        """Registra o início de uma coleta (conta mesmo as que falham: o ritmo é o que o LinkedIn enxerga)."""
        accounts = self._load()
        now = self.clock()
        today = _utc_day(now)
        state = accounts.get(account) or {}
        count = state.get("count", 0) if state.get("day") == today else 0
        accounts[account] = {"last_start": now, "day": today, "count": count + 1}
        self._save(accounts)
