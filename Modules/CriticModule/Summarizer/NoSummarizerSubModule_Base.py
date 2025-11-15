import json
from typing import Any, Dict, List, Optional

from ...utils import (
    _format_grad_for_module,
    _format_history_for_prompt,
    _log_submodule_io,
    _parse_bullet_list,
    _role_transcript,
)

MODULE_TYPE = "summarizer"
MODULE_VERSION = "base"


class NoSummarizerSubModule_Base:
    def __init__(self, model: str, client) -> None:
        pass

    def call(self, history: List[Dict[str, str]], grad: Any) -> str:
        aggregated = {
            "user_summary": None,
            "assistant_summary": None,
            "open_questions": None,
        }
        return json.dumps(aggregated, ensure_ascii=False)


def build(model_name: str, *, openai_client, **_) -> NoSummarizerSubModule_Base:
    return NoSummarizerSubModule_Base(model_name, openai_client)
