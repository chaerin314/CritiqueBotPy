import argparse
import os
from pathlib import Path

from Modules.utils import ensure_packages, load_config, load_exp_config, set_test_mode

ensure_packages(["openai", "tavily"])

from openai import OpenAI
from tavily import TavilyClient

from Modules.CLIModule import CLIModule
from Modules.CriticModule import CriticFactory
from Modules.EXPModule import EXPModule
from Modules.StreamlitModule import StreamlitModule


def parse_args():
    parser = argparse.ArgumentParser(description="CritiqueBot runner")
    parser.add_argument("--config", default="config.txt", help="경로 지정 (기본: config.txt)")
    parser.add_argument("--mode", choices=["cli", "exp", "streamlit"], help="실행 모드 강제 지정")
    parser.add_argument("--version", help="모듈 버전 구성(JSON 또는 프리셋 이름)")
    parser.add_argument("--experiment", help=argparse.SUPPRESS)
    parser.add_argument("--exp-dir", help="실험 CSV 디렉터리 (in/out/exp_config 포함)")
    parser.add_argument("--test-mode", action="store_true", help="TEST_MODE 강제 활성화")
    return parser.parse_args()


def load_clients(config: dict):
    openai_key = config.get("openai_api_key") #or os.environ.get("OPENAI_API_KEY")
    print(openai_key)
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY가 config.txt 또는 환경변수에 설정되어야 합니다.")

    tavily_key = config.get("tavily_api_key") or os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        raise RuntimeError("TAVILY_API_KEY가 필요합니다. config.txt 또는 환경변수에 추가하세요.")

    openai_client = OpenAI(api_key=openai_key)
    tavily_client = TavilyClient(api_key=tavily_key)
    return openai_client, tavily_client


def format_summary(config, runtime_meta):
    cfg_summary = {module: f"{cfg['version']}@{cfg['model']}" for module, cfg in config.items()}
    runtime_summary = {
        module: f"{meta['class']}({meta['model']})" for module, meta in runtime_meta.items()
    }
    return cfg_summary, runtime_summary


def resolve_exp_paths(config_dir: Path, exp_cfg: dict, override_dir: str = None):
    if override_dir:
        base = Path(override_dir)
        return {
            "input_csv": base / "in.csv",
            "output_csv": base / "out.csv",
            "config": base / "exp_config.txt",
        }
    return {
        "input_csv": config_dir / exp_cfg["input_csv"],
        "output_csv": config_dir / exp_cfg["output_csv"],
        "config": config_dir / exp_cfg["config"],
    }


def _resolve_config_path(arg_path: str) -> Path:
    candidate = Path(arg_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (Path(__file__).parent / candidate).resolve()


def main():
    args = parse_args()
    config_path = _resolve_config_path(args.config or "config.txt")
    config = load_config(config_path)
    mode = args.mode or config.get("mode", "cli")

    test_mode_flag = args.test_mode or bool(config.get("test_mode"))
    set_test_mode(test_mode_flag)

    openai_client, tavily_client = load_clients(config)
    factory = CriticFactory(
        openai_client=openai_client,
        tavily_client=tavily_client,
        custom_presets=config.get("experiment_presets"),
    )

    version_override = args.version or args.experiment or config.get("version")
    critic = factory.get_or_build(version_override)
    cfg_summary, runtime_summary = format_summary(*factory.describe(version_override))
    print("[CritiqueBot] 실험 구성:", cfg_summary)
    print("[CritiqueBot] 런타임 모듈:", runtime_summary)

    if mode == "cli":
        cli = CLIModule(critic_module=critic, evaluation_module=None)
        cli.run()
        return

    if mode == "streamlit":
        print("[CritiqueBot] Streamlit 모드는 app.py를 사용하세요:")
        print("  streamlit run app.py")
        print("\n또는 Python에서 직접 실행:")
        import streamlit.web.cli as stcli
        import sys
        sys.argv = ["streamlit", "run", "app.py"]
        stcli.main()
        return

    if mode == "exp":
        config_dir = Path(config["_config_dir"])
        exp_paths = resolve_exp_paths(config_dir, config["exp_module"], args.exp_dir)
        exp_config = load_exp_config(exp_paths["config"])
        if not exp_config.get("default_version"):
            exp_config["default_version"] = version_override
        exp_runner = EXPModule(
            critic_factory=factory,
            exp_config=exp_config,
            input_csv=exp_paths["input_csv"],
            output_csv=exp_paths["output_csv"],
        )
        exp_runner.run()
        print(f"[CritiqueBot] 실험 결과가 {exp_paths['output_csv']}에 저장되었습니다.")
        return

    raise ValueError(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
