import json

from ...utils import _format_history_for_prompt, _log_submodule_io

MODULE_TYPE = "textgrad"
MODULE_VERSION = "v1"


class TextGradGenerator:
    def __init__(self, model: str, client) -> None:
        self.model = model
        self.openai = client
        self.sys = (
            "You analyze judge diagnostics and propose targeted adjustments for"
            " debate sub-modules (Summarizer/Rebuttal)."
            "Deliver concise numbered steps in Korean when appropriate."
        )

    def ga(self, history, summary, rebuttal, feedback):
        convo = _format_history_for_prompt(history)
        summary_text = summary or "요약 정보가 비어 있습니다."
        if isinstance(rebuttal, dict):
            rebuttal_text = rebuttal.get("txt") or json.dumps(rebuttal, ensure_ascii=False)
        else:
            rebuttal_text = str(rebuttal)
        feedback_text = feedback or "내부 심사 피드백이 없지만, 명확성/근거/톤을 개선하세요."
        user_prompt = f"""대화 히스토리:
{convo}

현재 요약:
{summary_text}

현재 반박:
{rebuttal_text}

내부 심사 피드백:
{feedback_text}

"""
        user_prompt += (
            "Summarizer와 Rebuttal 모듈이 다음 시도에서 개선해야 할 2~3개의 구체적 지침을 번호 목록으로 작성하세요.\n"
            "Summarizer 지침과 Rebuttal 지침을 분리해 주세요.\n"
            'JSON 형식: {"summarizer_grad": ["..."], "rebuttal_grad": ["..."]}'
        )
        rsp = self.openai.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.sys},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = rsp.choices[0].message.content.strip()
        _log_submodule_io("TextGrad", user_prompt, content, self.__class__.__name__, self.model)
        return self._parse_grad_response(content)

    @staticmethod
    def _parse_grad_response(text):
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            trimmed = cleaned[3:]
            parts = trimmed.split("```", 1)
            cleaned = parts[0].strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            import json as _json

            data = _json.loads(cleaned)
        except Exception:
            return {}

        def _ensure_list(val):
            if not val:
                return []
            if isinstance(val, str):
                return [val]
            if isinstance(val, list):
                cleaned_items = []
                for item in val:
                    item_str = str(item).strip()
                    if item_str:
                        cleaned_items.append(item_str)
                return cleaned_items
            return [str(val).strip()]

        return {
            "summarizer_grad": _ensure_list(data.get("summarizer_grad")),
            "rebuttal_grad": _ensure_list(data.get("rebuttal_grad")),
        }


def build(model_name: str, *, openai_client, **_):
    return TextGradGenerator(model_name, openai_client)
