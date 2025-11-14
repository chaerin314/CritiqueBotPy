"""
Streamlit 웹 애플리케이션 진입점
실행 방법: streamlit run app.py
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from Modules.utils import ensure_packages, load_config, set_test_mode

# 필요한 패키지 확인 및 설치
ensure_packages(["openai", "tavily", "streamlit"])

# Streamlit import (ensure_packages 이후)
import streamlit as st

from openai import OpenAI
from tavily import TavilyClient

from Modules.StreamlitModule import StreamlitModule
from Modules.CriticModule import CriticFactory


def load_clients(config: dict):
    """API 클라이언트 로드"""
    openai_key = config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        st.error("❌ OPENAI_API_KEY가 config.txt 또는 환경변수에 설정되어야 합니다.")
        st.stop()

    tavily_key = config.get("tavily_api_key") or os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        st.error("❌ TAVILY_API_KEY가 필요합니다. config.txt 또는 환경변수에 추가하세요.")
        st.stop()

    openai_client = OpenAI(api_key=openai_key)
    tavily_client = TavilyClient(api_key=tavily_key)
    return openai_client, tavily_client


def format_summary(config, runtime_meta):
    """설정 요약 포맷팅"""
    cfg_summary = {module: f"{cfg['version']}@{cfg['model']}" for module, cfg in config.items()}
    runtime_summary = {
        module: f"{meta['class']}({meta['model']})" for module, meta in runtime_meta.items()
    }
    return cfg_summary, runtime_summary


def _resolve_config_path(arg_path: str) -> Path:
    """설정 파일 경로 해석"""
    candidate = Path(arg_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (Path(__file__).parent / candidate).resolve()


# 메인 애플리케이션
def main():
    # 설정 로드
    config_path = _resolve_config_path("config.txt")
    
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        st.error(f"❌ 설정 파일을 찾을 수 없습니다: {config_path}")
        st.stop()
    except Exception as e:
        st.error(f"❌ 설정 파일 로드 오류: {e}")
        st.stop()
    
    # 테스트 모드 설정
    test_mode_flag = bool(config.get("test_mode", False))
    set_test_mode(test_mode_flag)
    
    # API 클라이언트 로드
    try:
        openai_client, tavily_client = load_clients(config)
    except Exception as e:
        st.error(f"❌ API 클라이언트 로드 오류: {e}")
        st.stop()
    
    # CriticFactory 초기화
    factory = CriticFactory(
        openai_client=openai_client,
        tavily_client=tavily_client,
        custom_presets=config.get("experiment_presets"),
    )
    
    # 버전 설정
    version_override = config.get("version")
    try:
        critic = factory.get_or_build(version_override)
        cfg_summary, runtime_summary = format_summary(*factory.describe(version_override))
        
        # 사이드바에 구성 정보 표시
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 시스템 구성")
            st.json(cfg_summary)
            st.markdown("### 런타임 모듈")
            st.json(runtime_summary)
    except Exception as e:
        st.error(f"❌ Critic 모듈 초기화 오류: {e}")
        st.stop()
    
    # Streamlit 모듈 실행
    streamlit_module = StreamlitModule(critic_module=critic, evaluation_module=None)
    streamlit_module.run()


# Streamlit 앱 실행
# streamlit run app.py로 실행할 때 자동으로 main()이 호출됩니다
main()

