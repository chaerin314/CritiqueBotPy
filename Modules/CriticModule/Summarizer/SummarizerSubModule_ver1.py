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
MODULE_VERSION = "v1"


class SummarizerSubModule_ver1:
    def __init__(self, model: str, client) -> None:
        self.sys = (
            "You are the Summarizer sub-module inside a debate assistant. "
            "Compress the multi-turn dialogue into a briefing that highlights "
            "the user's stance, the assistant's prior rebuttals, and unresolved issues. "
            "Respond in Korean when the dialogue is Korean."
        )
        self.model = model
        self.openai = client

    def _call_model(self, prompt: str, tag: str = "Summarizer") -> str:
        rsp = self.openai.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.sys},
                {"role": "user", "content": prompt},
            ],
        )
        content = rsp.choices[0].message.content.strip()
        _log_submodule_io(tag, prompt, content, self.__class__.__name__, self.model)
        return content

    def _summarize_role(
        self, transcript: str, label: str, grad_text: Optional[str]
    ) -> List[str]:
        if not transcript:
            return []
        token_count = len(transcript.split())
        bullet_limit = 1 if token_count <= 20 else 3
        prompt = (
            f"""다음은 {label} 발화 기록입니다:
{transcript}

"""
            f"핵심 주장 1~{bullet_limit}개를 bullet list로 요약하세요. 존재하는 정보만 사용하고, 내용이 부족하면 1개 이하로만 작성하세요. 새로운 내용은 절대 만들지 마세요."
        )
        if grad_text:
            prompt += f"""

[개선 지시]
{grad_text}"""
        content = self._call_model(prompt, tag=f"Summarizer-{label}")
        return _parse_bullet_list(content)

    def _open_questions(
        self,
        history_text: str,
        user_summary: List[str],
        assistant_summary: List[str],
        grad_text: Optional[str],
    ) -> List[str]:
        user_lines = user_summary or ["(정보 없음)"]
        assistant_lines = assistant_summary or ["(정보 없음)"]
        user_block = "\n- ".join(user_lines)
        assistant_block = "\n- ".join(assistant_lines)
        prompt = f"""대화 히스토리:
{history_text}

사용자 요약:
- {user_block}

어시스턴트 요약:
- {assistant_block}

위 정보를 바탕으로 아직 해결되지 않은 쟁점이나 추가 질문을 bullet list로 1~3개 작성하세요. 근거가 없는 질문은 만들지 마세요."""
        if grad_text:
            prompt += f"""

[개선 지시]
{grad_text}"""
        content = self._call_model(prompt, tag="Summarizer-OpenQuestions")
        return _parse_bullet_list(content)

    def call(self, history: List[Dict[str, str]], grad: Any) -> str:
        grad_text = _format_grad_for_module(grad)
        history_text = _format_history_for_prompt(history)

        user_transcript = _role_transcript(history, "user")
        assistant_transcript = _role_transcript(history, "assistant")

        user_summary = self._summarize_role(user_transcript, "사용자", grad_text)
        assistant_summary = (
            self._summarize_role(assistant_transcript, "어시스턴트", grad_text)
            if assistant_transcript
            else []
        )

        open_questions = self._open_questions(
            history_text, user_summary, assistant_summary, grad_text
        )

        aggregated = {
            "user_summary": user_summary,
            "assistant_summary": assistant_summary,
            "open_questions": open_questions,
        }
        return json.dumps(aggregated, ensure_ascii=False)


def build(model_name: str, *, openai_client, **_) -> SummarizerSubModule_ver1:
    return SummarizerSubModule_ver1(model_name, openai_client)
