# Hidden Spot - AI 기반 맛집 큐레이션 서비스

네이버 지도 리뷰를 AI로 분석하여 심층적인 맛집 정보를 제공하는 서비스입니다. 이 프로젝트는 **FastAPI(Python) 백엔드**와 **Next.js(React) 프론트엔드**로 구성되어 있습니다.

## 📂 프로젝트 구조

```text
hidden-spot/
├── backend/          # Python FastAPI 서버 (리뷰 크롤링 및 AI 분석)
├── frontend/         # Next.js 프론트엔드 (UI 및 지도 연동)
├── spec.md           # 서비스 상세 기획서
└── supabase_schema.sql # 데이터베이스 초기 설정 스크립트
```

## 🚀 실행 방법

이 프로젝트는 두 개의 서버(백엔드, 프론트엔드)를 각각 별도로 실행해야 합니다.

### 1. 백엔드 (Python FastAPI)
백엔드는 가상 환경(`venv`)을 사용하여 종속성을 관리합니다. **`node_modules`를 사용하지 않습니다.**

```bash
cd backend
source venv/bin/activate    # 가상 환경 활성화 (Windows: venv\Scripts\activate)
pip install -r requirements.txt # (최초 1회) 필요한 패키지 설치
python3 main.py             # 서버 실행 (기본 포트: 8000)
```

### 2. 프론트엔드 (Next.js)
프론트엔드는 Node.js 환경에서 실행되며 **`node_modules`가 필요합니다.**

```bash
cd frontend
npm install                 # (최초 1회) 종속성 설치
npm run dev                 # 개발 서버 실행 (기본 포트: 3000)
```

## ⚠️ 주의 사항
- **Node.js 버전**: `v24.12.0` 사용을 권장합니다.
- **환경 변수**: `frontend/.env.local` 및 `backend/.env` 파일에 필요한 API 키가 설정되어 있는지 확인하세요.
- **경로**: 명령어를 실행할 때 반드시 해당 디렉토리(`backend` 또는 `frontend`)로 이동(`cd`)한 후 실행해야 합니다. 프로젝트 루트 폴더에서 직접 `npm` 명령어를 실행하면 `node_modules`를 찾지 못할 수 있습니다.

---
© 2026 Hidden Spot.
