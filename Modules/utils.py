import importlib.util
import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


CONFIG_DEFAULTS: Dict[str, Any] = {
    "mode": "cli",
    "test_mode": False,
    "version": None,
    "exp_module": {
        "input_csv": "EXP001/in.csv",
        "output_csv": "EXP001/out.csv",
        "config": "EXP001/exp_config.txt",
    },
}

EXP_CONFIG_DEFAULTS: Dict[str, Any] = {
    "default_runs": 1,
    "default_version": None,
    "rows": {},
    "has_header": False,
}

TEST_MODE = False


class _SubmoduleProgressLogger:
    """Single line progress printing when GPT calls take time."""

    def __init__(self) -> None:
        self.enabled = False
        self.total_steps = 0
        self.started_steps = 0
        self.prefix = ""
        self.single_line = False
        self.line_open = False

    def set_enabled(self, flag: bool) -> None:
        self.enabled = bool(flag)

    def prepare(self, total_steps: int) -> None:
        self.set_enabled(not TEST_MODE)
        self.total_steps = max(0, total_steps)
        self.started_steps = 0

    def extend(self, additional_steps: int) -> None:
        if not self.enabled:
            return
        self.total_steps = max(self.total_steps + int(additional_steps), self.started_steps)

    def set_prefix(self, text: str) -> None:
        self.prefix = text or ""

    def set_single_line_mode(self, flag: bool) -> None:
        if not flag:
            self.end_line()
        self.single_line = bool(flag)

    @contextmanager
    def step(self, label: str):
        token = self._start(label)
        try:
            yield
        except Exception:
            self._finish(token, status="failed")
            raise
        else:
            self._finish(token)

    def _start(self, label: str):
        if not self.enabled:
            return None
        self.started_steps += 1
        idx = self.started_steps
        total = self.total_steps or idx
        if total < idx:
            total = idx
            self.total_steps = total
        prefix = f" {self.prefix}" if self.prefix else ""
        if self.single_line:
            if not self.line_open:
                print(f"[CritiqueBot]{prefix}", end="", flush=True)
                self.line_open = True
            print(f" {label}", end="", flush=True)
        else:
            line = f"[CritiqueBot]{prefix} ({idx}/{total}) {label} ..."
            print(line, end="", flush=True)
        return True

    def _finish(self, token, status: str = "complete!") -> None:
        if token is None:
            return
        if not self.single_line:
            print(f" {status}")

    def end_line(self) -> None:
        if self.line_open:
            print()
            self.line_open = False

    def append_token(self, text: str) -> None:
        if not self.enabled or not self.single_line:
            return
        if not self.line_open:
            prefix = f" {self.prefix}" if self.prefix else ""
            print(f"[CritiqueBot]{prefix}", end="", flush=True)
            self.line_open = True
        print(f" {text}", end="", flush=True)


SUBMODULE_PROGRESS_LOGGER = _SubmoduleProgressLogger()


def set_test_mode(flag: bool) -> None:
    global TEST_MODE
    TEST_MODE = bool(flag)
    SUBMODULE_PROGRESS_LOGGER.set_enabled(not TEST_MODE)
    if TEST_MODE:
        print(f"[CritiqueBot] TEST_MODE set to {TEST_MODE}")


def _format_history_for_prompt(history: Optional[List[Dict[str, str]]]) -> str:
    lines: List[str] = []
    for turn in history or []:
        role = turn.get("role", "user")
        prefix = "User" if role == "user" else "Assistant"
        content = (turn.get("content") or "").strip()
        lines.append(f"{prefix}: {content}")
    joined = "\n".join(lines).strip()
    return joined or "대화 기록이 아직 없습니다."


def _test_mode_print(message: str) -> None:
    if TEST_MODE:
        print(message)


def _log_submodule_io(
    tag: str,
    prompt: str,
    response: str,
    module_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> None:
    if not TEST_MODE:
        return
    divider = "-" * 60
    header = f"[CritiqueBot::{tag}]"
    if module_name or model_name:
        module_bits = module_name or "UnknownModule"
        if model_name:
            module_bits += f"/{model_name}"
        header += f" [{module_bits}]"
    print(
        f"""
{header} 요청
{divider}
{prompt}
"""
    )
    print(
        f"""{header} 응답
{divider}
{response}
{divider}
"""
    )


def _format_grad_for_module(grad: Any) -> Optional[str]:
    if not grad:
        return None
    if isinstance(grad, (list, tuple, set)):
        cleaned = [str(item).strip() for item in grad if str(item).strip()]
        if cleaned:
            return "\n".join(f"- {item}" for item in cleaned)
        return None
    return str(grad).strip() or None


def _collect_role_messages(history: Iterable[Dict[str, str]], role: str) -> List[str]:
    return [
        turn.get("content", "").strip()
        for turn in (history or [])
        if turn.get("role") == role and turn.get("content")
    ]


def _role_transcript(history: List[Dict[str, str]], role: str) -> str:
    msgs = _collect_role_messages(history, role)
    return "\n".join(msgs).strip()


def _parse_bullet_list(text: str) -> List[str]:
    bullets: List[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("- "):
            bullets.append(line[2:].strip())
        elif line.startswith("•"):
            bullets.append(line[1:].strip())
        else:
            bullets.append(line)
    return [b for b in bullets if b]


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def load_config(config_path: Path) -> Dict[str, Any]:
    base = Path(config_path)
    if not base.exists():
        raise FileNotFoundError(f"[CritiqueBot] config 파일을 찾을 수 없습니다: {base}")
    data = _load_json(base)
    merged = json.loads(json.dumps(CONFIG_DEFAULTS))
    merged.update(data)
    exp_mod = CONFIG_DEFAULTS["exp_module"].copy()
    exp_mod.update(merged.get("exp_module") or {})
    merged["exp_module"] = exp_mod
    if merged.get("version") is None and data.get("experiment") is not None:
        merged["version"] = data.get("experiment")
    merged["_config_dir"] = str(base.parent.resolve())
    return merged


def load_exp_config(config_path: Path) -> Dict[str, Any]:
    base = Path(config_path)
    if not base.exists():
        raise FileNotFoundError(f"[CritiqueBot] exp_config 파일을 찾을 수 없습니다: {base}")
    data = _load_json(base)
    merged = EXP_CONFIG_DEFAULTS.copy()
    merged.update(data)
    if merged.get("default_version") is None and data.get("default_experiment") is not None:
        merged["default_version"] = data.get("default_experiment")
    rows = {}
    for k, v in (merged.get("rows") or {}).items():
        if not isinstance(v, dict):
            continue
        row_cfg = dict(v)
        if "version" not in row_cfg and "experiment" in row_cfg:
            row_cfg["version"] = row_cfg["experiment"]
        rows[str(k)] = row_cfg
    merged["rows"] = rows
    return merged


def ensure_packages(packages: List[str]) -> None:
    missing = []
    for pkg in packages:
        if importlib.util.find_spec(pkg) is None:
            missing.append(pkg)
    if not missing:
        return
    print(f"[CritiqueBot] 필요한 패키지 설치 중: {', '.join(missing)}")
    cmd = [sys.executable, "-m", "pip", "install", *missing]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"pip install failed for {missing}:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}"
        )


def load_batch_config(config_path: Path):
    base = Path(config_path)
    if not base.exists():
        raise FileNotFoundError(f"[CritiqueBot] exp 설정 파일을 찾을 수 없습니다: {base}")
    data = _load_json(base)
    general_defaults = {
        "test_mode": False,
        "openai_api_key": None,
        "tavily_api_key": None,
        "version": None,
    }
    general = general_defaults.copy()
    for key in general_defaults:
        if key in data:
            general[key] = data[key]
    general["_config_dir"] = str(base.parent.resolve())
    runner_defaults = {
        "input_csv": "in.csv",
        "output_csv": "out.csv",
        "default_runs": 1,
        "default_version": None,
        "has_header": False,
        "rows": {},
    }
    runner_source = data.get("exp_runner") or data.get("runner") or {}
    for key in runner_defaults:
        if key not in runner_source and key in data:
            runner_source[key] = data[key]
    runner = runner_defaults.copy()
    runner.update(runner_source)
    rows = {}
    for k, v in (runner.get("rows") or {}).items():
        if isinstance(v, dict):
            rows[str(k)] = v
    runner["rows"] = rows
    runner["_config_dir"] = general["_config_dir"]
    return general, runner
