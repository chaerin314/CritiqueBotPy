from typing import Any, Dict, List

from ...utils import (
    _format_grad_for_module,
    _format_history_for_prompt,
    _log_submodule_io,
    _parse_bullet_list,
    _test_mode_print,
)
from .RebuttalSubModule_ver1 import RebuttalSubModule_ver1

MODULE_TYPE = "rebuttal"
MODULE_VERSION = "base"


class RebuttalSubModule_Base:
    def __init__(
        self,
        model: str,
        client,
    ) -> None:
        self.model = model
        self.openai = client
        self.sys = (
            "You are the Rebuttal sub-module for a conversational debate assistant."
            "Speak in a natural, friendly Korean tone when the dialogue is Korean, acknowledging the user's points while presenting evidence-backed counterarguments."
            "Do not hallucinate. Always answer based on facts." 
            "Always produce JSON with keys `rebuttal` and `references`."
        )

    def _call_model(self, prompt: str, tag: str = "Rebuttal") -> str:
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

    def call(self, history, summary, grad):
        #grad_text = _format_grad_for_module(grad)
        convo = _format_history_for_prompt(history)
        #summary_text = summary if summary else "요약 정보가 제공되지 않았습니다."

        #queries = self._generate_queries(convo, summary_text, grad_text)
        #_test_mode_print(f"[CritiqueBot] 생성된 검색 질의: {queries}")
        #evidence = self._gather_evidence(queries)
        #evidence_block = self._format_evidence_block(evidence)
        #ref_pool = self._reference_pool(evidence)

        user_prompt = f"""대화 히스토리:
{convo}

"""
        user_prompt += (
            "위 대화 히스토리를 참고해 자연스럽고 친근한 반박문을 작성하세요. 상대의 주장도 짧게 인정한 뒤, 근거를 들며 차분히 반박하세요.\n"
            "반박문은 3~5문장 이내로 간결하게 작성하세요.\n"
            'JSON {"rebuttal": "...", "references": [{"title": "...", "url": "..."}]} 형식으로 출력하세요.'
            "근거 및 reference는 실제로 알려진 사실·통계를 기반으로 답하세요. 절대 환각하지 마세요."
            "특히 url의 환각에 더욱 주의하세요."
        )

        content = self._call_model(user_prompt, tag="Rebuttal")
        data = RebuttalSubModule_ver1._parse_structured_response(content)
        rebuttal = data.get("rebuttal", content).strip()
        refs = RebuttalSubModule_ver1._normalize_refs(data.get("references", []))
        return {"txt": rebuttal, "ref": refs}


def build(model_name: str, *, openai_client, **_):
    return RebuttalSubModule_Base(model_name, openai_client)
