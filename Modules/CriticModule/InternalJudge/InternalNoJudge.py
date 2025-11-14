MODULE_TYPE = "judge"
MODULE_VERSION = "none"


class InternalNoJudge:
    def __init__(self, model, client) -> None:
        self.model = model
        self.openai = client
        self.last_total_score = None
        self.pass_threshold = None

    def call(self, history, summary, rebuttal):
        return True, rebuttal, None


def build(model_name: str, *, openai_client, **_):
    return InternalNoJudge(model_name, openai_client)
