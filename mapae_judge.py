"""
Mapae (마패) - AI Powered Game Policy Auditor
==============================================

AI Analysis Engine Module

This module contains the core AI analysis engine that powers Mapae's
policy compliance auditing capabilities.

Features:
- Dual-mode analysis (Gemini 3 Flash API / NotebookLM MCP)
- Intelligent response parsing with multi-platform support
- Robust error handling and fallback mechanisms
- Structured output generation for UI rendering

The MapaeJudge class handles:
1. AI model initialization and configuration
2. Prompt generation and context management
3. Response parsing and data extraction
4. Multi-platform report generation (Google/Apple/Toss)

Author: Portfolio Project
License: MIT
Version: 1.0.0
"""


import re
from typing import Dict, Optional, List
import google.generativeai as genai
import os
import subprocess
import json


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
        
        # Initialize Gemini 3 Flash Preview (latest stable model)
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-3-flash-preview')
        else:
            self.model = None
            
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
        Query Gemini AI with the prompt.
        
        Args:
            prompt: Analysis prompt
            
        Returns:
            str: Raw AI response
        """
        if not self.model:
            raise ValueError("AI 모델이 초기화되지 않았습니다. config.txt에서 GOOGLE_API_KEY를 설정해주세요.")
        
        # Generate response with safety settings
        response = self.model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.3,  # Lower temperature for more consistent analysis
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
            }
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
            results["google"] = self._parse_platform_report(google_match.group(1))
        
        if apple_match:
            results["apple"] = self._parse_platform_report(apple_match.group(1))
            
        if toss_match:
            results["toss"] = self._parse_platform_report(toss_match.group(1))
        
        # Fallback: if no delimiters found, create unified report
        if not any(results.values()):
            unified_report = self._parse_platform_report(raw_response)
            results["google"] = unified_report
            results["apple"] = unified_report
            results["toss"] = unified_report
            
        return results
    
    def _parse_platform_report(self, report_text: str) -> Dict:
        """
        Parse a single platform report into structured data.
        
        Args:
            report_text: Text of platform-specific report
            
        Returns:
            Dict: Structured report with verdict, issues, recommendations
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
        
        return {
            "verdict": verdict,
            "issues": issues,
            "recommendations": recommendations,
            "raw_text": report_text.strip()
        }
    
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
