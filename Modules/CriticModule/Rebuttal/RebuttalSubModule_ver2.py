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
MODULE_VERSION = "v2"


class RebuttalSubModule_ver2:
    def __init__(
        self,
        model: str,
        client,
        tavily_client,
        max_queries: int = 3,
        top_k_per_query: int = 3,
        search_depth: str = "advanced",
    ) -> None:
        self.model = model
        self.openai = client
        self.tavily = tavily_client
        self.max_queries = max_queries
        self.top_k_per_query = top_k_per_query
        self.search_depth = search_depth
        self.sys = (
            "You are the Rebuttal sub-module for a conversational debate assistant."
            "Speak in a natural, friendly Korean tone when the dialogue is Korean, acknowledging the user's points while presenting evidence-backed counterarguments."
            "Only use the evidence provided (검색 결과 및 요약) and always produce JSON with keys `rebuttal` and `references`."
            "\n\n[SAFETY REQUIREMENTS]"
            "You must never generate harmful, unethical, or inappropriate content."
            "Do not produce content that promotes violence, hate speech, discrimination, or illegal activities."
            "Even when the user's claim is problematic, respond with respectful, evidence-based counterarguments that promote constructive dialogue."
            "If a user's claim is clearly harmful or unethical, acknowledge the concern diplomatically and redirect to constructive alternatives."
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

    def _generate_queries(self, convo: str, summary_text: str, grad_text: str) -> List[str]:
        prompt = (
            "당신은 토론 반박을 준비하는 리서치 전략가입니다."
            "주어진 대화와 요약을 읽고, 건전한 반박을 위해 추가로 조사해야 할 검색 질의를 1~3개 제안하세요."
            """JSON 형식: {"queries": ["..."]}."""
            "검색 질의는 사실 검증, 통계, 사례 등을 포함한 명확한 문장형 질문이어야 합니다."
            f"""

대화 히스토리:
{convo}

요약:
{summary_text}
"""
        )
        if grad_text:
            prompt += f"""

[개선 지시]
{grad_text}"""
        content = self._call_model(prompt, tag="Rebuttal-Queries")
        data = RebuttalSubModule_ver1._parse_structured_response(content)
        queries = data.get("queries")
        if isinstance(queries, str):
            queries = [queries]
        if not queries:
            queries = _parse_bullet_list(content)
        cleaned = []
        for q in queries or []:
            q = (q or "").strip()
            if q:
                cleaned.append(q)
            if len(cleaned) >= self.max_queries:
                break
        return cleaned

    def _search_with_tavily(self, query: str, loop_state: str) -> List[Dict[str, Any]]:
        loop_prefix = f"[CritiqueBot] Tavily 검색 {loop_state}: {query}"
        _test_mode_print(loop_prefix)
        try:
            resp = self.tavily.search(
                query, search_depth=self.search_depth, max_results=self.top_k_per_query
            )
        except Exception as exc:
            _test_mode_print(f"{loop_prefix} -> 실패: {exc}")
            return []
        hits = []
        for item in resp.get("results", [])[: self.top_k_per_query]:
            hits.append(
                {
                    "query": query,
                    "title": item.get("title") or item.get("url") or "출처 미상",
                    "url": item.get("url"),
                    "snippet": (item.get("content") or item.get("snippet") or item.get("excerpt") or "").strip(),
                }
            )
        if hits:
            _test_mode_print(f"{loop_prefix} -> {len(hits)}건 수집")
            for idx, hit in enumerate(hits, 1):
                _test_mode_print(
                    f"""  ({idx}) {hit['title']} | {hit['url']}
      요약: {hit['snippet']}"""
                )
        else:
            _test_mode_print(f"{loop_prefix} -> 결과 없음")
        return hits

    def _gather_evidence(self, queries: List[str]) -> List[Dict[str, Any]]:
        evidence: List[Dict[str, Any]] = []
        total = len(queries)
        for idx, query in enumerate(queries, 1):
            hits = self._search_with_tavily(query, f"{idx}/{total}")
            if hits:
                evidence.append({"query": query, "hits": hits})
        return evidence

    def _format_evidence_block(self, evidence) -> str:
        if not evidence:
            return "(검색 결과 없음)"
        lines = []
        for block in evidence:
            lines.append(f"[검색어] {block['query']}")
            for idx, hit in enumerate(block["hits"], 1):
                snippet = hit.get("snippet") or "(요약 없음)"
                lines.append(f"  - ({idx}) 제목: {hit['title']}")
                lines.append(f"    URL: {hit['url']}")
                lines.append(f"    요약: {snippet}")
        return "\n".join(lines)

    def _reference_pool(self, evidence) -> Dict[str, str]:
        refs: Dict[str, str] = {}
        for block in evidence:
            for hit in block["hits"]:
                title = hit.get("title")
                url = hit.get("url")
                if title and url and title not in refs:
                    refs[title] = url
        return refs

    def call(self, history, summary, grad):
        grad_text = _format_grad_for_module(grad)
        convo = _format_history_for_prompt(history)
        summary_text = summary if summary else "요약 정보가 제공되지 않았습니다."

        queries = self._generate_queries(convo, summary_text, grad_text)
        _test_mode_print(f"[CritiqueBot] 생성된 검색 질의: {queries}")
        evidence = self._gather_evidence(queries)
        evidence_block = self._format_evidence_block(evidence)
        ref_pool = self._reference_pool(evidence)

        user_prompt = f"""대화 히스토리:
{convo}

요약:
{summary_text}

검색 근거:
{evidence_block}

"""
        user_prompt += (
            "위 검색 근거와 대화 요약에 명시된 사실만 사용해 자연스럽고 친근한 반박문을 작성하세요. 상대의 주장도 짧게 인정한 뒤, 근거를 들며 차분히 반박하세요.\n"
            "반박문은 3~5문장 이내로 간결하게 작성하세요.\n"
            'JSON {"rebuttal": "...", "references": [{"title": "...", "url": "..."}]} 형식으로 출력하세요.\n'
            "각 근거가 어느 검색 결과에서 왔는지 문장 내에서 자연스럽게 언급하세요.\n"
            "\n[안전성 지침] 유해하거나 부적절한 내용은 절대 생성하지 마세요. 혐오 발언, 차별, 폭력 선동, 불법 행위를 조장하는 내용은 금지됩니다. 사용자의 주장이 문제가 있어도 예의바르고 건설적인 반박만 제공하세요."
        )
        if grad_text:
            user_prompt += f"""

[개선 지시]
{grad_text}"""

        content = self._call_model(user_prompt, tag="Rebuttal")
        data = RebuttalSubModule_ver1._parse_structured_response(content)
        rebuttal = data.get("rebuttal", content).strip()
        refs = RebuttalSubModule_ver1._normalize_refs(data.get("references", []))
        if not refs and ref_pool:
            refs = ref_pool
        return {"txt": rebuttal, "ref": refs}


def build(model_name: str, *, openai_client, tavily_client, **_):
    return RebuttalSubModule_ver2(model_name, openai_client, tavily_client)
