# Mapae 설정 가이드

## 🔑 API 키 설정 방법

### 1단계: Google AI API 키 발급

1. [Google AI Studio](https://makersuite.google.com/app/apikey) 접속
2. "Create API Key" 클릭
3. API 키 복사

### 2단계: config.txt 파일 수정

프로젝트 폴더의 `config.txt` 파일을 열고 다음과 같이 수정:

```
GOOGLE_API_KEY=여기에_실제_API_키_붙여넣기
```

**예시:**
```
GOOGLE_API_KEY=***REMOVED_API_KEY***
```

### 3단계: 앱 새로고침

Streamlit 앱을 새로고침하면 자동으로 API 키가 로드됩니다.

---

## 📓 NotebookLM 연동 (선택사항)

NotebookLM을 사용하여 정책 문서 기반 분석을 원하는 경우:

### 1단계: NotebookLM Notebook 생성

1. [NotebookLM](https://notebooklm.google.com/) 접속
2. 새 노트북 생성
3. 정책 문서 업로드:
   - Google Play Store 정책 PDF
   - Apple App Store 리뷰 가이드라인 PDF
   - Toss 플랫폼 정책 문서

### 2단계: Notebook ID 확인

브라우저 URL에서 Notebook ID 복사:
```
https://notebooklm.google.com/notebook/YOUR_NOTEBOOK_ID_HERE
```

### 3단계: config.txt 수정

```
USE_NOTEBOOKLM=true
NOTEBOOKLM_NOTEBOOK_ID=여기에_노트북_ID_붙여넣기
```

### 4단계: npx 설치 확인

터미널에서 다음 명령어 실행:
```bash
npx -v
```

npx가 없다면 Node.js 설치:
```bash
brew install node
```

---

## ✅ 설정 확인

앱 사이드바의 **"🔑 설정 상태"** 섹션에서 확인:

- ✅ API 키 설정 완료 (녹색) → 정상
- ❌ API 키 미설정 (빨간색) → config.txt 확인 필요
- 📓 NotebookLM 활성화 → NotebookLM 사용 중

---

## 🔄 작동 방식

### Gemini 모드 (기본)
```
사용자 입력 → Gemini AI → 3개 플랫폼 분석 → 결과 표시
```

### NotebookLM 모드 (활성화 시)
```
사용자 입력 → NotebookLM (정책 문서 기반) → 3개 플랫폼 분석 → 결과 표시
                ↓ (실패 시)
              Gemini AI (자동 폴백)
```

---

## 🛠️ 문제 해결

### API 키 오류
```
❌ API 키 미설정
```
**해결:** config.txt에서 `GOOGLE_API_KEY=` 뒤에 실제 API 키 입력

### NotebookLM 오류
```
⚠️ NotebookLM 오류, Gemini로 전환
```
**해결:** 
- Notebook ID가 올바른지 확인
- npx가 설치되어 있는지 확인
- 인터넷 연결 확인
- 자동으로 Gemini로 폴백되므로 분석은 계속 진행됩니다

---

## 📝 config.txt 전체 예시

```
# Mapae Configuration File
# API 키를 여기에 입력하세요

# Google Generative AI API Key
# https://makersuite.google.com/app/apikey 에서 발급받으세요
GOOGLE_API_KEY=***REMOVED_API_KEY***

# NotebookLM MCP 설정 (선택사항)
# NotebookLM을 사용하려면 아래 설정을 활성화하세요
USE_NOTEBOOKLM=true
NOTEBOOKLM_NOTEBOOK_ID=abc123def456ghi789
```

---

## 🔒 보안 주의사항

- ⚠️ **config.txt 파일을 Git에 커밋하지 마세요!**
- `.gitignore`에 `config.txt` 추가 권장
- API 키는 절대 공개 저장소에 업로드하지 마세요
