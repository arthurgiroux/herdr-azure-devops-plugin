"""Thin wrapper over the herdr CLI."""

import json
import os
import subprocess

from . import config


class HerdrError(Exception):
    pass


def run_herdr(args: list[str]) -> dict:
    binary = os.environ.get("HERDR_BIN_PATH", "herdr")
    try:
        proc = subprocess.run([binary, *args], capture_output=True, text=True)
    except FileNotFoundError as err:
        raise HerdrError(f"herdr binary not found: {binary}") from err
    if proc.returncode != 0:
        raise HerdrError(proc.stderr.strip() or proc.stdout.strip())
    try:
        return json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError as err:
        raise HerdrError(f"Unexpected herdr output: {err}") from err


def pane_cwd(pane_id: str) -> str | None:
    pane = run_herdr(["pane", "get", pane_id]).get("result", {}).get("pane", {})
    return pane.get("foreground_cwd") or pane.get("cwd")


def open_plugin_pane(target_pane: str | None, env: dict[str, str]) -> None:
    args = ["plugin", "pane", "open", "--plugin", config.PLUGIN_ID,
            "--entrypoint", config.PANE_ENTRYPOINT, "--no-focus"]
    if target_pane:
        args += ["--target-pane", target_pane]
    for key, value in env.items():
        args += ["--env", f"{key}={value}"]
    run_herdr(args)


def show_toast(title: str, body: str, sound: str) -> None:
    run_herdr(["notification", "show", title, "--body", body, "--sound", sound])

