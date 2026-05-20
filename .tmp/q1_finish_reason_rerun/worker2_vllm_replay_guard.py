#!/usr/bin/env python3
"""Worker-2 guard for Q1 remote vLLM replay runs.

This utility keeps the mutable remote/container and duplicate-process checks out
of the shared replay script so worker-3 can shard/aggregate without merge
conflicts.  It provides three guard surfaces:

1. endpoint model readiness (`/v1/models` must expose the expected Llama model),
2. remote Docker container switching between `vllm-server` and `vllm-gemma`,
3. a local non-blocking flock + process scan wrapper for replay commands.

The commands emit JSON so team logs can be copied directly into OMX task
completion evidence.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTDIR = ROOT / ".tmp/q1_finish_reason_rerun"
DEFAULT_API_URL = "http://210.179.28.26:18000/v1/chat/completions"
DEFAULT_LLAMA_MODEL = "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"
DEFAULT_GEMMA_MODEL = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
DEFAULT_SSH_HOST = "Hanam_JW_PC"
DEFAULT_LLAMA_CONTAINER = "vllm-server"
DEFAULT_GEMMA_CONTAINER = "vllm-gemma"
DEFAULT_DUPLICATE_PATTERN = "replay_q1_turns_with_metadata.py"


class GuardError(RuntimeError):
    """Raised when a guard check cannot be satisfied."""


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def chat_url_to_models_url(api_url: str) -> str:
    """Convert an OpenAI-compatible chat-completions URL to `/v1/models`."""

    parsed = urllib.parse.urlparse(api_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1/models"):
        models_path = path
    elif path.endswith("/v1/chat/completions"):
        models_path = path[: -len("/chat/completions")] + "/models"
    elif path.endswith("/chat/completions"):
        models_path = path[: -len("/chat/completions")] + "/models"
    else:
        models_path = "/v1/models"
    return urllib.parse.urlunparse(parsed._replace(path=models_path, params="", query="", fragment=""))


def model_ids_from_body(body: str) -> list[str]:
    payload = json.loads(body)
    data = payload.get("data", [])
    ids: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        for key in ("id", "root"):
            value = item.get(key)
            if isinstance(value, str) and value not in ids:
                ids.append(value)
    return ids


def fetch_model_ids(api_url: str, timeout: int) -> tuple[list[str], str]:
    models_url = chat_url_to_models_url(api_url)
    req = urllib.request.Request(models_url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return model_ids_from_body(body), body


def run_command(command: list[str], timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "elapsed_s": round(time.monotonic() - started, 3),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": 124,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "").strip() if isinstance(exc.stderr, str) else "timeout",
            "elapsed_s": round(time.monotonic() - started, 3),
        }


def docker_status(ssh_host: str, timeout: int) -> dict[str, Any]:
    remote = (
        "docker ps -a "
        "--filter name=vllm "
        "--format '{{.Names}}\\t{{.Status}}\\t{{.Ports}}'"
    )
    return run_command(["ssh", ssh_host, remote], timeout=timeout)


def switch_container(
    ssh_host: str,
    stop_container: str,
    start_container: str,
    timeout: int,
) -> dict[str, Any]:
    remote = (
        f"docker stop {stop_container} >/dev/null 2>&1 || true; "
        f"docker start {start_container}; "
        "docker ps -a --filter name=vllm "
        "--format '{{.Names}}\\t{{.Status}}\\t{{.Ports}}'"
    )
    return run_command(["ssh", ssh_host, remote], timeout=timeout)


def scan_duplicate_processes(pattern: str) -> list[dict[str, Any]]:
    result = run_command(["ps", "-axo", "pid=,command="], timeout=10)
    if result["returncode"] != 0:
        raise GuardError(f"process scan failed: {result['stderr'] or result['stdout']}")

    ignored_pids = {os.getpid(), os.getppid()}
    matches: list[dict[str, Any]] = []
    for raw_line in str(result["stdout"]).splitlines():
        line = raw_line.strip()
        if not line or pattern not in line:
            continue
        pid_text, _, command = line.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if pid in ignored_pids:
            continue
        if Path(__file__).name in command:
            continue
        matches.append({"pid": pid, "command": command.strip()})
    return matches


def require_no_duplicate_process(pattern: str, allow_duplicate_replay: bool) -> list[dict[str, Any]]:
    matches = scan_duplicate_processes(pattern)
    if matches and not allow_duplicate_replay:
        raise GuardError(
            f"duplicate replay process guard blocked {len(matches)} matching process(es)"
        )
    return matches


def wait_for_expected_model(
    api_url: str,
    expected_model: str,
    attempts: int,
    sleep_s: float,
    timeout: int,
) -> dict[str, Any]:
    history: list[dict[str, Any]] = []
    for attempt in range(1, attempts + 1):
        try:
            model_ids, body = fetch_model_ids(api_url, timeout=timeout)
            record = {"attempt": attempt, "ok": True, "model_ids": model_ids}
            history.append(record)
            if expected_model in model_ids:
                return {
                    "ok": True,
                    "expected_model": expected_model,
                    "model_ids": model_ids,
                    "attempt": attempt,
                    "raw_body": body,
                    "history": history,
                }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            history.append({"attempt": attempt, "ok": False, "error": repr(exc)})
        if attempt < attempts:
            time.sleep(sleep_s)
    return {
        "ok": False,
        "expected_model": expected_model,
        "model_ids": history[-1].get("model_ids", []) if history else [],
        "history": history,
    }


@contextlib.contextmanager
def exclusive_lock(lock_file: Path, metadata: dict[str, Any]) -> Iterator[None]:
    """Hold a non-blocking POSIX flock while a guarded command runs."""

    import fcntl

    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_file, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            existing = os.read(fd, 8192).decode("utf-8", errors="replace")
            raise GuardError(f"lock already held at {lock_file}: {existing}") from exc

        encoded = (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, encoded)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def base_record(command: str) -> dict[str, Any]:
    return {
        "created_at": now_iso(),
        "command": command,
        "cwd": str(Path.cwd()),
        "pid": os.getpid(),
    }


def command_status(args: argparse.Namespace) -> int:
    record = base_record("status")
    try:
        model_ids, raw_body = fetch_model_ids(args.api_url, args.timeout)
        record["models"] = {
            "ok": True,
            "models_url": chat_url_to_models_url(args.api_url),
            "model_ids": model_ids,
            "expected_model": args.expected_model,
            "expected_present": args.expected_model in model_ids,
            "raw_body": raw_body,
        }
    except Exception as exc:  # status should report all surfaces, not stop early
        record["models"] = {
            "ok": False,
            "models_url": chat_url_to_models_url(args.api_url),
            "expected_model": args.expected_model,
            "expected_present": False,
            "error": repr(exc),
        }

    try:
        record["duplicates"] = {
            "ok": True,
            "pattern": args.duplicate_pattern,
            "matches": scan_duplicate_processes(args.duplicate_pattern),
        }
    except Exception as exc:
        record["duplicates"] = {
            "ok": False,
            "pattern": args.duplicate_pattern,
            "error": repr(exc),
        }

    record["docker"] = docker_status(args.ssh_host, args.ssh_timeout)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    if args.require_expected and not record["models"].get("expected_present"):
        return 3
    if args.require_no_duplicates and record["duplicates"].get("matches"):
        return 4
    return 0


def command_check_duplicates(args: argparse.Namespace) -> int:
    record = base_record("check-duplicates")
    try:
        matches = require_no_duplicate_process(args.duplicate_pattern, args.allow_duplicate_replay)
        record["ok"] = True
        record["pattern"] = args.duplicate_pattern
        record["matches"] = matches
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    except GuardError as exc:
        record["ok"] = False
        record["error"] = str(exc)
        record["matches"] = scan_duplicate_processes(args.duplicate_pattern)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 4


def command_ensure_llama(args: argparse.Namespace) -> int:
    record = base_record("ensure-llama")
    try:
        record["duplicates"] = require_no_duplicate_process(
            args.duplicate_pattern,
            args.allow_duplicate_replay,
        )
        ready = wait_for_expected_model(
            args.api_url,
            args.expected_model,
            attempts=1,
            sleep_s=0,
            timeout=args.timeout,
        )
        record["before"] = ready
        if not ready["ok"]:
            if not args.apply:
                record["ok"] = False
                record["would_switch"] = {
                    "stop": args.gemma_container,
                    "start": args.llama_container,
                    "ssh_host": args.ssh_host,
                }
                print(json.dumps(record, ensure_ascii=False, indent=2))
                return 3
            record["switch"] = switch_container(
                args.ssh_host,
                stop_container=args.gemma_container,
                start_container=args.llama_container,
                timeout=args.ssh_timeout,
            )
            if record["switch"]["returncode"] != 0:
                record["ok"] = False
                print(json.dumps(record, ensure_ascii=False, indent=2))
                return 5
            ready = wait_for_expected_model(
                args.api_url,
                args.expected_model,
                attempts=args.wait_attempts,
                sleep_s=args.wait_sleep,
                timeout=args.timeout,
            )
        record["after"] = ready
        record["ok"] = bool(ready["ok"])
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0 if ready["ok"] else 6
    except GuardError as exc:
        record["ok"] = False
        record["error"] = str(exc)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 4


def command_restore_gemma(args: argparse.Namespace) -> int:
    record = base_record("restore-gemma")
    if not args.apply:
        record["ok"] = False
        record["would_switch"] = {
            "stop": args.llama_container,
            "start": args.gemma_container,
            "ssh_host": args.ssh_host,
        }
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 3
    record["switch"] = switch_container(
        args.ssh_host,
        stop_container=args.llama_container,
        start_container=args.gemma_container,
        timeout=args.ssh_timeout,
    )
    ready = wait_for_expected_model(
        args.api_url,
        args.expected_model,
        attempts=args.wait_attempts,
        sleep_s=args.wait_sleep,
        timeout=args.timeout,
    )
    record["after"] = ready
    record["ok"] = record["switch"]["returncode"] == 0 and bool(ready["ok"])
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if record["ok"] else 6


def command_run(args: argparse.Namespace) -> int:
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print(json.dumps({"ok": False, "error": "missing command after --"}, indent=2))
        return 2

    record = base_record("run")
    record["guarded_command"] = command
    record["lock_file"] = str(args.lock_file)
    try:
        duplicates = require_no_duplicate_process(
            args.duplicate_pattern,
            args.allow_duplicate_replay,
        )
        record["duplicates"] = duplicates
        if not args.skip_model_check:
            ready = wait_for_expected_model(
                args.api_url,
                args.expected_model,
                attempts=args.wait_attempts,
                sleep_s=args.wait_sleep,
                timeout=args.timeout,
            )
            record["model_ready"] = ready
            if not ready["ok"]:
                raise GuardError(f"expected model not ready: {args.expected_model}")

        if args.dry_run:
            record["ok"] = True
            record["dry_run"] = True
            print(json.dumps(record, ensure_ascii=False, indent=2))
            return 0

        with exclusive_lock(
            args.lock_file,
            {
                "created_at": now_iso(),
                "pid": os.getpid(),
                "command": command,
                "cwd": str(Path.cwd()),
                "duplicate_pattern": args.duplicate_pattern,
                "expected_model": args.expected_model,
            },
        ):
            proc = subprocess.run(command, check=False)
            record["returncode"] = proc.returncode
            record["ok"] = proc.returncode == 0
            print(json.dumps(record, ensure_ascii=False, indent=2))
            return proc.returncode
    except GuardError as exc:
        record["ok"] = False
        record["error"] = str(exc)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 4


def command_self_test(_args: argparse.Namespace) -> int:
    assert chat_url_to_models_url("http://x:1/v1/chat/completions") == "http://x:1/v1/models"
    assert chat_url_to_models_url("http://x:1/chat/completions") == "http://x:1/models"
    assert chat_url_to_models_url("http://x:1/v1/models") == "http://x:1/v1/models"
    body = json.dumps({"data": [{"id": "a", "root": "a"}, {"id": "b", "root": "c"}]})
    assert model_ids_from_body(body) == ["a", "b", "c"]
    empty = json.dumps({"data": []})
    assert model_ids_from_body(empty) == []
    print(json.dumps({"ok": True, "self_test": "passed"}, indent=2))
    return 0


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api-url", default=os.getenv("VLLM_API_URL", DEFAULT_API_URL))
    parser.add_argument("--expected-model", default=os.getenv("EVAL_MODEL_NAME", DEFAULT_LLAMA_MODEL))
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--duplicate-pattern", default=DEFAULT_DUPLICATE_PATTERN)
    parser.add_argument("--allow-duplicate-replay", action="store_true")


def add_remote_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ssh-host", default=os.getenv("Q1_VLLM_SSH_HOST", DEFAULT_SSH_HOST))
    parser.add_argument("--ssh-timeout", type=int, default=30)
    parser.add_argument("--llama-container", default=os.getenv("Q1_LLAMA_CONTAINER", DEFAULT_LLAMA_CONTAINER))
    parser.add_argument("--gemma-container", default=os.getenv("Q1_GEMMA_CONTAINER", DEFAULT_GEMMA_CONTAINER))
    parser.add_argument("--wait-attempts", type=int, default=24)
    parser.add_argument("--wait-sleep", type=float, default=5.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command_name", required=True)

    status = sub.add_parser("status", help="Report endpoint, Docker, and duplicate-process state.")
    add_common_args(status)
    add_remote_args(status)
    status.add_argument("--require-expected", action="store_true")
    status.add_argument("--require-no-duplicates", action="store_true")
    status.set_defaults(func=command_status)

    dup = sub.add_parser("check-duplicates", help="Fail if replay processes are already running.")
    add_common_args(dup)
    dup.set_defaults(func=command_check_duplicates)

    ensure = sub.add_parser("ensure-llama", help="Ensure the remote endpoint serves the Llama target.")
    add_common_args(ensure)
    add_remote_args(ensure)
    ensure.add_argument("--apply", action="store_true", help="Actually switch Docker containers if needed.")
    ensure.set_defaults(func=command_ensure_llama)

    restore = sub.add_parser("restore-gemma", help="Restore the remote endpoint to the Gemma judge container.")
    add_common_args(restore)
    add_remote_args(restore)
    restore.set_defaults(expected_model=os.getenv("Q1_GEMMA_MODEL", DEFAULT_GEMMA_MODEL))
    restore.add_argument("--apply", action="store_true", help="Actually switch Docker containers.")
    restore.set_defaults(func=command_restore_gemma)

    run = sub.add_parser("run", help="Run a command under duplicate-process and model-readiness guards.")
    add_common_args(run)
    run.add_argument("--lock-file", type=Path, default=DEFAULT_OUTDIR / "worker2_replay.lock")
    run.add_argument("--skip-model-check", action="store_true")
    run.add_argument("--wait-attempts", type=int, default=1)
    run.add_argument("--wait-sleep", type=float, default=0.0)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("command", nargs=argparse.REMAINDER)
    run.set_defaults(func=command_run)

    self_test = sub.add_parser("self-test", help="Run offline unit checks for parser helpers.")
    self_test.set_defaults(func=command_self_test)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
