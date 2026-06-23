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
from mapae_judge import MapaeJudge, RISK_DISCLAIMER
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

# Design system: deep-blue brand + coral accent (6:3:1) · IBM Plex Sans KR · OKLCH tokens
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@300;400;500;600;700&family=JetBrains+Mono&display=swap');

:root {
    --bg:           oklch(98.5% 0.002 70);
    --surface:      oklch(100% 0 0);
    --ink:          oklch(14% 0.005 70);
    --ink-soft:     oklch(42% 0.012 70);
    --brand:        oklch(45% 0.12 250);
    --brand-strong: oklch(35% 0.13 250);
    --accent:       oklch(65% 0.18 25);
    --warn-color:   oklch(75% 0.15 75);
    --line:         oklch(91.5% 0.005 70);
    --radius:       14px;
}

/* Base */
html, body, [class*="css"], .stApp {
    font-family: 'IBM Plex Sans KR', sans-serif;
    color: var(--ink);
    word-break: keep-all;
}
.stApp { background: var(--bg); }
.block-container { max-width: 1100px; padding-top: 2.2rem; }
h1, h2, h3 { letter-spacing: -.01em; font-weight: 600; word-break: keep-all; }

/* Card */
.card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 18px 20px;
}

/* Header (clean, no gradient) */
.page-header { padding: 2rem 0 1.2rem; border-bottom: 1px solid var(--line); margin-bottom: 1.6rem; }
.page-title  { font-size: 1.7rem; font-weight: 700; color: var(--ink); margin: 0; letter-spacing: -.02em; }
.page-sub    { font-size: .9rem; color: var(--ink-soft); margin: .3rem 0 0; }

/* Verdict chips — PASS=brand, WARNING=warn, REJECT=accent(coral), border-only */
.verdict-chip {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: .85rem;
    font-weight: 600;
    letter-spacing: .01em;
    margin: .5rem 0 1rem;
}
.verdict-pass    { border: 1.5px solid var(--brand);      color: var(--brand); }
.verdict-warning { border: 1.5px solid var(--warn-color); color: var(--warn-color); }
.verdict-reject  { border: 1.5px solid var(--accent);     color: var(--accent); }
.verdict-unknown,
.verdict-error   { border: 1.5px solid var(--ink-soft);   color: var(--ink-soft); }

/* Button — brand deep blue, no shadow */
.stButton > button {
    background: var(--brand);
    color: #fff;
    border: 0;
    border-radius: 10px;
    font-weight: 600;
    font-family: 'IBM Plex Sans KR', sans-serif;
}
.stButton > button:hover { background: var(--brand-strong); }

/* KPI metric value */
[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace;
    color: var(--brand);
}

/* Sidebar — warm gray, border instead of shadow */
[data-testid="stSidebar"] {
    background: oklch(96% 0.003 70);
    border-right: 1px solid var(--line);
}
[data-testid="stSidebar"] * { color: var(--ink) !important; }
[data-testid="stSidebar"] .stCaption { color: var(--ink-soft) !important; }

/* Code / mono */
code, pre { font-family: 'JetBrains Mono', monospace; }

/* Progress bar — brand */
[data-testid="stProgress"] > div > div { background: var(--brand); }
</style>
""", unsafe_allow_html=True)


def render_sidebar():
    """Render the sidebar. Returns precision mode setting."""
    with st.sidebar:
        # Branding
        st.markdown("""
        <div style='padding:.8rem 0 1rem;'>
            <div style='font-size:1.15rem;font-weight:700;color:var(--ink);letter-spacing:-.01em;'>마패 (Mapae)</div>
            <div style='font-size:.8rem;color:var(--ink-soft);margin-top:3px;'>게임 정책 컴플라이언스 진단</div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Usage guide
        st.markdown("**사용 방법**")
        st.markdown("""
1. 게임 정보 입력
2. 기획서 업로드 또는 붙여넣기
3. 분석 실행
4. 플랫폼별 결과 검토
5. 보고서 내보내기

지원 플랫폼: Google Play · App Store · Toss
        """)

        st.divider()

        # Analysis mode
        st.markdown("**분석 모드**")
        use_precision_mode = st.checkbox(
            "정밀 검사 (NotebookLM 연동)",
            value=False,
            help="기본: Gemini 3.5 Flash 빠른 분석\n체크: NotebookLM 심층 분석 (느림)"
        )
        if use_precision_mode:
            st.caption("NotebookLM 모드 활성화")
        else:
            st.caption("Gemini 3.5 Flash 모드")

        st.divider()

        # API key status
        st.markdown("**설정 상태**")
        api_key = config.get('GOOGLE_API_KEY')
        if api_key:
            st.caption("API 키 설정됨")
        else:
            st.caption("API 키 미설정 — config.txt 확인")

        st.divider()

        # Policy update
        st.markdown("**정책 업데이트**")
        _render_policy_panel()

        st.divider()

        st.caption("포트폴리오 프로젝트 2026")

        return use_precision_mode


def _render_policy_panel():
    """Show policy snapshot status and optional refresh button in sidebar."""
    try:
        from policy_updater import SNAPSHOT_DIR, POLICY_SOURCES
        from pathlib import Path

        status_lines = []
        for key, src in POLICY_SOURCES.items():
            snap_dir = SNAPSHOT_DIR / key
            snaps = sorted(snap_dir.glob("*.txt"), reverse=True) if snap_dir.exists() else []
            if snaps:
                status_lines.append(f"✅ {src['name'][:12]}… ({snaps[0].stem})")
            else:
                status_lines.append(f"⬜ {src['name'][:12]}… (미수집)")

        for line in status_lines:
            st.caption(line)

        if st.button("🔄 정책 지금 업데이트", use_container_width=True,
                     help="공개 정책 페이지 3곳을 fetch하고 diff를 저장합니다 (10-20초)"):
            with st.spinner("정책 페이지 수집 중…"):
                from policy_updater import update_all_policies, get_changes_summary
                results = update_all_policies()
                summary = get_changes_summary(results)
            # Store for display on main area after sidebar closes
            st.session_state["policy_update_summary"] = summary
            st.rerun()

    except Exception as e:
        st.caption(f"정책 추적 모듈 오류: {e}")


def render_header():
    """Render the main header — clean, no gradient."""
    st.markdown("""
    <div class='page-header'>
        <div class='page-title'>마패 — 게임 정책 컴플라이언스 진단</div>
        <div class='page-sub'>Google Play · App Store · Toss 기준 자동 분석 &nbsp;·&nbsp; 정책 기반 추정 · 법률자문 아님</div>
    </div>
    """, unsafe_allow_html=True)


def render_verdict_badge(verdict: str, emoji: str):
    """Render a verdict chip — border only, no filled background."""
    chip_class = f"verdict-{verdict.lower()}"
    label = {"PASS": "PASS", "WARNING": "WARNING", "REJECT": "REJECT",
             "UNKNOWN": "UNKNOWN", "ERROR": "ERROR"}.get(verdict.upper(), verdict)
    st.markdown(f"<span class='verdict-chip {chip_class}'>{label}</span>",
                unsafe_allow_html=True)


def render_analysis_results(results: dict, judge: MapaeJudge):
    """Render analysis results in tabbed layout."""
    st.markdown("### 분석 결과")

    st.caption(
        "PASS — 정책 준수 &nbsp;·&nbsp; WARNING — 수정 권장 &nbsp;·&nbsp; REJECT — 출시 전 반드시 수정 &nbsp;·&nbsp; "
        "정책 기반 추정 · 실 심사 데이터 아님"
    )

    st.divider()

    tab1, tab2, tab3 = st.tabs(["Google Play", "App Store", "Toss"])
    
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

    # REJECT-Risk score
    reject_risk = report.get("reject_risk")
    if reject_risk is not None:
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.progress(reject_risk / 100)
        with col_b:
            st.markdown(
                f"<span style='font-family:JetBrains Mono,monospace;font-size:.95rem;"
                f"font-weight:600;color:var(--accent);'>{reject_risk}%</span>",
                unsafe_allow_html=True,
            )
        st.caption(report.get("reject_risk_disclaimer", RISK_DISCLAIMER))

    # Policy citation from local RAG
    citation = report.get("policy_citation")
    if citation:
        with st.expander("근거 인용 (로컬 정책 DB)"):
            st.caption(citation)

    st.divider()

    # Issues
    st.markdown("**발견된 문제점**")
    issues = report.get("issues", [])
    if issues:
        for i, issue in enumerate(issues, 1):
            st.markdown(f"{i}. {issue}")
    else:
        st.caption("문제점이 발견되지 않았습니다.")

    st.divider()

    # Recommendations
    st.markdown("**권장사항**")
    recommendations = report.get("recommendations", [])
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            st.markdown(f"{i}. {rec}")
    else:
        st.caption("권장사항 없음")

    # Raw report
    with st.expander("전체 원문 보기"):
        st.text(report.get("raw_text", "—"))


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
        textColor='#1b1a17',
        alignment=TA_CENTER,
        spaceAfter=30
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor='#2d4f8a',
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

    # Show policy update results if a refresh was just triggered
    if st.session_state.get("policy_update_summary"):
        st.markdown(st.session_state.pop("policy_update_summary"))
        st.divider()

    # Mandatory disclaimer banner
    st.caption(
        "이 도구는 공개 정책 기반 추정을 제공합니다. "
        "REJECT-Risk 스코어는 실 심사 데이터가 아니며 법률 자문이 아닙니다. "
        "제출 전 각 플랫폼 공식 정책을 직접 확인하세요."
    )
    
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
            "분석 실행",
            disabled=not is_ready,
            use_container_width=True
        )
    
    # Perform analysis
    if analyze_button and is_ready:
        with st.spinner("분석 중…"):
            # Get contextualized prompt
            prompt = input_handler.get_contextualized_prompt()
            
            # Run analysis
            results = judge.analyze(prompt)
            
            # Store in session state
            st.session_state['analysis_complete'] = True
            st.session_state['results'] = results
            st.session_state['project_info'] = input_handler.get_project_info()
        
        st.success("분석 완료")
        st.rerun()
    
    # Display results
    if st.session_state['analysis_complete'] and st.session_state['results']:
        st.divider()
        render_analysis_results(st.session_state['results'], judge)
        
        # Export options
        st.divider()
        st.markdown("### 내보내기")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # PDF download
            pdf_bytes = generate_pdf_report(
                st.session_state['project_info'],
                st.session_state['results'],
                judge
            )
            
            st.download_button(
                label="PDF 다운로드",
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
                label="Markdown 저장",
                data=md_report,
                file_name=f"mapae_report_{st.session_state['project_info']['game_name'].replace(' ', '_')}.md",
                mime="text/markdown",
                use_container_width=True
            )


if __name__ == "__main__":
    main()
