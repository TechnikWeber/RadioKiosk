"""One long-running mpv instance, controlled through its JSON IPC socket.

Every source hands mpv a URL, so volume, output device and metadata work the same
for web radio, DAB+ and FM.
"""

import asyncio
import json
import shutil

from .config import RUNTIME_DIR
from .util import kill, spawn


class Mpv:
    def __init__(self, on_event):
        self.on_event = on_event
        self.proc = None
        self.writer = None
        self.pending = {}
        self.next_id = 0
        self.socket = RUNTIME_DIR / "mpv.sock"

    @staticmethod
    def available():
        return shutil.which("mpv") is not None

    async def _ensure(self):
        if self.proc and self.proc.returncode is None and self.writer:
            return
        if not self.available():
            raise RuntimeError("mpv is not installed")
        await kill(self.proc)
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        self.socket.unlink(missing_ok=True)
        self.proc = await spawn(
            "mpv", "--idle=yes", "--no-video", "--no-terminal", "--no-config",
            f"--input-ipc-server={self.socket}",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        for _ in range(50):
            if self.socket.exists():
                break
            await asyncio.sleep(0.1)
        reader, self.writer = await asyncio.open_unix_connection(str(self.socket))
        asyncio.create_task(self._read(reader))
        await self.command("observe_property", 1, "media-title")
        await self.command("observe_property", 2, "core-idle")

    async def _read(self, reader):
        while line := await reader.readline():
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if "request_id" in msg:
                fut = self.pending.pop(msg["request_id"], None)
                if fut and not fut.done():
                    fut.set_result(msg)
            elif "event" in msg:
                self.on_event(msg)
        self.writer = None
        for fut in self.pending.values():
            if not fut.done():
                fut.set_exception(RuntimeError("mpv exited"))
        self.pending.clear()

    async def command(self, *args):
        self.next_id += 1
        fut = asyncio.get_running_loop().create_future()
        self.pending[self.next_id] = fut
        self.writer.write(json.dumps({"command": args, "request_id": self.next_id}).encode() + b"\n")
        await self.writer.drain()
        return await asyncio.wait_for(fut, 5)

    async def play(self, url, options=""):
        await self._ensure()
        await self.command("loadfile", url, "replace", -1, options)

    async def stop(self):
        if self.writer:
            await self.command("stop")

    async def close(self):
        await kill(self.proc)
