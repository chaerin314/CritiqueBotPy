import csv
from pathlib import Path
from typing import Any, Dict, List

from .utils import SUBMODULE_PROGRESS_LOGGER


class EXPModule:
    """Batch runner that replays scripted user turns from CSV."""

    def __init__(self, critic_factory, exp_config: Dict, input_csv: Path, output_csv: Path) -> None:
        self.factory = critic_factory
        self.exp_cfg = exp_config
        self.input_csv = Path(input_csv)
        self.output_csv = Path(output_csv)

    def run(self) -> None:
        entries = self._load_inputs()
        if not entries:
            print(f"[CritiqueBot] EXPModule: 입력 CSV({self.input_csv})에서 실행할 행을 찾지 못했습니다.")
            return
        max_turns = max(len(entry["turns"]) for entry in entries)
        header = ["case_id", "run"]
        for idx in range(1, max_turns + 1):
            header.append(f"user{idx}")
            header.append(f"model{idx}")
            header.append(f"ref{idx}")
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        total_rows = len(entries)
        with self.output_csv.open("w", newline="", encoding="utf-8") as f_out:
            writer = csv.writer(f_out)
            writer.writerow(header)
            for row_idx, entry in enumerate(entries, start=1):
                case_id = entry["case_id"]
                alias = entry["alias"]
                user_turns = entry["turns"]
                row_cfg = self.exp_cfg["rows"].get(case_id) or self.exp_cfg["rows"].get(alias, {})
                runs = row_cfg.get("runs", self.exp_cfg["default_runs"]) or 1
                row_version = row_cfg.get("version")
                if row_version is None:
                    row_version = row_cfg.get("experiment")
                exp_override = row_version if row_version is not None else self.exp_cfg.get("default_version")
                if exp_override is None:
                    exp_override = self.exp_cfg.get("default_experiment")
                for run_idx in range(1, runs + 1):
                    prefix_base = f"[Row {row_idx}/{total_rows} | {case_id} | Run {run_idx}/{runs}"
                    critic = self.factory.get_or_build(exp_override)
                    model_turns = self._play_case(critic, list(user_turns), prefix_base)
                    SUBMODULE_PROGRESS_LOGGER.set_prefix("")
                    row = [case_id, str(run_idx)]
                    for idx in range(max_turns):
                        user_text = user_turns[idx] if idx < len(user_turns) else ""
                        model_entry = model_turns[idx] if idx < len(model_turns) else None
                        if model_entry:
                            model_text = model_entry.get("txt") or ""
                            refs = model_entry.get("ref") or {}
                            ref_snippet = "; ".join(f"{title}: {url}" for title, url in refs.items()) if refs else ""
                        else:
                            model_text = ""
                            ref_snippet = ""
                        row.append(user_text)
                        row.append(model_text)
                        row.append(ref_snippet)
                    writer.writerow(row)

    def _load_inputs(self) -> List[Dict[str, List[str]]]:
        path = self.input_csv
        if not path.exists():
            raise FileNotFoundError(f"in.csv not found: {path}")
        entries: List[Dict[str, List[str]]] = []
        with path.open("r", encoding="utf-8") as f_in:
            reader = csv.reader(f_in)
            all_rows = list(reader)
        if self.exp_cfg.get("has_header") and all_rows:
            all_rows = all_rows[1:]
        for idx, row in enumerate(all_rows, start=1):
            raw_cells = [cell.strip() for cell in row]
            if not any(raw_cells):
                continue
            case_id = raw_cells[0] or f"row{idx}"
            turns = [cell for cell in raw_cells[1:] if cell]
            entries.append({"case_id": case_id, "alias": f"row{idx}", "turns": turns})
        return entries

    def _play_case(self, critic, user_turns: List[str], prefix_base: str) -> List[str]:
        history = []
        model_turns: List[Dict[str, Any]] = []
        total_turns = len(user_turns)
        for turn_idx, user_text in enumerate(user_turns, start=1):
            turn_prefix = f"{prefix_base} | Turn {turn_idx}/{total_turns}]"
            SUBMODULE_PROGRESS_LOGGER.set_prefix(turn_prefix)
            SUBMODULE_PROGRESS_LOGGER.set_single_line_mode(True)
            history.append({"role": "user", "content": user_text})
            try:
                rsp = critic.call(history)
                refs = {}
                if isinstance(rsp, dict):
                    assistant_text = rsp.get("txt") or ""
                    refs = rsp.get("ref") or {}
                else:
                    assistant_text = str(rsp)
                model_turns.append({"txt": assistant_text, "ref": refs})
                history.append({"role": "assistant", "content": assistant_text})
            finally:
                SUBMODULE_PROGRESS_LOGGER.end_line()
                SUBMODULE_PROGRESS_LOGGER.set_single_line_mode(False)
        return model_turns
