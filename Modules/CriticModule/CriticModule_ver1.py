from ..utils import SUBMODULE_PROGRESS_LOGGER, _test_mode_print


class CriticModule_ver1:
    def __init__(self, summarizer, rebuttal, internal_judge, text_grad):
        # Summarize -> Rebut (-> Internal judging)
        self.s = summarizer
        self.r = rebuttal
        self.ij = internal_judge
        self.tg = text_grad

    def _extract_grad(self, grad, key):
        if isinstance(grad, dict):
            return grad.get(key)
        return grad

    def _label(self, loop_label, name):
        if SUBMODULE_PROGRESS_LOGGER.single_line:
            return name
        return f"{loop_label} {name}"

    def call(self, history, max_loop=5):
        grad = None
        for loop_idx in range(max_loop):
            loop_no = loop_idx + 1
            _test_mode_print(
                f"""
[CritiqueBot] ===== Loop {loop_no} 시작 ====="""
            )
            loop_label = f"Loop {loop_no}"

            summ_grad = self._extract_grad(grad, "summarizer_grad")
            _test_mode_print(f"[CritiqueBot] Summarizer 호출 (grad 제공 여부: {bool(summ_grad)})")
            SUBMODULE_PROGRESS_LOGGER.prepare(3)
            with SUBMODULE_PROGRESS_LOGGER.step(self._label(loop_label, "Summarizer")):
                smry = self.s.call(history, summ_grad)
            _test_mode_print(
                f"""[CritiqueBot] Summarizer 결과:
{smry}"""
            )

            rbtl_grad = self._extract_grad(grad, "rebuttal_grad")
            _test_mode_print("[CritiqueBot] Rebuttal 호출")
            with SUBMODULE_PROGRESS_LOGGER.step(self._label(loop_label, "Rebuttal")):
                rbtl = self.r.call(history, smry, rbtl_grad)
            _test_mode_print(
                f"""[CritiqueBot] Rebuttal 결과:
{rbtl}"""
            )

            _test_mode_print("[CritiqueBot] Internal Judge 호출")
            with SUBMODULE_PROGRESS_LOGGER.step(self._label(loop_label, "Judge")):
                is_pass, rbtl, feedback = self.ij.call(history, smry, rbtl)
            _test_mode_print(f"[CritiqueBot] Internal Judge 결과 - 통과 여부: {is_pass}, 진단: {feedback}")
            if SUBMODULE_PROGRESS_LOGGER.single_line:
                score = getattr(self.ij, "last_total_score", None)
                threshold = getattr(self.ij, "pass_threshold", None)
                if threshold is None:
                    score_text = "n.a."
                elif score is None:
                    score_text = f"n.a./{threshold:.0f}"
                else:
                    score_text = f"{score:.1f}/{threshold:.0f}"
                status = "Pass" if is_pass else "Fail"
                SUBMODULE_PROGRESS_LOGGER.append_token(f"{status} {score_text}")
            if is_pass:
                _test_mode_print("[CritiqueBot] 루프 종료 - 판정 통과")
                return rbtl

            _test_mode_print("[CritiqueBot] TextGrad 지침 생성")
            SUBMODULE_PROGRESS_LOGGER.extend(1)
            with SUBMODULE_PROGRESS_LOGGER.step(self._label(loop_label, "TextGrad")):
                grad = self.tg.ga(history, smry, rbtl, feedback)
            _test_mode_print(
                f"""[CritiqueBot] TextGrad 결과:
{grad}"""
            )

        _test_mode_print("[CritiqueBot] 최대 루프 도달 - 마지막 반박 반환")
        return rbtl
