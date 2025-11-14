#!/usr/bin/env python3
"""
Utility script: lists available module versions and writes readme.txt
with instructions for editing config.txt directly.
"""
import json
from pathlib import Path

from Modules.CriticModule import CriticFactory


def _default_module_map(factory: CriticFactory):
    modules = {}
    for module_name, builders in sorted(factory.builders.items()):
        default_version = sorted(builders.keys())[0]
        modules[module_name] = {"version": default_version, "model": "gpt-4o-mini"}
    return modules


def render_readme(factory: CriticFactory) -> str:
    lines = []
    lines.append("CritiqueBot Configuration Guide")
    lines.append("=" * 34)
    lines.append("")
    lines.append("1. 편집할 파일: config.txt")
    lines.append("2. `version` 항목에서 각 모듈의 version/model을 직접 지정하세요.")
    lines.append("3. EXP 입력 CSV의 첫 열(case_id)을 사용해 각 실험을 식별합니다.")
    lines.append("4. 아래 표는 현재 import된 모듈이 제공하는 버전 목록입니다.")
    lines.append("")
    for module_name, builders in sorted(factory.builders.items()):
        versions = ", ".join(sorted(builders.keys()))
        lines.append(f"- {module_name}: {versions}")
    lines.append("")
    sample = {
        "mode": "cli",
        "test_mode": True,
        "openai_api_key": "<YOUR_OPENAI_KEY>",
        "tavily_api_key": "<YOUR_TAVILY_KEY>",
        "version": {
            "default_model": "gpt-4o-mini",
            "modules": _default_module_map(factory),
        },
        "exp_module": {
            "input_csv": "EXP001/in.csv",
            "output_csv": "EXP001/out.csv",
            "config": "EXP001/exp_config.txt",
        },
    }
    lines.append("샘플 config (필요 부분을 복사해 사용하세요):")
    lines.append("```json")
    lines.append(json.dumps(sample, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("이 파일은 `python update.py` 실행 시 생성/갱신됩니다.")
    return "\n".join(lines)


def main():
    factory = CriticFactory(openai_client=None, tavily_client=None)
    readme_path = Path(__file__).with_name("readme.txt")
    readme_path.write_text(render_readme(factory), encoding="utf-8")
    print(f"[CritiqueBot] readme.txt updated with available module versions.")


if __name__ == "__main__":
    main()
