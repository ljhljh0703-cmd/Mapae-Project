"""
Mapae (마패) - AI Powered Game Policy Auditor
==============================================

Main Streamlit Application

This is the main entry point for the Mapae application, which provides
automated compliance analysis for game developers targeting multiple app stores.

Features:
- Hybrid analysis engine (Fast/Precision modes)
- Multi-market policy compliance (Google Play, App Store, Toss)
- Real-time analysis with AI-powered insights
- PDF and Markdown report generation

Architecture:
User -> Streamlit UI -> MapaeInput -> MapaeJudge -> Gemini/NotebookLM -> Results

Author: Portfolio Project
License: MIT
Version: 1.0.0
"""

import streamlit as st
from mapae_input import MapaeInput
from mapae_judge import MapaeJudge
from config_loader import Config
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from datetime import datetime


# Load configuration
config = Config()

# Page configuration
st.set_page_config(
    page_title="마패 - 범용 게임 심의 진단 솔루션",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Dark Navy & Gold theme
st.markdown("""
<style>
    /* Main theme colors */
    :root {
        --primary-navy: #1a2332;
        --accent-gold: #d4af37;
        --success-green: #28a745;
        --warning-orange: #ffc107;
        --danger-red: #dc3545;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #1a2332 0%, #2d3e50 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .main-title {
        color: #d4af37 !important;
        font-size: 2.5rem;
        font-weight: bold;
        margin: 0;
        text-align: center;
    }
    
    .main-subtitle {
        color: #ffffff !important;
        font-size: 1.2rem;
        text-align: center;
        margin-top: 0.5rem;
    }
    
    /* Verdict badges */
    .verdict-badge {
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        font-size: 1.3rem;
        font-weight: bold;
        text-align: center;
    }
    
    .verdict-pass {
        background-color: #d4edda;
        color: #155724;
        border: 2px solid #28a745;
    }
    
    .verdict-warning {
        background-color: #fff3cd;
        color: #856404;
        border: 2px solid #ffc107;
    }
    
    .verdict-reject {
        background-color: #f8d7da;
        color: #721c24;
        border: 2px solid #dc3545;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #1a2332;
    }
    
    [data-testid="stSidebar"] .sidebar-content {
        color: #ffffff;
    }
    
    /* Force all sidebar text to be white */
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    
    /* Sidebar headers */
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] h5,
    [data-testid="stSidebar"] h6 {
        color: #ffffff !important;
    }
    
    /* Sidebar paragraphs and text */
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] li,
    [data-testid="stSidebar"] label {
        color: #ffffff !important;
    }
    
    /* Sidebar markdown content */
    [data-testid="stSidebar"] .stMarkdown {
        color: #ffffff !important;
    }
    
    /* Button styling */
    .stButton > button {
        background-color: #d4af37;
        color: #1a2332;
        font-weight: bold;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 5px;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        background-color: #c19b2f;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(212, 175, 55, 0.3);
    }
</style>
""", unsafe_allow_html=True)


def render_sidebar():
    """Render the sidebar with branding and usage guide. Returns precision mode setting."""
    with st.sidebar:
        # Logo and branding
        st.markdown("""
        <div style='text-align: center; padding: 1rem;'>
            <h1 style='color: #d4af37; font-size: 2.5rem; margin: 0;'>🎮</h1>
            <h2 style='color: #d4af37; margin: 0.5rem 0;'>마패 (Mapae)</h2>
            <p style='color: #ffffff; font-size: 0.9rem;'>범용 심의 진단 도구</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Usage guide
        st.markdown("### 📖 사용 가이드")
        st.markdown("""
        **마패에 오신 것을 환영합니다!**
        
        이 도구는 게임 개발자가 제출 전에 잠재적인 정책 문제를 진단하는 데 도움을 줍니다.
        
        **사용 방법:**
        1. 게임 정보를 입력하세요
        2. 기획서를 업로드하거나 텍스트를 붙여넣으세요
        3. "분석하기" 버튼을 클릭하여 즉시 진단받으세요
        4. 각 플랫폼별 결과를 검토하세요
        5. 전문 보고서를 내보내세요
        
        **지원 플랫폼:**
        - ✅ 구글 플레이 스토어
        - ✅ 애플 앱스토어
        - ✅ 토스 플랫폼
        """)
        
        st.divider()
        
        # Analysis Mode Selection
        st.markdown("### ⚡ 분석 모드")
        
        use_precision_mode = st.checkbox(
            "✅ 정밀 검사 모드 (NotebookLM 연동)",
            value=False,
            help="기본: 빠른 Gemini 3.0 Flash API 사용 (일반 마켓 정책)\n체크: NotebookLM 브라우저 자동화로 심층 분석 (사내 규정 등 비공개 데이터)"
        )
        
        if use_precision_mode:
            st.info("🔬 정밀 검사 모드: NotebookLM 브라우저 자동화 활성화 (느림)")
        else:
            st.success("⚡ 빠른 모드: Gemini 3.0 Flash API 사용 (권장)")
        
        st.divider()
        
        # Configuration status
        st.markdown("### 🔑 설정 상태")
        
        api_key = config.get('GOOGLE_API_KEY')
        
        if api_key:
            st.success("✅ API 키 설정 완료")
        else:
            st.error("❌ API 키 미설정")
            st.info("💡 `config.txt` 파일에서 GOOGLE_API_KEY를 설정하세요")
        
        st.divider()
        
        # Portfolio info
        st.markdown("""
        <div style='text-align: center; color: #888; font-size: 0.8rem; margin-top: 2rem;'>
            <p>포트폴리오 프로젝트 2026</p>
            <p>Streamlit & Google AI 기반</p>
        </div>
        """, unsafe_allow_html=True)
        
        return use_precision_mode


def render_header():
    """Render the main header."""
    st.markdown("""
    <div class='main-header'>
        <h1 class='main-title'>마패: 범용 게임 심의 진단 솔루션</h1>
        <p class='main-subtitle'>게임 개발자를 위한 자동화된 정책 준수 분석</p>
    </div>
    """, unsafe_allow_html=True)


def render_verdict_badge(verdict: str, emoji: str):
    """Render a verdict badge with appropriate styling."""
    verdict_class = f"verdict-{verdict.lower()}"
    
    st.markdown(f"""
    <div class='verdict-badge {verdict_class}'>
        {emoji} {verdict}
    </div>
    """, unsafe_allow_html=True)


def render_analysis_results(results: dict, judge: MapaeJudge):
    """Render analysis results in tabbed layout."""
    st.markdown("## 📊 분석 결과")
    
    # Verdict system explanation
    st.info("""
    **📋 판정 시스템 안내**
    
    - ✅ **PASS**: 정책 준수, 문제 없음 - 현재 상태로 출시 가능
    - ⚠️ **WARNING**: 주의 필요, 일부 수정 권장 - 검토 후 출시 권장
    - ❌ **REJECT**: 정책 위반, 반드시 수정 필요 - 수정 없이 출시 불가
    - ❓ **UNKNOWN**: 판정 불가 - AI가 명확한 판정을 내리지 못한 경우
    - 🔴 **ERROR**: 분석 중 오류 발생 - 다시 시도해주세요
    """)
    
    st.divider()
    
    # Create tabs for each platform
    tab1, tab2, tab3 = st.tabs(["🟢 구글 플레이", "🍎 앱스토어", "💳 토스"])
    
    # Google Play tab
    with tab1:
        render_platform_report("구글 플레이 스토어", results["google"], judge)
    
    # App Store tab
    with tab2:
        render_platform_report("애플 앱스토어", results["apple"], judge)
    
    # Toss tab
    with tab3:
        render_platform_report("토스 플랫폼", results["toss"], judge)


def render_platform_report(platform_name: str, report: dict, judge: MapaeJudge):
    """Render a single platform's report."""
    if not report:
        st.warning(f"{platform_name}에 대한 분석 결과가 없습니다")
        return
    
    verdict = report.get("verdict", "UNKNOWN")
    emoji = judge.get_verdict_emoji(verdict)
    
    # Verdict badge
    render_verdict_badge(verdict, emoji)
    
    # Issues section
    st.markdown("### 🚨 발견된 문제점")
    issues = report.get("issues", [])
    
    if issues:
        for i, issue in enumerate(issues, 1):
            st.markdown(f"{i}. {issue}")
    else:
        st.success("문제점이 발견되지 않았습니다!")
    
    st.divider()
    
    # Recommendations section
    st.markdown("### 💡 권장사항")
    recommendations = report.get("recommendations", [])
    
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            st.markdown(f"{i}. {rec}")
    else:
        st.info("현재 특별한 권장사항이 없습니다.")
    
    # Raw report (expandable)
    with st.expander("📄 전체 보고서 보기"):
        st.text(report.get("raw_text", "상세 보고서가 없습니다."))


def generate_pdf_report(project_info: dict, results: dict, judge: MapaeJudge) -> bytes:
    """
    Generate PDF report of analysis results.
    
    Args:
        project_info: Project metadata
        results: Analysis results
        judge: Judge instance for formatting
        
    Returns:
        bytes: PDF file content
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor='#1a2332',
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor='#d4af37',
        spaceAfter=12
    )
    
    # Title
    story.append(Paragraph("마패 분석 보고서", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Project info
    story.append(Paragraph("프로젝트 정보", heading_style))
    story.append(Paragraph(f"<b>게임명:</b> {project_info['game_name']}", styles['Normal']))
    story.append(Paragraph(f"<b>장르:</b> {project_info['genre']}", styles['Normal']))
    story.append(Paragraph(f"<b>출시 예정 국가:</b> {', '.join(project_info['target_countries'])}", styles['Normal']))
    story.append(Paragraph(f"<b>보고서 작성일:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Platform reports
    platforms = [
        ("구글 플레이 스토어", results["google"]),
        ("애플 앱스토어", results["apple"]),
        ("토스 플랫폼", results["toss"])
    ]
    
    for platform_name, report in platforms:
        if not report:
            continue
            
        story.append(PageBreak())
        story.append(Paragraph(platform_name, heading_style))
        
        verdict = report.get("verdict", "UNKNOWN")
        story.append(Paragraph(f"<b>판정:</b> {verdict}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Issues
        story.append(Paragraph("<b>문제점:</b>", styles['Normal']))
        for issue in report.get("issues", []):
            story.append(Paragraph(f"• {issue}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Recommendations
        story.append(Paragraph("<b>권장사항:</b>", styles['Normal']))
        for rec in report.get("recommendations", []):
            story.append(Paragraph(f"• {rec}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_markdown_report(project_info: dict, results: dict) -> str:
    """
    Generate Markdown report for clipboard copy.
    
    Args:
        project_info: Project metadata
        results: Analysis results
        
    Returns:
        str: Markdown formatted report
    """
    md = f"""# 마패 분석 보고서

## 프로젝트 정보
- **게임명:** {project_info['game_name']}
- **장르:** {project_info['genre']}
- **출시 예정 국가:** {', '.join(project_info['target_countries'])}
- **보고서 작성일:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

"""
    
    platforms = [
        ("구글 플레이 스토어", results["google"]),
        ("애플 앱스토어", results["apple"]),
        ("토스 플랫폼", results["toss"])
    ]
    
    for platform_name, report in platforms:
        if not report:
            continue
            
        verdict = report.get("verdict", "UNKNOWN")
        md += f"## {platform_name}\n\n"
        md += f"**판정:** {verdict}\n\n"
        
        md += "### 문제점\n"
        for issue in report.get("issues", []):
            md += f"- {issue}\n"
        md += "\n"
        
        md += "### 권장사항\n"
        for rec in report.get("recommendations", []):
            md += f"- {rec}\n"
        md += "\n---\n\n"
    
    return md


def main():
    """Main application entry point."""
    # Initialize session state
    if 'analysis_complete' not in st.session_state:
        st.session_state['analysis_complete'] = False
    if 'results' not in st.session_state:
        st.session_state['results'] = None
    if 'project_info' not in st.session_state:
        st.session_state['project_info'] = None
    
    # Render UI and get precision mode setting
    use_precision_mode = render_sidebar()
    render_header()
    
    # Check API key from config
    api_key = config.get('GOOGLE_API_KEY')
    if not api_key:
        st.warning("⚠️ API 키가 설정되지 않았습니다. `config.txt` 파일을 확인하세요.")
        st.info("""
        **설정 방법:**
        1. 프로젝트 폴더의 `config.txt` 파일을 엽니다
        2. `GOOGLE_API_KEY=your-api-key-here` 부분을 수정합니다
        3. [Google AI Studio](https://makersuite.google.com/app/apikey)에서 API 키를 발급받아 입력합니다
        4. 파일을 저장하고 페이지를 새로고침합니다
        """)
        st.stop()
    
    # Initialize modules with precision mode from sidebar
    input_handler = MapaeInput()
    notebook_id = config.get('NOTEBOOKLM_NOTEBOOK_ID')
    
    judge = MapaeJudge(
        api_key=api_key,
        use_notebooklm=use_precision_mode,  # Use sidebar checkbox value
        notebook_id=notebook_id
    )
    
    # Input form
    is_ready = input_handler.render_input_form()
    
    st.divider()
    
    # Analysis button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        analyze_button = st.button(
            "🔍 게임 기획서 분석하기",
            disabled=not is_ready,
            use_container_width=True
        )
    
    # Perform analysis
    if analyze_button and is_ready:
        with st.spinner("🤖 플랫폼 정책에 따라 게임 기획서를 분석하고 있습니다..."):
            # Get contextualized prompt
            prompt = input_handler.get_contextualized_prompt()
            
            # Run analysis
            results = judge.analyze(prompt)
            
            # Store in session state
            st.session_state['analysis_complete'] = True
            st.session_state['results'] = results
            st.session_state['project_info'] = input_handler.get_project_info()
        
        st.success("✅ 분석 완료!")
        st.rerun()
    
    # Display results
    if st.session_state['analysis_complete'] and st.session_state['results']:
        st.divider()
        render_analysis_results(st.session_state['results'], judge)
        
        # Export options
        st.divider()
        st.markdown("## 📥 결과 내보내기")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # PDF download
            pdf_bytes = generate_pdf_report(
                st.session_state['project_info'],
                st.session_state['results'],
                judge
            )
            
            st.download_button(
                label="📄 PDF 보고서 다운로드",
                data=pdf_bytes,
                file_name=f"mapae_report_{st.session_state['project_info']['game_name'].replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        
        with col2:
            # Markdown copy
            md_report = generate_markdown_report(
                st.session_state['project_info'],
                st.session_state['results']
            )
            
            st.download_button(
                label="📋 마크다운으로 복사",
                data=md_report,
                file_name=f"mapae_report_{st.session_state['project_info']['game_name'].replace(' ', '_')}.md",
                mime="text/markdown",
                use_container_width=True
            )


if __name__ == "__main__":
    main()
