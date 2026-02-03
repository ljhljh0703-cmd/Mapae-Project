"""
Mapae (마패) - AI Powered Game Policy Auditor
==============================================

User Input Module

This module handles all user input collection including project information,
document uploads, and text paste functionality.

Features:
- Multi-format document support (PDF, DOCX, plain text)
- Project metadata collection (name, genre, target markets)
- Input validation and sanitization
- Contextualized prompt generation for AI analysis

The MapaeInput class provides:
1. Streamlit UI rendering for input forms
2. File upload and text extraction
3. Input validation and error handling
4. Prompt contextualization for AI engine

Author: Portfolio Project
License: MIT
Version: 1.0.0
"""


import streamlit as st
from typing import Dict, List, Optional
import PyPDF2
from docx import Document
import io


class MapaeInput:
    """
    Input handler for Mapae game review diagnostic system.
    
    Collects:
    - Project metadata (name, genre, target countries)
    - Game design documents (PDF/DOCX)
    - Direct text input
    """
    
    # Genre options for dropdown
    GENRES = [
        "액션",
        "어드벤처", 
        "RPG",
        "전략",
        "퍼즐",
        "캐주얼",
        "시뮬레이션",
        "스포츠",
        "레이싱",
        "격투",
        "호러",
        "기타"
    ]
    
    # Target country options
    COUNTRIES = [
        "대한민국",
        "미국",
        "일본",
        "중국",
        "글로벌",
        "유럽",
        "동남아시아",
        "기타"
    ]
    
    def __init__(self):
        """Initialize input handler."""
        self.project_info: Dict[str, any] = {}
        self.document_text: str = ""
        
    def render_input_form(self) -> bool:
        """
        Render the input form in Streamlit.
        
        Returns:
            bool: True if form is complete and ready for analysis
        """
        st.header("📋 프로젝트 정보")
        
        # Project metadata inputs
        col1, col2 = st.columns(2)
        
        with col1:
            game_name = st.text_input(
                "게임명 *",
                placeholder="예: 에픽 퀘스트 어드벤처",
                help="게임 제목을 입력하세요"
            )
            
        with col2:
            genre = st.selectbox(
                "장르 *",
                options=self.GENRES,
                help="주요 장르를 선택하세요"
            )
        
        target_countries = st.multiselect(
            "출시 예정 국가 *",
            options=self.COUNTRIES,
            default=["글로벌"],
            help="출시 예정인 모든 시장을 선택하세요"
        )
        
        # Store project info
        self.project_info = {
            "game_name": game_name,
            "genre": genre,
            "target_countries": target_countries
        }
        
        st.divider()
        
        # Document input section
        st.header("📄 게임 기획서")
        
        input_method = st.radio(
            "입력 방식",
            options=["파일 업로드", "텍스트 붙여넣기"],
            horizontal=True
        )
        
        if input_method == "파일 업로드":
            uploaded_files = st.file_uploader(
                "PDF 또는 DOCX 파일 업로드",
                type=["pdf", "docx"],
                accept_multiple_files=True,
                help="파일당 최대 크기: 10MB"
            )
            
            if uploaded_files:
                self.document_text = self._process_uploaded_files(uploaded_files)
                
                if self.document_text:
                    st.success(f"✅ {len(uploaded_files)}개 파일 처리 완료")
                    with st.expander("추출된 텍스트 미리보기"):
                        st.text_area(
                            "문서 내용",
                            value=self.document_text[:1000] + "..." if len(self.document_text) > 1000 else self.document_text,
                            height=200,
                            disabled=True
                        )
        else:
            self.document_text = st.text_area(
                "게임 기획서를 붙여넣으세요",
                height=300,
                max_chars=50000,
                placeholder="게임 기획서, 기능 설명, 수익화 계획 등을 붙여넣으세요...",
                help="최대 50,000자"
            )
        
        # Validation
        is_valid = self._validate_input()
        
        if not is_valid:
            st.warning("⚠️ 필수 항목(*)을 모두 입력하고 기획서 내용을 제공해주세요")
            
        return is_valid
    
    def _process_uploaded_files(self, uploaded_files: List) -> str:
        """
        Extract text from uploaded PDF/DOCX files.
        
        Args:
            uploaded_files: List of uploaded file objects
            
        Returns:
            str: Combined extracted text
        """
        combined_text = []
        
        for uploaded_file in uploaded_files:
            try:
                if uploaded_file.name.endswith('.pdf'):
                    text = self._extract_pdf_text(uploaded_file)
                elif uploaded_file.name.endswith('.docx'):
                    text = self._extract_docx_text(uploaded_file)
                else:
                    continue
                    
                combined_text.append(f"\n\n=== {uploaded_file.name} ===\n\n{text}")
                
            except Exception as e:
                st.error(f"Error processing {uploaded_file.name}: {str(e)}")
                
        return "\n".join(combined_text)
    
    def _extract_pdf_text(self, pdf_file) -> str:
        """
        Extract text from PDF file.
        
        Args:
            pdf_file: Uploaded PDF file object
            
        Returns:
            str: Extracted text
        """
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file.read()))
        text_parts = []
        
        for page in pdf_reader.pages:
            text_parts.append(page.extract_text())
            
        return "\n".join(text_parts)
    
    def _extract_docx_text(self, docx_file) -> str:
        """
        Extract text from DOCX file.
        
        Args:
            docx_file: Uploaded DOCX file object
            
        Returns:
            str: Extracted text
        """
        doc = Document(io.BytesIO(docx_file.read()))
        text_parts = []
        
        for paragraph in doc.paragraphs:
            text_parts.append(paragraph.text)
            
        return "\n".join(text_parts)
    
    def _validate_input(self) -> bool:
        """
        Validate that all required inputs are provided.
        
        Returns:
            bool: True if valid, False otherwise
        """
        # Check project info
        if not self.project_info.get("game_name"):
            return False
        if not self.project_info.get("genre"):
            return False
        if not self.project_info.get("target_countries"):
            return False
            
        # Check document content (minimum 10 characters)
        if not self.document_text or len(self.document_text.strip()) < 10:
            return False
            
        return True
    
    def get_contextualized_prompt(self) -> str:
        """
        Generate a contextualized prompt for the AI judge.
        
        Returns:
            str: Formatted prompt with context
        """
        context = f"""
게임 정보:
- 게임명: {self.project_info['game_name']}
- 장르: {self.project_info['genre']}
- 출시 예정 국가: {', '.join(self.project_info['target_countries'])}

이 게임은 {self.project_info['genre']} 장르이며 {', '.join(self.project_info['target_countries'])} 출시를 계획하고 있습니다.

게임 기획서:
{self.document_text}

---

위 게임 기획서를 구글 플레이 스토어, 애플 앱스토어, 토스 플랫폼의 정책에 따라 분석해주세요.
각 플랫폼별로 다음 구조로 보고서를 작성해주세요 (반드시 한글로 작성):

[GOOGLE_REPORT]
판정: PASS/WARNING/REJECT
문제점: (정책 위반 사항이나 우려사항 나열)
권장사항: (실행 가능한 해결 방법)

[APPLE_REPORT]
판정: PASS/WARNING/REJECT
문제점: (정책 위반 사항이나 우려사항 나열)
권장사항: (실행 가능한 해결 방법)

[TOSS_REPORT]
판정: PASS/WARNING/REJECT
문제점: (정책 위반 사항이나 우려사항 나열)
권장사항: (실행 가능한 해결 방법)

중요: 모든 분석 내용은 반드시 한글로 작성해주세요.
"""
        return context.strip()
    
    def get_project_info(self) -> Dict[str, any]:
        """
        Get collected project information.
        
        Returns:
            Dict: Project metadata
        """
        return self.project_info
    
    def get_document_text(self) -> str:
        """
        Get collected document text.
        
        Returns:
            str: Document content
        """
        return self.document_text
