"""Minimal async clients for ebusd's TCP command port and HTTP/JSON port.

Home Assistant independent, so it can be unit-tested on its own.

TCP (default 8888): one command per line; ebusd answers with one or more
lines followed by an empty line. Used for:
  read -m <maxage> -c <circuit> <name>   (cached if fresh, else from the bus)
  read -f -c <circuit> <name>            (force a bus read; used to verify writes)
  write -c <circuit> <name> <value>      (only via the coordinator's guarded writer)
  info / state

HTTP (default 8889): GET /data/<circuit> returns ebusd's cache as JSON.
Used to collect passively-refreshed values and the "global" status block
without touching the bus.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - Version bump only; no functional change.
  0.2.1 (2026-10-28) - Version bump only; no functional change.
  0.2.2 (2026-10-28) - Version bump only; no functional change.
  0.3.0 (2026-10-28) - Version bump only; no functional change.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.\-]+$")


class EbusdError(Exception):
    """Base error."""


class EbusdConnectionError(EbusdError):
    """ebusd could not be reached."""


class EbusdNoSignal(EbusdError):
    """ebusd is running but has no eBUS signal."""


class EbusdCommandError(EbusdError):
    """ebusd answered a single command with ERR: ..."""


def parse_value_token(token: str) -> Any:
    """Convert one ebusd value token to float, str or None."""
    tok = token.strip()
    if tok in ("", "-", "null"):
        return None
    try:
        return float(tok)
    except ValueError:
        return tok


def parse_read_response(line: str) -> list[Any]:
    """Parse the (non-verbose) answer to a read command: 'v1;v2;...'."""
    if line.startswith("ERR:"):
        if "no signal" in line:
            raise EbusdNoSignal(line)
        raise EbusdCommandError(line)
    return [parse_value_token(tok) for tok in line.split(";")]


def parse_info(lines: list[str]) -> dict[str, Any]:
    """Parse the answer to 'info' into a dict."""
    out: dict[str, Any] = {"devices": {}}
    addr_re = re.compile(r'^address ([0-9a-f]{2}): (.*)$')
    scan_re = re.compile(r'scanned "([^"]*)"')
    for raw in lines:
        line = raw.lstrip("﻿").strip()
        if not line:
            continue
        if m := addr_re.match(line):
            entry: dict[str, Any] = {"desc": m.group(2)}
            if s := scan_re.search(m.group(2)):
                entry.update(
                    dict(p.split("=", 1) for p in s.group(1).split(";") if "=" in p)
                )
            out["devices"][m.group(1)] = entry
            continue
        if ": " in line:
            key, val = line.split(": ", 1)
            out[key.strip()] = val.strip()
    return out


def parse_state(line: str) -> dict[str, Any]:
    """Parse the answer to 'state', e.g. 'signal acquired, 52 symbols/sec (147 max), 5 masters'."""
    line = line.lstrip("﻿").strip()
    out: dict[str, Any] = {"signal": line.startswith("signal acquired")}
    if m := re.search(r"(\d+) symbols/sec \((\d+) max\)", line):
        out["symbolrate"] = int(m.group(1))
        out["maxsymbolrate"] = int(m.group(2))
    if m := re.search(r"(\d+) masters", line):
        out["masters"] = int(m.group(1))
    return out


def format_write_value(value: Any) -> str:
    """Format a value for an ebusd write command."""
    if isinstance(value, bool):
        raise ValueError("boolean values are not supported")
    if isinstance(value, (int, float)):
        text = f"{float(value):.2f}".rstrip("0").rstrip(".")
        return text if text not in ("", "-0") else "0"
    text = str(value)
    if not _SAFE_TOKEN.match(text):
        raise ValueError(f"unsafe value {text!r}")
    return text


def _check_name(*parts: str) -> None:
    for part in parts:
        if not _SAFE_TOKEN.match(part):
            raise ValueError(f"unsafe name {part!r}")


class EbusdTcpClient:
    """Async client for ebusd's TCP command port (one persistent connection)."""

    def __init__(self, host: str, port: int, timeout: float = 10.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    async def _connect(self) -> None:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.timeout
            )
        except (OSError, TimeoutError) as err:
            raise EbusdConnectionError(
                f"cannot connect to ebusd at {self.host}:{self.port}: {err}"
            ) from err

    async def close(self) -> None:
        """Close the connection."""
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (OSError, ConnectionError):
                pass
        self._reader = self._writer = None

    async def command(self, cmd: str, retry: bool = True) -> list[str]:
        """Send one command and return the answer lines (without the blank terminator).

        A failed command is retried once on a fresh connection, except when
        retry=False (used for writes, which must never be sent twice).
        """
        if "\n" in cmd or "\r" in cmd:
            raise ValueError("newline in command")
        attempts = (1, 2) if retry else (2,)
        async with self._lock:
            for attempt in attempts:
                if self._writer is None:
                    await self._connect()
                assert self._reader is not None and self._writer is not None
                try:
                    self._writer.write(f"{cmd}\n".encode())
                    await self._writer.drain()
                    lines: list[str] = []
                    while True:
                        raw = await asyncio.wait_for(
                            self._reader.readline(), self.timeout
                        )
                        if not raw:
                            raise ConnectionResetError("connection closed by ebusd")
                        line = raw.decode("utf-8", "replace").rstrip("\r\n")
                        if line == "":
                            return lines
                        lines.append(line)
                except (OSError, TimeoutError, ConnectionError) as err:
                    await self.close()
                    if attempt == 2:
                        raise EbusdConnectionError(
                            f"ebusd at {self.host}:{self.port} did not answer "
                            f"'{cmd.split(' ')[0]}': {err}"
                        ) from err
        raise EbusdConnectionError("unreachable")  # pragma: no cover

    async def read(
        self,
        circuit: str,
        name: str,
        maxage: int | None = None,
        force: bool = False,
    ) -> list[Any]:
        """Read one message. Returns its non-ignored field values in order."""
        _check_name(circuit, name)
        opt = "-f " if force else (f"-m {int(maxage)} " if maxage is not None else "")
        lines = await self.command(f"read {opt}-c {circuit} {name}")
        if not lines:
            raise EbusdCommandError("ERR: empty answer")
        return parse_read_response(lines[0])

    async def write(self, circuit: str, name: str, value: Any) -> str:
        """Write one message. Only called by the coordinator's guarded writer."""
        _check_name(circuit, name)
        text = format_write_value(value)
        lines = await self.command(f"write -c {circuit} {name} {text}", retry=False)
        answer = lines[0] if lines else ""
        if answer.startswith("ERR:"):
            if "no signal" in answer:
                raise EbusdNoSignal(answer)
            raise EbusdCommandError(answer)
        return answer

    async def info(self) -> dict[str, Any]:
        """Return parsed 'info'."""
        return parse_info(await self.command("info"))

    async def state(self) -> dict[str, Any]:
        """Return parsed 'state'."""
        lines = await self.command("state")
        return parse_state(lines[0] if lines else "")


def parse_http_circuit(payload: dict[str, Any], circuit: str) -> dict[str, dict[str, Any]]:
    """Turn ebusd's /data JSON for one circuit into {name: {values, lastup}}."""
    out: dict[str, dict[str, Any]] = {}
    block = payload.get(circuit)
    if not isinstance(block, dict):
        return out
    messages = block.get("messages")
    if not isinstance(messages, dict):
        return out
    for name, msg in messages.items():
        if not isinstance(msg, dict):
            continue
        fields = msg.get("fields")
        if not isinstance(fields, dict) or not fields:
            continue
        values = [
            (f.get("value") if isinstance(f, dict) else None) for f in fields.values()
        ]
        out[name] = {"values": values, "lastup": msg.get("lastup")}
    return out


class EbusdHttpClient:
    """Async client for ebusd's HTTP/JSON port (read-only)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        timeout: float = 10.0,
    ) -> None:
        self._session = session
        self.base = f"http://{host}:{port}"
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def get_circuit(self, circuit: str) -> dict[str, Any]:
        """GET /data/<circuit>; returns the raw JSON (includes 'global' when present)."""
        _check_name(circuit)
        url = f"{self.base}/data/{circuit}"
        try:
            async with self._session.get(url, timeout=self.timeout) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise EbusdConnectionError(f"HTTP {url}: {err}") from err
