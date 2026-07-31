"""
pi_client.py
~~~~~~~~~~~~
Python client for the Pi Agent RPC stdio process.

Spawns the Node.js process once (persistent) and communicates via line-delimited
JSON-RPC over stdin/stdout.

Includes:
  - Automatic process restart if the subprocess crashes.
  - Request timeouts to avoid hanging HTTP handlers.
  - Clear error reporting if Node/TypeScript runtime is missing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)

_PI_RUNTIME_DIR = Path(__file__).resolve().parent.parent / "pi-runtime"


class PiRPCError(Exception):
    """Raised when the Pi RPC process returns an error or fails to start."""
    pass


class PiClient:
    """Persistent stdio RPC client for the Pi Node subprocess."""

    def __init__(self, runtime_dir: Path | None = None):
        self.runtime_dir = runtime_dir or _PI_RUNTIME_DIR
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._req_counter = 0

    async def _ensure_process(self) -> asyncio.subprocess.Process:
        """Start or restart the Pi Node RPC subprocess if not running."""
        if self._proc is not None and self._proc.returncode is None:
            return self._proc

        # Check Node.js runtime presence
        node_cmd = "node"
        server_js = self.runtime_dir / "dist" / "server.js"
        server_ts = self.runtime_dir / "src" / "server.ts"

        if not server_js.exists() and not server_ts.exists():
            raise PiRPCError(
                f"Pi runtime entrypoint missing in {self.runtime_dir}. "
                "Run `npm run build` inside backend/pi-runtime first."
            )

        cmd = [node_cmd]
        if server_js.exists():
            cmd.append(str(server_js))
        else:
            # Fallback to tsx/node --loader if dist/server.js not compiled yet
            cmd.extend(["--import", "tsx", str(server_ts)])

        try:
            logger.info("Spawning Pi RPC subprocess: %s (cwd=%s)", " ".join(cmd), self.runtime_dir)
            self._proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.runtime_dir),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy(),
            )
            # Read startup line
            if self._proc.stdout:
                line = await asyncio.wait_for(self._proc.stdout.readline(), timeout=5.0)
                logger.info("Pi RPC startup output: %s", line.decode().strip())
            return self._proc
        except FileNotFoundError:
            raise PiRPCError(
                "Node.js ('node') command not found. Ensure Node.js is installed and in PATH."
            )
        except Exception as exc:
            raise PiRPCError(f"Failed to start Pi RPC subprocess: {exc}") from exc

    async def run_turn(
        self,
        messages: list[dict[str, str]],
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: str = "",
        session_id: str = "default-session",
        timeout_seconds: float = 30.0,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Send a prompt turn to the Pi agent and yield streaming RPC events.

        Yields dicts representing SSE events:
          {"type": "tool_call", "tool": "...", "args": {...}}
          {"type": "token", "content": "..."}
          {"type": "done", "content": "...", "skill_used": "..."}
        """
        async with self._lock:
            proc = await self._ensure_process()

            self._req_counter += 1
            req_id = f"req-{self._req_counter}"

            payload = {
                "id": req_id,
                "session_id": session_id,
                "messages": messages,
                "provider": provider,
                "model": model,
                "api_key": api_key,
            }

            assert proc.stdin is not None
            assert proc.stdout is not None

            proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
            await proc.stdin.drain()

            start_time = asyncio.get_event_loop().time()

            while True:
                remaining = timeout_seconds - (asyncio.get_event_loop().time() - start_time)
                if remaining <= 0:
                    raise PiRPCError(f"Pi RPC request timed out after {timeout_seconds}s")

                try:
                    line_bytes = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
                except asyncio.TimeoutError:
                    raise PiRPCError(f"Pi RPC request timed out after {timeout_seconds}s")

                if not line_bytes:
                    # Subprocess closed stdout (crashed)
                    self._proc = None
                    raise PiRPCError("Pi RPC subprocess terminated unexpectedly.")

                line = line_bytes.decode("utf-8").strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Unparseable line from Pi RPC: %r", line)
                    continue

                if msg.get("id") != req_id and msg.get("type") != "ready":
                    continue

                msg_type = msg.get("type")
                if msg_type == "error":
                    raise PiRPCError(f"Pi agent error: {msg.get('error')}")

                yield msg

                if msg_type == "done":
                    break

    async def close(self) -> None:
        """Gracefully terminate the subprocess."""
        if self._proc is not None:
            try:
                self._proc.terminate()
                await self._proc.wait()
            except Exception:
                pass
            finally:
                self._proc = None


# Singleton instance
pi_client = PiClient()
