import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Modules.utils import ensure_packages, load_batch_config, set_test_mode

ensure_packages(["openai", "tavily"])

from openai import OpenAI
from tavily import TavilyClient

from Modules.CriticModule import CriticFactory
from Modules.EXPModule import EXPModule


def _load_clients(cfg):
    openai_key = cfg.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        raise RuntimeError("exp_config.txt 내 openai_api_key 또는 OPENAI_API_KEY 환경변수가 필요합니다.")
    tavily_key = cfg.get("tavily_api_key") or os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        raise RuntimeError("exp_config.txt 내 tavily_api_key 또는 TAVILY_API_KEY 환경변수가 필요합니다.")
    return OpenAI(api_key=openai_key), TavilyClient(api_key=tavily_key)


def main():
    exp_dir = Path(__file__).parent
    cfg_path = exp_dir / "exp_config.txt"
    general_cfg, runner_cfg = load_batch_config(cfg_path)

    set_test_mode(bool(general_cfg.get("test_mode")))
    openai_client, tavily_client = _load_clients(general_cfg)

    factory = CriticFactory(openai_client=openai_client, tavily_client=tavily_client)

    version_override = general_cfg.get("version")
    critic = factory.get_or_build(version_override)
    cfg_summary, runtime_summary = factory.describe(version_override)
    print("[CritiqueBot] (exp) 버전 구성:", cfg_summary)
    print("[CritiqueBot] (exp) 런타임 모듈:", runtime_summary)

    base_dir = Path(general_cfg["_config_dir"])
    input_csv = (base_dir / runner_cfg["input_csv"]).resolve()
    output_csv = (base_dir / runner_cfg["output_csv"]).resolve()

    if runner_cfg.get("default_version") is None:
        runner_cfg["default_version"] = version_override

    exp_runner = EXPModule(
        critic_factory=factory,
        exp_config=runner_cfg,
        input_csv=input_csv,
        output_csv=output_csv,
    )
    exp_runner.run()
    print(f"[CritiqueBot] EXP 완료: {output_csv}")


if __name__ == "__main__":
    main()
