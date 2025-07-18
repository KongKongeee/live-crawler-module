
# 📺 실시간 방송 편성표 크롤러 (Live TV Schedule Crawler)

## 📖 프로젝트 개요

이 프로젝트는 **IPTV 추천 시스템의 핵심 데이터 파이프라인** 중 하나로, 실시간 TV 방송 편성표 데이터를 수집하고 정제하여 추천 모델의 기반 데이터를 구축하는 것을 목표로 합니다.

SK Broadband의 Btv 편성표를 기준으로 데이터를 수집하며, TMDB, Naver, Google Gemini API 등 외부 소스를 활용하여 각 프로그램의 장르, 줄거리, 출연진과 같은 풍부한 메타데이터를 보강합니다.

## ✨ 주요 기능

- **실시간 방송 편성표 크롤링**: 매일 주요 채널의 실시간 방송 스케줄 정보를 정확하게 수집합니다.
- **메타데이터 보강**: TMDB, Naver, Gemini API를 연동하여 프로그램의 상세 정보(장르, 줄거리, 포스터, 출연진 등)를 추가하여 데이터의 질을 높입니다.
- **자동화된 데이터 저장**: 수집 및 가공된 데이터를 날짜별, 채널별 `CSV` 파일로 자동 저장하여 데이터 관리 및 추적을 용이하게 합니다.
- **예외 처리**: `metadata_exceptions.json`을 통해 특정 프로그램에 대한 메타데이터를 수동으로 관리하여 데이터의 일관성과 정확성을 유지합니다.

## 🛠️ 기술 스택

- **Language**: `Python`
- **Data Handling**: `Pandas`
- **Crawling**: `Requests`, `BeautifulSoup4`
- **Configuration**: `python-dotenv`
- **APIs**: `TMDB API`, `Naver API`, `Google Gemini API`

## 📂 프로젝트 구조

```
live_crawler/
├── main.py             # 크롤러 실행 스크립트
├── requirements.txt    # 프로젝트 의존성 파일
├── .env                # API 키 및 환경 변수 설정 파일
├── lib/                # 핵심 로직 라이브러리
│   ├── config/         # 장르, 예외 처리 등 설정 파일
│   ├── metadata/       # TMDB, Naver, Gemini API 연동 모듈
│   └── utils/          # 텍스트 정제 등 유틸리티 함수
├── data_crawling_tmdb_gemini/ # 수집된 데이터(CSV)가 저장되는 디렉토리
└── README.md           # 프로젝트 소개 문서
```

## 🚀 설치 및 실행 방법

1.  **리포지토리 클론**
    ```bash
    git clone https://github.com/your-username/live-crawler.git
    cd live-crawler
    ```

2.  **의존성 설치**
    ```bash
    pip install -r requirements.txt
    ```

3.  **환경 변수 설정**
    `.env` 파일을 생성하고 아래와 같이 API 키를 입력합니다.
    ```
    TMDB_API_KEY="YOUR_TMDB_API_KEY"
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
    ```

4.  **크롤러 실행**
    ```bash
    python main.py
    ```

## 🔗 관련 프로젝트

이 프로젝트는 IPTV 추천 시스템 데이터 파이프라인의 일부입니다. TVING VOD 데이터 수집을 위한 **[tving-crawler](https://github.com/your-username/tving-crawler)** 프로젝트도 함께 확인해보세요.
