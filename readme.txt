CritiqueBot Configuration Guide
==================================

1. 편집할 파일: config.txt
2. `version` 항목에서 각 모듈의 version/model을 직접 지정하세요.
3. EXP 입력 CSV의 첫 열(case_id)을 사용해 각 실험을 식별합니다.
4. 아래 표는 현재 import된 모듈이 제공하는 버전 목록입니다.

- judge: none, v1
- rebuttal: v1, v2
- summarizer: v1
- textgrad: v1

샘플 config (필요 부분을 복사해 사용하세요):
```json
{
  "mode": "cli",
  "test_mode": true,
  "openai_api_key": "<YOUR_OPENAI_KEY>",
  "tavily_api_key": "<YOUR_TAVILY_KEY>",
  "version": {
    "default_model": "gpt-4o-mini",
    "modules": {
      "judge": {
        "version": "none",
        "model": "gpt-4o-mini"
      },
      "rebuttal": {
        "version": "v1",
        "model": "gpt-4o-mini"
      },
      "summarizer": {
        "version": "v1",
        "model": "gpt-4o-mini"
      },
      "textgrad": {
        "version": "v1",
        "model": "gpt-4o-mini"
      }
    }
  },
  "exp_module": {
    "input_csv": "EXP001/in.csv",
    "output_csv": "EXP001/out.csv",
    "config": "EXP001/exp_config.txt"
  }
}
```

이 파일은 `python update.py` 실행 시 생성/갱신됩니다.