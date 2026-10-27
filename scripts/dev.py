#!/usr/bin/env python3
"""Run the local FastAPI services and Vue client together (macOS/Linux)."""

from __future__ import annotations

import argparse
import errno
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
SERVICES = (("m1", 3101), ("m2", 3102), ("m3", 3103), ("d", 3104))
HOST = "127.0.0.1"
WEB_PORT = 5173
OUTPUT_LOCK = threading.Lock()


def log(message: str) -> None:
    with OUTPUT_LOCK:
        print(message, flush=True)


def stop(processes: list[subprocess.Popen]) -> None:
    # Each command owns a separate session, including npm/reloader descendants.
    previous = {sig: signal.signal(sig, signal.SIG_IGN) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        for process in reversed(processes):
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 5
        for process in processes:
            try:
                process.wait(timeout=max(0.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        for process in reversed(processes):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def setup(command: list[str]) -> None:
    process = subprocess.Popen(command, cwd=ROOT, start_new_session=True)
    try:
        if process.wait() != 0:
            raise RuntimeError(f"依赖准备失败：{' '.join(command)}")
    finally:
        stop([process])


def prepare(install: bool) -> tuple[str, str]:
    npm = shutil.which("npm")
    if not npm or not shutil.which("node"):
        raise RuntimeError("未找到 Node.js/npm，请先安装项目推荐的 Node.js 24。")
    python = ROOT / ".venv" / "bin" / "python"
    if install or not python.is_file():
        uv = shutil.which("uv")
        if uv:
            log("使用 uv.lock 准备 Python 依赖……")
            os.environ.setdefault("UV_CACHE_DIR", str(ROOT / ".uv-cache"))
            setup([uv, "sync", "--frozen"])
        else:
            if not python.is_file():
                base = shutil.which("python3.12")
                if not base and sys.version_info[:2] == (3, 12):
                    base = sys.executable
                if not base:
                    raise RuntimeError("请先安装 uv 或 Python 3.12，再重新运行本脚本。")
                setup([base, "-m", "venv", str(ROOT / ".venv")])
            log("使用 pip 准备 Python 依赖（版本范围来自 pyproject.toml）。")
            read_dependencies = (
                "import json,tomllib; "
                "print(json.dumps(tomllib.load(open('pyproject.toml','rb'))"
                "['project']['dependencies']))"
            )
            dependencies = json.loads(subprocess.check_output(
                [str(python), "-c", read_dependencies], cwd=ROOT, text=True
            ))
            setup([str(python), "-m", "pip", "install", *dependencies])
    result = subprocess.run(
        [str(python), "-c", "import sys; assert sys.version_info[:2] == (3, 12); import fastapi, uvicorn, psycopg"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        raise RuntimeError(".venv 需要 Python 3.12、FastAPI、Uvicorn 和 Psycopg；请运行本脚本加 --install 修复依赖。")
    if install or not (WEB / "node_modules" / ".bin" / "vite").is_file():
        log("使用 package-lock.json 准备前端依赖……")
        setup([npm, "--prefix", str(WEB), "ci"])
    return str(python), npm


def check_ports() -> None:
    for name, port in (*SERVICES, ("web", WEB_PORT)):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind((HOST, port))
            except OSError as error:
                hint = "请先停止占用端口的进程。" if error.errno == errno.EADDRINUSE else "请检查本机监听权限。"
                raise RuntimeError(
                    f"{name} 无法使用 {HOST}:{port}：{error}。{hint}"
                ) from error


def forward_output(name: str, process: subprocess.Popen) -> None:
    for line in process.stdout:
        log(f"[{name}] {line.rstrip()}")


def check_running(processes: dict[str, subprocess.Popen]) -> None:
    for name, process in processes.items():
        code = process.poll()
        if code is not None:
            raise RuntimeError(f"{name} 已退出（状态码 {code}），停止其余服务。")


def wait_ready(processes: dict[str, subprocess.Popen]) -> None:
    pending = {name: (port, "/healthz") for name, port in SERVICES}
    pending["web"] = (WEB_PORT, "/")
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + 30
    while pending and time.monotonic() < deadline:
        check_running(processes)
        for name, (port, path) in list(pending.items()):
            try:
                with opener.open(f"http://{HOST}:{port}{path}", timeout=0.3) as response:
                    body = response.read().decode("utf-8")
                    valid = (
                        "@vite/client" in body if name == "web"
                        else json.loads(body) == {"service": f"{name}-api", "status": "ok"}
                    )
                    if response.status == 200 and valid:
                        if name == "m1":
                            log(f"M1 依赖模式：{response.headers.get('X-Dependency-Mode', '未报告')}")
                        elif name == "d":
                            log(f"D 身份依赖模式：{response.headers.get('X-Identity-Mode', '未报告')}")
                        del pending[name]
            except (URLError, TimeoutError, OSError, ValueError):
                pass
        if pending:
            time.sleep(0.1)
    check_running(processes)
    if pending:
        raise RuntimeError(f"启动检查超时：{', '.join(pending)}；请检查上方服务日志。")


def interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def main() -> int:
    parser = argparse.ArgumentParser(description="一键启动本机四个 FastAPI 服务与 Vue 前端；沿用当前环境配置，业务数据库及外部依赖需另行配置。")
    parser.add_argument("--install", action="store_true", help="重新同步后端与前端依赖；首次运行自动安装缺失的环境")
    parser.add_argument("--no-reload", action="store_true", help="关闭后端自动重载")
    args = parser.parse_args()
    processes: dict[str, subprocess.Popen] = {}
    signal.signal(signal.SIGTERM, interrupt)
    try:
        check_ports()
        python, npm = prepare(args.install)
        commands = {}
        for name, port in SERVICES:
            command = [python, "-m", "uvicorn", f"services.{name}.main:app", "--host", HOST, "--port", str(port)]
            if not args.no_reload:
                command += ["--reload", "--reload-dir", str(ROOT / "services")]
            commands[name] = command
        commands["web"] = [npm, "--prefix", str(WEB), "run", "dev", "--", "--host", HOST, "--port", str(WEB_PORT), "--strictPort"]
        for name, command in commands.items():
            process = subprocess.Popen(
                command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", start_new_session=True,
            )
            processes[name] = process
            threading.Thread(target=forward_output, args=(name, process), daemon=True).start()
        wait_ready(processes)
        log(f"\n前后端 HTTP 入口已启动：\n  Web  http://{HOST}:{WEB_PORT}")
        for name, port in SERVICES:
            log(f"  {name.upper():3}  http://{HOST}:{port}/docs  （健康检查：/healthz）")
        log("健康检查通过不代表业务依赖可用。本启动器不自动启用开发替身；M1 调度器需单独启动。按 Ctrl+C 停止本次服务。\n")
        while True:
            check_running(processes)
            time.sleep(0.25)
    except KeyboardInterrupt:
        log("\n正在停止本次启动的全部服务……")
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        log(f"启动失败：{error}")
        return 1
    finally:
        stop(list(processes.values()))


if __name__ == "__main__":
    sys.exit(main())
