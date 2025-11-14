import streamlit as st


class StreamlitModule:
    def __init__(self, critic_module, evaluation_module=None):
        self.cm = critic_module
        self.em = evaluation_module
        
        # Initialize session state
        if "history" not in st.session_state:
            st.session_state.history = []
        if "conversation_started" not in st.session_state:
            st.session_state.conversation_started = False

    def run(self):
        # Title and description
        st.title("🤖 CritiqueBot")
        st.markdown("당신의 주장에 대한 반박과 평가를 받아보세요.")
        
        # Sidebar for configuration info
        with st.sidebar:
            st.header("설정")
            st.info("CritiqueBot과 대화를 시작하세요!")
            
            # Debug mode toggle
            debug_mode = st.checkbox("🔍 디버그 모드", value=st.session_state.get("debug_mode", False))
            st.session_state.debug_mode = debug_mode
            
            if st.button("🔄 대화 초기화", use_container_width=True):
                st.session_state.history = []
                st.session_state.conversation_started = False
                st.rerun()
        
        # Display conversation history
        self._display_history()
        
        # Main input area
        if not st.session_state.conversation_started:
            self._initial_input()
        else:
            self._conversation_input()
    
    def _display_history(self):
        """Display the conversation history"""
        if not st.session_state.history:
            return
        
        st.markdown("---")
        st.subheader("대화 기록")
        
        for idx, turn in enumerate(st.session_state.history):
            role = turn.get("role", "user")
            content = turn.get("content", "")
            
            if role == "user":
                with st.chat_message("user"):
                    st.write(content)
            else:
                with st.chat_message("assistant"):
                    st.write(content)
                    
                    # Display references only if available
                    refs = turn.get("ref", {}) or turn.get("references", {})
                    # Debug: show refs structure in test mode
                    if st.session_state.get("debug_mode", False):
                        with st.expander("🔍 참조 링크 디버그 정보"):
                            st.json({"refs_type": type(refs).__name__, "refs": refs})
                    
                    if refs:
                        # Handle both dict and list formats
                        ref_items = []
                        if isinstance(refs, dict):
                            ref_items = list(refs.items())
                        elif isinstance(refs, list):
                            for item in refs:
                                if isinstance(item, dict):
                                    title = item.get("title") or item.get("name", "제목 없음")
                                    url = item.get("url") or item.get("link", "")
                                    if url:
                                        ref_items.append((title, url))
                                elif isinstance(item, (str, tuple)):
                                    # Handle tuple or string format
                                    if isinstance(item, tuple) and len(item) == 2:
                                        ref_items.append(item)
                                    elif isinstance(item, str):
                                        # Try to parse string format
                                        continue
                        
                        if ref_items:
                            valid_refs = []
                            for title, url in ref_items:
                                # Clean and validate URL
                                if not title:
                                    title = "제목 없음"
                                if not url:
                                    continue  # Skip invalid entries silently
                                
                                # Ensure URL is a string
                                url = str(url).strip()
                                
                                # Skip if URL is empty or looks like plain text (not a URL)
                                if not url:
                                    continue
                                
                                # Filter out common non-URL patterns
                                invalid_patterns = [
                                    "대화", "요약", "히스토리", "반박", "주장", "근거",
                                    "없음", "정보", "내용", "결과", "검색"
                                ]
                                url_lower = url.lower()
                                if any(pattern in url_lower for pattern in invalid_patterns):
                                    continue  # Skip invalid entries silently
                                
                                # Check if it looks like a URL (has domain-like structure)
                                has_domain = "." in url and not url.startswith("/")
                                has_protocol = url.startswith(("http://", "https://"))
                                
                                if not has_domain and not has_protocol:
                                    continue  # Skip entries that don't look like URLs
                                
                                # Add protocol if missing but has domain
                                if has_domain and not has_protocol:
                                    url = f"https://{url}"
                                
                                # Validate URL format more strictly
                                from urllib.parse import urlparse
                                try:
                                    parsed = urlparse(url)
                                    if not parsed.scheme or not parsed.netloc:
                                        continue  # Skip invalid URLs silently
                                    
                                    # Additional validation: netloc should have a dot (domain)
                                    if "." not in parsed.netloc:
                                        continue
                                    
                                    # Store valid reference
                                    valid_refs.append((title, url))
                                except Exception:
                                    continue  # Skip on any parsing error
                            
                            # Display only valid references
                            if valid_refs:
                                st.markdown("**🔗 참조 링크:**")
                                for title, url in valid_refs:
                                    import html
                                    escaped_url = html.escape(url)
                                    escaped_title = html.escape(str(title))
                                    
                                    # Create clickable link
                                    st.markdown(
                                        f'<a href="{escaped_url}" target="_blank" rel="noopener noreferrer" style="text-decoration: none; color: #1f77b4; display: block; margin: 4px 0;">🔗 {escaped_title}</a>',
                                        unsafe_allow_html=True
                                    )
        
        st.markdown("---")
    
    def _initial_input(self):
        """Handle initial claim input"""
        st.subheader("새로운 주장 시작하기")
        
        with st.form("initial_claim_form", clear_on_submit=True):
            user_input = st.text_area(
                "당신의 주장을 입력하세요:",
                height=150,
                placeholder="예: 인공지능은 인간의 일자리를 대체할 것입니다.",
                key="initial_input"
            )
            submitted = st.form_submit_button("제출", use_container_width=True)
            
            # Form 제출 시 입력값 처리
            if submitted:
                input_text = user_input.strip() if user_input else ""
                if input_text:
                    st.session_state.pending_input = input_text
                    st.rerun()
        
        # session_state에 저장된 입력값이 있으면 처리
        if "pending_input" in st.session_state:
            input_text = st.session_state.pending_input
            del st.session_state.pending_input
            self._process_user_input(input_text)
    
    def _conversation_input(self):
        """Handle ongoing conversation input"""
        st.subheader("재반박 또는 새 주장 시작")
        
        # Action buttons
        _, col2 = st.columns([3, 1])
        
        with col2:
            if st.button("🆕 새 주장 시작", use_container_width=True):
                st.session_state.history = []
                st.session_state.conversation_started = False
                st.rerun()
        
        # Rebuttal input form
        with st.form("rebuttal_form", clear_on_submit=True):
            user_input = st.text_area(
                "당신의 재반박을 입력하세요:",
                height=150,
                placeholder="봇의 반박에 대한 재반박을 입력하세요.",
                key="rebuttal_input"
            )
            submitted = st.form_submit_button("💬 재반박 제출", use_container_width=True)
            
            # Form 제출 시 입력값 처리 (clear_on_submit=True이므로 제출 전에 확인)
            if submitted:
                # 입력값을 session_state에 저장 (clear_on_submit으로 지워지기 전)
                input_text = user_input.strip() if user_input else ""
                if input_text:
                    # 입력값을 session_state에 저장하고 처리
                    st.session_state.pending_input = input_text
                    st.rerun()
        
        # session_state에 저장된 입력값이 있으면 처리
        if "pending_input" in st.session_state:
            input_text = st.session_state.pending_input
            del st.session_state.pending_input
            self._process_user_input(input_text)
    
    def _process_user_input(self, user_input: str):
        """Process user input and get bot response"""
        # Add user message to history
        st.session_state.history.append({"role": "user", "content": user_input})
        st.session_state.conversation_started = True
        
        # Show loading indicator
        with st.spinner("봇이 반박을 생성하는 중..."):
            # Get bot response
            rsp = self.cm.call(st.session_state.history)
            
            # Extract response text and references
            if isinstance(rsp, dict):
                response_text = rsp.get("txt", "")
                refs = rsp.get("ref", {}) or rsp.get("references", {})
            else:
                response_text = str(rsp)
                refs = {}
            
            # Ensure refs is always a dict (even if empty)
            if not isinstance(refs, dict):
                if isinstance(refs, list):
                    # Convert list to dict if needed
                    refs_dict = {}
                    for item in refs:
                        if isinstance(item, dict):
                            title = item.get("title") or item.get("name", "제목 없음")
                            url = item.get("url") or item.get("link", "")
                            if title and url:
                                refs_dict[str(title)] = str(url)
                    refs = refs_dict
                else:
                    refs = {}
            
            # Debug: log references structure if debug mode is enabled
            if st.session_state.get("debug_mode", False):
                st.write(f"🔍 디버그: 받은 참조 링크 타입: {type(refs).__name__}, 내용: {refs}")
            
            # Add bot response to history with references (always include ref field)
            st.session_state.history.append({
                "role": "assistant",
                "content": response_text,
                "ref": refs  # Always include ref field, even if empty
            })
        
        # Rerun to display new messages
        st.rerun()

