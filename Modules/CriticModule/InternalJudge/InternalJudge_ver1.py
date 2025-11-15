import json
from typing import Any, Dict, Tuple

from ...utils import _format_history_for_prompt, _log_submodule_io

MODULE_TYPE = "judge"
MODULE_VERSION = "v1"


class InternalJudge_ver1:
    def __init__(self, model: str, client) -> None:
        self.model = model
        self.openai = client
        self.pass_threshold = 90.0
        self.last_total_score = None
        self.sys = (
            "You are the Judge sub-module for a debate assistant."
            "Score the assistant's rebuttal across the values required for a constructive counterargument"
            " and provide actionable guidance."
        )
        self.metrics = (
            ("context_alignment", "사용자 주장과 히스토리를 정확히 반영했는가"),
            ("evidence_quality", "사실·근거·출처가 정확하고 충분한가"),
            ("civility", "톤이 예의바르고 협력적인가"),
            ("actionability", "대화 진전을 위한 구체성이 있는가"),
        )

    def call(self, history, summary, rebuttal) -> Tuple[bool, Any, str]:
        convo = _format_history_for_prompt(history)
        summary_text = summary if summary else "요약 정보가 제공되지 않았습니다."
        if isinstance(rebuttal, dict):
            rebuttal_txt = rebuttal.get("txt") or json.dumps(rebuttal, ensure_ascii=False)
            references = rebuttal.get("ref") or {}
        else:
            rebuttal_txt = str(rebuttal)
            references = {}
        ref_str = "\n".join(f"- {title}: {url}" for title, url in references.items()) or "(참조 없음)"
        metric_desc = "\n".join(f"- {key}: {desc}" for key, desc in self.metrics)
        user_prompt = f"""대화 히스토리:
{convo}

요약:
{summary_text}

어시스턴트의 반박문:
{rebuttal_txt}

참조 링크:
{ref_str}

"""
        user_prompt += (
            "다음 평가 항목별로 0~25 점을 부여하고 (모두 합해 최대 100점), 총점을 계산하세요:\n"
            f"{metric_desc}\n"
            'JSON 형식: {"scores": {"context_alignment": number, "evidence_quality": number, "civility": number, "actionability": number}, "total_score": number(0-100), "feedback": "..."}.\n'
            "feedback에는 개선해야 할 구체적인 조치 2~3가지를 포함하세요."
        )
        rsp = self.openai.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.sys},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = rsp.choices[0].message.content.strip()
        _log_submodule_io("Judge", user_prompt, content, self.__class__.__name__, self.model)
        data = self._parse_structured_response(content)
        scores = data.get("scores") or {}
        if isinstance(scores, list):
            converted = {}
            for entry in scores:
                if isinstance(entry, dict):
                    name = entry.get("metric") or entry.get("name")
                    val = entry.get("score") or entry.get("value")
                    if name is not None and val is not None:
                        try:
                            converted[str(name)] = float(val)
                        except (TypeError, ValueError):
                            continue
            scores = converted
        elif isinstance(scores, dict):
            parsed = {}
            for k, v in scores.items():
                try:
                    parsed[str(k)] = float(v)
                except (TypeError, ValueError):
                    continue
            scores = parsed
        else:
            scores = {}
        total_score = data.get("total_score")
        try:
            total_score = float(total_score)
        except (TypeError, ValueError):
            total_score = sum(scores.values())
        self.last_total_score = total_score
        feedback = data.get("feedback", "").strip()
        passed = total_score >= self.pass_threshold
        return passed, rebuttal, feedback if feedback else None

    @staticmethod
    def _parse_structured_response(text: str) -> Dict[str, Any]:
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            trimmed = cleaned[3:]
            parts = trimmed.split("```", 1)
            cleaned = parts[0].strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            import json as _json

            return _json.loads(cleaned)
        except Exception:
            return {}


def build(model_name: str, *, openai_client, **_):
    return InternalJudge_ver1(model_name, openai_client)
