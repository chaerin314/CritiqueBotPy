import json
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Tuple

from .CriticModule_ver1 import CriticModule_ver1
from ..utils import _test_mode_print

SUPPORTED_MODEL_SHORTCUTS = [
    "gpt-5-chat-latest",
    "gpt-4o-mini",
    "gpt-5",
]

DEFAULT_EXPERIMENT_TEMPLATE = {
    "summarizer": {"version": "v1", "model": "gpt-4o-mini"},
    "rebuttal": {"version": "v2", "model": "gpt-5-chat-latest"},
    "judge": {"version": "v1", "model": "gpt-4o-mini"},
    "textgrad": {"version": "v1", "model": "gpt-4o-mini"},
}

PRESET_EXPERIMENTS = {
    "default": DEFAULT_EXPERIMENT_TEMPLATE,
    "budget": {
        "default_model": "gpt-4o-mini",
        "rebuttal": {"version": "v1"},
        "judge": {"version": "none"},
    },
    "max-grounding": {
        "default_model": "gpt-5",
        "rebuttal": {"version": "v2", "model": "gpt-5"},
    },
}


class CriticFactory:
    def __init__(self, openai_client, tavily_client, custom_presets: Dict[str, Any] = None) -> None:
        self.openai_client = openai_client
        self.tavily_client = tavily_client
        self.presets = dict(PRESET_EXPERIMENTS)
        if custom_presets:
            self.presets.update(custom_presets)
        self.builders = self._discover_module_builders()
        self.cache: Dict[str, Dict[str, Any]] = {}

    def _discover_module_builders(self) -> Dict[str, Dict[str, Any]]:
        registry: Dict[str, Dict[str, Any]] = {}
        base_path = Path(__file__).parent
        for path in base_path.rglob("*.py"):
            if path.name == "__init__.py":
                continue
            rel = path.relative_to(base_path).with_suffix("")
            module_name = ".".join((__name__, *rel.parts))
            module = import_module(module_name)
            module_type = getattr(module, "MODULE_TYPE", None)
            if not module_type:
                continue
            version = getattr(module, "MODULE_VERSION", path.stem)
            build_fn = getattr(module, "build", None)
            if not callable(build_fn):
                raise ValueError(f"{module_name} must expose callable build()")
            registry.setdefault(module_type, {})[version] = build_fn
        return registry

    def get_or_build(self, experiment=None):
        entry = self._get_entry(experiment)
        return entry["critic"]

    def describe(self, experiment=None) -> Tuple[Dict[str, Any], Dict[str, str]]:
        entry = self._get_entry(experiment)
        return entry["config"], entry["runtime_meta"]

    def _get_entry(self, experiment):
        config = self._normalize_experiment_config(experiment)
        key = json.dumps(config, sort_keys=True, ensure_ascii=False)
        if key not in self.cache:
            critic, runtime_meta = self._build_critic_from_config(config)
            self.cache[key] = {
                "critic": critic,
                "config": config,
                "runtime_meta": runtime_meta,
            }
        return self.cache[key]

    def _clone_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return json.loads(json.dumps(data, ensure_ascii=False))

    def _normalize_experiment_config(self, experiment) -> Dict[str, Any]:
        cfg = self._clone_config(DEFAULT_EXPERIMENT_TEMPLATE)
        if experiment is None:
            return cfg
        if isinstance(experiment, str):
            if experiment in self.presets:
                experiment = self._clone_config(self.presets[experiment])
            else:
                if experiment not in SUPPORTED_MODEL_SHORTCUTS:
                    _test_mode_print(f"[CritiqueBot] 알 수 없는 모델 별칭 '{experiment}', 기본 실험을 사용합니다.")
                    experiment = {}
                else:
                    experiment = {"default_model": experiment}
        elif isinstance(experiment, dict):
            experiment = self._clone_config(experiment)
        else:
            raise TypeError(f"Unsupported experiment config type: {type(experiment)}")

        default_model = experiment.pop("default_model", None)
        if default_model:
            for module in cfg:
                cfg[module]["model"] = default_model
        default_version = experiment.pop("default_version", None)
        if default_version:
            for module in cfg:
                cfg[module]["version"] = default_version

        module_models = experiment.pop("models", {}) or {}
        module_versions = experiment.pop("versions", {}) or {}
        module_overrides = experiment.pop("modules", {}) or {}
        for module in cfg:
            if module in module_models:
                cfg[module]["model"] = module_models[module]
            if module in module_versions:
                cfg[module]["version"] = module_versions[module]
            override = None
            if module in experiment:
                override = experiment[module]
            elif module in module_overrides:
                override = module_overrides[module]
            if override is not None:
                if isinstance(override, str):
                    cfg[module]["model"] = override
                elif isinstance(override, dict):
                    if "model" in override:
                        cfg[module]["model"] = override["model"]
                    if "version" in override:
                        cfg[module]["version"] = override["version"]
        for leftover in experiment.keys():
            if leftover not in cfg and leftover not in ("modules",):
                _test_mode_print(f"[CritiqueBot] 경고: 사용되지 않은 실험 키 {leftover}")
        return cfg

    def _build_critic_from_config(self, config: Dict[str, Any]):
        runtime_meta = {}
        modules = {}
        for module_name, module_cfg in config.items():
            builders = self.builders.get(module_name, {})
            version = module_cfg.get("version")
            builder = builders.get(version)
            if builder is None:
                available = ", ".join(builders.keys()) or "(none)"
                raise ValueError(
                    f"Unsupported {module_name} version '{version}'. 사용 가능: {available}"
                )
            instance = builder(
                module_cfg.get("model"),
                openai_client=self.openai_client,
                tavily_client=self.tavily_client,
            )
            modules[module_name] = instance
            runtime_meta[module_name] = {
                "class": instance.__class__.__name__,
                "model": module_cfg.get("model"),
            }
        critic = CriticModule_ver1(
            summarizer=modules["summarizer"],
            rebuttal=modules["rebuttal"],
            internal_judge=modules["judge"],
            text_grad=modules["textgrad"],
        )
        return critic, runtime_meta
