from typing import Any, Dict

from ...utils import _format_history_for_prompt, _log_submodule_io

MODULE_TYPE = "rebuttal"
MODULE_VERSION = "v1"


class RebuttalSubModule_ver1:
    def __init__(self, model: str, client) -> None:
        self.model = model
        self.openai = client
        self.sys = (
            "You are the Rebuttal sub-module for a conversational debate assistant."
            "Speak in natural, friendly Korean whenever the dialogue is Korean, like a respectful teammate who still pushes back with evidence."
            "Craft concise, good-faith counterarguments that acknowledge the user's points, bring new evidence, and stay civil."
            "Always produce JSON with keys `rebuttal` and `references`."
        )

    def call(self, history, summary, grad):
        convo = _format_history_for_prompt(history)
        summary_text = summary if summary else "요약 정보가 제공되지 않았습니다."
        user_prompt = f"""대화 히스토리:
{convo}

요약:
{summary_text}

"""
        user_prompt += (
            "위 정보를 종합해 자연스럽고 대화체에 가까운 반박문을 작성하세요. 상대의 말을 인정하면서도 필요한 근거는 분명히 제시합니다.\n"
            "반박문은 3~5문장 이내로 간결하게 작성하세요.\n"
            'JSON {"rebuttal": "...", "references": [{"title": "...", "url": "..."}]} 로 출력합니다.\n'
            "근거는 실제로 알려진 사실·통계를 우선 사용하고, 확실하지 않으면 그 사실이 추정임을 명시하세요."
        )
        if grad:
            user_prompt += f"""

[개선 지시]
{grad}"""
        rsp = self.openai.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.sys},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = rsp.choices[0].message.content.strip()
        _log_submodule_io("Rebuttal", user_prompt, content, self.__class__.__name__, self.model)
        data = self._parse_structured_response(content)
        rebuttal = data.get("rebuttal", content).strip()
        refs = self._normalize_refs(data.get("references", []))
        return {"txt": rebuttal, "ref": refs}

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

    @staticmethod
    def _normalize_refs(refs) -> Dict[str, str]:
        normalized: Dict[str, str] = {}
        if isinstance(refs, dict):
            refs_iter = [refs]
        elif isinstance(refs, list):
            refs_iter = refs
        else:
            refs_iter = []
        for item in refs_iter:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("name")
            url = item.get("url") or item.get("link")
            if title and url:
                normalized[str(title)] = str(url)
        return normalized


def build(model_name: str, *, openai_client, **_):
    return RebuttalSubModule_ver1(model_name, openai_client)
