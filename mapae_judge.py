"""
Mapae (마패) - AI Powered Game Policy Auditor
==============================================

AI Analysis Engine Module

This module contains the core AI analysis engine that powers Mapae's
policy compliance auditing capabilities.

Features:
- Dual-mode analysis (Gemini 2.0 Flash API / NotebookLM MCP)
- Intelligent response parsing with multi-platform support
- Robust error handling and fallback mechanisms
- Structured output generation for UI rendering
- REJECT-Risk scoring (policy-based estimate, not real review data)
- Local RAG citation from stored policy snapshots

The MapaeJudge class handles:
1. AI model initialization and configuration
2. Prompt generation and context management
3. Response parsing and data extraction
4. Multi-platform report generation (Google/Apple/Toss)
5. Deterministic REJECT-Risk scoring per platform
6. Policy citation via local vector DB (if available)

Author: Portfolio Project
License: MIT
Version: 1.1.0
"""


import re
from typing import Dict, Optional, List
import os
import subprocess
import json

# Use new google-genai SDK (google-generativeai is deprecated as of 0.8.x)
try:
    from google import genai as _genai
    from google.genai import types as _genai_types
    _NEW_SDK = True
except ImportError:
    import google.generativeai as _genai_legacy  # type: ignore[import]
    _NEW_SDK = False


# Keyword → base risk score mapping (used for deterministic scoring)
_RISK_KEYWORDS: Dict[str, int] = {
    # Critical (25-35)
    "도박": 35, "gambling": 35, "카지노": 35, "베팅": 30, "배팅": 30,
    "미성년자": 32, "아동": 32, "청소년": 28, "minor": 32, "child safety": 35,
    "불법": 30, "illegal": 30, "금지": 25, "prohibited": 25,
    # High (18-25)
    "가챠": 25, "gacha": 25, "확률형": 25, "뽑기": 20, "랜덤박스": 22, "loot box": 22,
    "개인정보": 22, "privacy": 22, "데이터 수집": 20,
    "실제 돈": 25, "real money": 25, "현금": 20,
    "사기": 28, "fraud": 28, "기만": 22, "misleading": 22, "허위": 22,
    # Medium (10-18)
    "연령": 15, "age rating": 15, "심의": 12, "등급": 12,
    "인앱 결제": 12, "iap": 12, "구독": 10,
    "광고": 10, "ads": 10, "advertisement": 10,
    "위반": 15, "violation": 15,
    # Low (5-10)
    "수정": 5, "권장": 5, "주의": 7, "warning": 7,
}

# Platform-specific strictness multipliers
_PLATFORM_MULT: Dict[str, float] = {
    "apple": 1.15,   # App Store is stricter
    "google": 1.00,
    "toss": 0.90,    # Toss has narrower scope
}

# Verdict base ranges
_VERDICT_BASE: Dict[str, int] = {
    "PASS": 8,
    "WARNING": 38,
    "REJECT": 68,
    "UNKNOWN": 22,
    "ERROR": 22,
}
_VERDICT_CAP: Dict[str, int] = {
    "PASS": 30,
    "WARNING": 65,
    "REJECT": 97,
    "UNKNOWN": 50,
    "ERROR": 50,
}

RISK_DISCLAIMER = "⚠️ 정책 기반 추정 · 실 심사 데이터 아님 · 법률자문 아님"


class MapaeJudge:
    """
    AI judge for analyzing game design documents against platform policies.

    Supports:
    - Google Play Store policies
    - Apple App Store policies
    - Toss platform policies

    Uses NotebookLM MCP if available, otherwise falls back to Gemini.
    """

    def __init__(self, api_key: Optional[str] = None, use_notebooklm: bool = False, notebook_id: Optional[str] = None):
        """
        Initialize the judge with AI backend.

        Args:
            api_key: Google Generative AI API key (optional, can use env var)
            use_notebooklm: Whether to use NotebookLM MCP
            notebook_id: NotebookLM notebook ID for policy documents
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.use_notebooklm = use_notebooklm
        self.notebook_id = notebook_id

        # Initialize Gemini 2.0 Flash (stable fast model)
        self._model_name = "gemini-3.5-flash"
        if self.api_key:
            if _NEW_SDK:
                self._client = _genai.Client(api_key=self.api_key)
            else:
                _genai_legacy.configure(api_key=self.api_key)
                self._legacy_model = _genai_legacy.GenerativeModel(self._model_name)
            self.model = True  # sentinel: API key present
        else:
            self._client = None
            self.model = None

        # Optional RAG: load policy snapshots into local vector DB if available
        self.rag = None
        try:
            from policy_rag import PolicyRAG
            rag = PolicyRAG()
            rag.load_snapshots()
            self.rag = rag
        except Exception:
            pass
            
    def analyze(self, prompt: str) -> Dict[str, Dict]:
        """
        Analyze game design document against platform policies.
        
        Args:
            prompt: Contextualized prompt with game info and document
            
        Returns:
            Dict: Analysis results for each platform
            {
                "google": {"verdict": str, "issues": List, "recommendations": List},
                "apple": {...},
                "toss": {...}
            }
        """
        try:
            # Try NotebookLM MCP first if enabled
            if self.use_notebooklm and self.notebook_id:
                try:
                    raw_response = self._query_notebooklm(prompt)
                except Exception as e:
                    # Fallback to Gemini if NotebookLM fails
                    raw_response = self._query_gemini(prompt)
            else:
                # Use Gemini directly
                raw_response = self._query_gemini(prompt)
            
            # Parse the response into structured data
            parsed_results = self._parse_response(raw_response)
            
            return parsed_results
            
        except Exception as e:
            # Return error state
            return self._create_error_response(str(e))
    
    def _query_notebooklm(self, prompt: str) -> str:
        """
        Query NotebookLM MCP with the prompt.
        
        Args:
            prompt: Analysis prompt
            
        Returns:
            str: Raw NotebookLM response
        """
        try:
            # Call notebooklm-mcp-cli via subprocess
            cmd = [
                "npx", "-y", "notebooklm-mcp-cli",
                "query",
                "--notebook-id", self.notebook_id,
                "--question", prompt
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise Exception(f"NotebookLM CLI 오류: {result.stderr}")
            
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            raise Exception("NotebookLM 응답 시간 초과 (60초)")
        except FileNotFoundError:
            raise Exception("notebooklm-mcp-cli를 찾을 수 없습니다. npx가 설치되어 있는지 확인하세요.")
    
    def _query_gemini(self, prompt: str) -> str:
        """
        Query Gemini AI with the prompt using google-genai SDK.

        Args:
            prompt: Analysis prompt

        Returns:
            str: Raw AI response
        """
        if not self.model:
            raise ValueError("AI 모델이 초기화되지 않았습니다. config.txt에서 GOOGLE_API_KEY를 설정해주세요.")

        if _NEW_SDK:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=_genai_types.GenerateContentConfig(
                    temperature=0.3,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=8192,
                ),
            )
        else:
            response = self._legacy_model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 8192,
                },
            )

        return response.text
    
    def _parse_response(self, raw_response: str) -> Dict[str, Dict]:
        """
        Parse AI response into structured platform reports.
        
        Args:
            raw_response: Raw text from AI
            
        Returns:
            Dict: Structured analysis results
        """
        results = {
            "google": None,
            "apple": None,
            "toss": None
        }
        
        # Try to extract platform-specific reports
        google_match = re.search(
            r'\[GOOGLE_REPORT\](.*?)(?=\[APPLE_REPORT\]|\[TOSS_REPORT\]|$)',
            raw_response,
            re.DOTALL | re.IGNORECASE
        )
        
        apple_match = re.search(
            r'\[APPLE_REPORT\](.*?)(?=\[GOOGLE_REPORT\]|\[TOSS_REPORT\]|$)',
            raw_response,
            re.DOTALL | re.IGNORECASE
        )
        
        toss_match = re.search(
            r'\[TOSS_REPORT\](.*?)(?=\[GOOGLE_REPORT\]|\[APPLE_REPORT\]|$)',
            raw_response,
            re.DOTALL | re.IGNORECASE
        )
        
        # Parse each platform report
        if google_match:
            results["google"] = self._parse_platform_report(google_match.group(1), "google")

        if apple_match:
            results["apple"] = self._parse_platform_report(apple_match.group(1), "apple")

        if toss_match:
            results["toss"] = self._parse_platform_report(toss_match.group(1), "toss")

        # Fallback: if no delimiters found, create unified report
        if not any(results.values()):
            unified_report = self._parse_platform_report(raw_response, "google")
            results["google"] = unified_report
            results["apple"] = self._parse_platform_report(raw_response, "apple")
            results["toss"] = self._parse_platform_report(raw_response, "toss")
            
        return results
    
    def _parse_platform_report(self, report_text: str, platform_key: str = "unknown") -> Dict:
        """
        Parse a single platform report into structured data.

        Args:
            report_text: Text of platform-specific report
            platform_key: Platform identifier for risk scoring (google/apple/toss)

        Returns:
            Dict: Structured report with verdict, issues, recommendations,
                  reject_risk score, and optional policy citation
        """
        # Extract verdict (support both English and Korean)
        verdict_match = re.search(
            r'(?:Verdict|판정):\s*(PASS|WARNING|REJECT)',
            report_text,
            re.IGNORECASE
        )
        verdict = verdict_match.group(1).upper() if verdict_match else "UNKNOWN"

        # Extract issues (support both English and Korean)
        issues_match = re.search(
            r'(?:Issues?|문제점):(.*?)(?=(?:Recommendations?|권장사항):|$)',
            report_text,
            re.DOTALL | re.IGNORECASE
        )
        issues_text = issues_match.group(1) if issues_match else ""
        issues = self._extract_list_items(issues_text)

        # Extract recommendations (support both English and Korean)
        rec_match = re.search(
            r'(?:Recommendations?|권장사항):(.*?)$',
            report_text,
            re.DOTALL | re.IGNORECASE
        )
        rec_text = rec_match.group(1) if rec_match else ""
        recommendations = self._extract_list_items(rec_text)

        # Deterministic REJECT-Risk score
        reject_risk = self._calculate_reject_risk(verdict, issues, platform_key)

        # Optional RAG citation
        policy_citation = None
        if self.rag and issues:
            try:
                policy_citation = self.rag.get_citation_for_issue(" ".join(issues[:3]))
            except Exception:
                pass

        return {
            "verdict": verdict,
            "issues": issues,
            "recommendations": recommendations,
            "raw_text": report_text.strip(),
            "reject_risk": reject_risk,
            "reject_risk_disclaimer": RISK_DISCLAIMER,
            "policy_citation": policy_citation,
        }

    def _calculate_reject_risk(self, verdict: str, issues: List[str], platform_key: str) -> int:
        """
        Compute REJECT-Risk score 0-100 deterministically.

        Algorithm:
        1. Start from verdict-based range base
        2. Add keyword-weighted issue severity (capped at +30)
        3. Apply platform strictness multiplier
        4. Clamp to verdict-specific ceiling

        NOTE: This is a policy-based ESTIMATE. Not derived from real review outcome data.
        """
        base = _VERDICT_BASE.get(verdict, 22)
        cap = _VERDICT_CAP.get(verdict, 50)

        issue_text = " ".join(issues).lower()
        keyword_bonus = 0
        for kw, score in _RISK_KEYWORDS.items():
            if kw.lower() in issue_text:
                keyword_bonus = min(keyword_bonus + score, 30)

        mult = _PLATFORM_MULT.get(platform_key, 1.0)
        raw = (base + keyword_bonus) * mult
        return max(0, min(int(raw), cap))
    
    def _extract_list_items(self, text: str) -> List[str]:
        """
        Extract list items from text (bullet points, numbered lists, etc.).
        
        Args:
            text: Text containing list items
            
        Returns:
            List[str]: Extracted items
        """
        items = []
        
        # Split by common list markers
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Remove common list markers
            line = re.sub(r'^[-*•]\s*', '', line)
            line = re.sub(r'^\d+\.\s*', '', line)
            
            # Skip if line is empty after removing markers
            if not line:
                continue
            
            # Filter out single meaningless characters (ㅇ, -, *, etc.)
            if len(line) <= 2 and line in ['ㅇ', '-', '*', '•', '.', ':', ';', '—', '_', '~', '=']:
                continue
            
            # Filter out lines that are only whitespace or single Korean consonants
            if line.strip() in ['ㅇ', 'ㄱ', 'ㄴ', 'ㄷ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅅ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']:
                continue
            
            # Filter out lines that are only dashes or underscores (—, __, etc.)
            if re.match(r'^[-_—=~]+$', line):
                continue
            
            # Filter out markdown headers (###, ##, etc.)
            if re.match(r'^#+$', line):
                continue
            
            # Only add lines with meaningful content (at least 2 characters)
            if len(line.strip()) >= 2:
                items.append(line)
        
        # If no items found, return the whole text as single item
        if not items and text.strip():
            # But only if it's not just a single meaningless character
            cleaned_text = text.strip()
            if len(cleaned_text) > 1 and not re.match(r'^[-_—=~ㅇ*•.#]+$', cleaned_text):
                items = [cleaned_text]
            
        return items
    
    def _create_error_response(self, error_message: str) -> Dict[str, Dict]:
        """
        Create error response structure.
        
        Args:
            error_message: Error description
            
        Returns:
            Dict: Error response for all platforms
        """
        error_report = {
            "verdict": "ERROR",
            "issues": [f"Analysis failed: {error_message}"],
            "recommendations": ["Please check your API key and try again."],
            "raw_text": f"Error: {error_message}"
        }
        
        return {
            "google": error_report,
            "apple": error_report,
            "toss": error_report
        }
    
    def get_verdict_emoji(self, verdict: str) -> str:
        """
        Get emoji representation for verdict.
        
        Args:
            verdict: Verdict string (PASS/WARNING/REJECT/ERROR)
            
        Returns:
            str: Emoji
        """
        emoji_map = {
            "PASS": "✅",
            "WARNING": "⚠️",
            "REJECT": "❌",
            "ERROR": "🔴",
            "UNKNOWN": "❓"
        }
        
        return emoji_map.get(verdict.upper(), "❓")
    
    def get_verdict_color(self, verdict: str) -> str:
        """
        Get color for verdict display.
        
        Args:
            verdict: Verdict string
            
        Returns:
            str: Color name for Streamlit
        """
        color_map = {
            "PASS": "green",
            "WARNING": "orange",
            "REJECT": "red",
            "ERROR": "red",
            "UNKNOWN": "gray"
        }
        
        return color_map.get(verdict.upper(), "gray")
