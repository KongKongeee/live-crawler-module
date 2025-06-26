# 📺 LG U+ IPTV 프로그램 메타데이터 크롤링 시스템

LG U+ IPTV 채널 편성표를 기반으로 각 프로그램의 상세 정보를 수집하고, TMDb, NAVER, Gemini API를 통해 장르, 서브장르, 설명, 출연진, 썸네일, 시청 등급 등 메타데이터를 자동 추출하여 정제된 CSV로 저장하는 크롤링 시스템입니다.

---

## 📁 프로젝트 구조

```
IFITV_Crawler/
├── main.py                             # 메인 실행 파일
├── .env                                # API 키 환경변수
├── lib/
│   ├── config/
│   │   └── genre_config.py             # 장르/서브장르/키워드 설정 로딩
│   ├── json/
│   │   └── categories.json             # desc_keywords가 포함된 JSON 구조
│   └── utils/
│       └── text_cleaning.py            # 프로그램명 정제 등 텍스트 유틸
├── modules/
│   └── crawler.py                      # 병렬 크롤러 클래스
├── lib/
│   └── metadata/
│       ├── tmdb.py                     # TMDb 기반 메타데이터 추출
│       ├── naver.py                    # NAVER 웹/이미지 검색 및 출연진 추출
│       └── gemini.py                   # Google Gemini로 결측 메타데이터 보완
├── data_crawling_tmdb_gemini/         # 결과 CSV 저장 디렉토리
```

---

## ⚙️ 실행 환경

- Python 3.10+
- ChromeDriver
- `requirements.txt` 필수 라이브러리:
  - `selenium`
  - `requests`
  - `beautifulsoup4`
  - `pandas`
  - `python-dotenv`
  - `google-generativeai`

---

## 🔑 `.env` 구성

```env
TMDB_API_KEY=your_tmdb_key
GEMINI_API_KEY=your_gemini_key
```

---

## 🚀 실행 방법

```bash
python main.py
```

`main.py` 실행 시:

- `Crawler.run()`이 채널별 편성표를 순회하며 프로그램 정보를 수집
- TMDb → NAVER → Gemini 순으로 메타데이터 추출
- `lib/json/categories.json` 기반으로 서브장르 자동 분류
- 정제된 CSV를 `data_crawling_tmdb_gemini/` 디렉토리에 저장

---

## 🔍 메타데이터 추출 항목

| 항목    | 설명                                                                 |
| ----- | ------------------------------------------------------------------ |
| 프로그램명 | LG U+ 편성표 기준                                                       |
| 장르    | 드라마, 예능, 영화, 애니, 보도                                                |
| 서브장르  | 사용자 정의 기준에 따른 정제값                                                  |
| 설명    | TMDb + NAVER + Gemini 기반 요약                                        |
| 출연진   | NAVER 또는 Gemini 기반 한글화된 cast                                       |
| 썸네일   | TMDb 또는 NAVER 이미지 URL                                              |
| 시청등급  | 숫자값 정제: `12 → 12세 이상`, `15 → 15세 이상`, `19 → 19세 이상`, 누락 시 `전체 이용가` |

---

## 🧠 서브장르 분류 기준

- `lib/json/categories.json` 내 "desc\_keywords" 키 아래 각 장르별 키워드 정의
- 장르별 허용 서브장르는 `allowed_subgenres_by_genre`에서 검증

---

## 📌 예외 처리 및 보완

- TMDb 응답 없음 → NAVER 검색 보완
- 썸네일, 출연진 누락 → Gemini API로 대체 추출
- Gemini 응답값에 따른 서브장르 및 시청등급 재보정
- program\_id 오토 인크리먼트 활용하여 추가

---

## 📄 캐시 파일: `metadata_cache.csv`

- 프로그램 메타데이터 중복 요청을 줄이기 위한 **캐시 저장 파일**
- `get_program_metadata()` 호출 시, 이미 수집된 프로그램명이 존재하면 해당 CSV에서 값을 불러와 재요청 생략
- 주요 컬럼:
  - `title`, `genre`, `sub_genre`, `desc`, `thumbnail`, `cast`, `age_rating`
- 캐시를 통해 크롤링 속도 및 API 호출 비용 절감 효과

---

## 🛠 향후 개선 예정

- 로그 기록 기능 추가 (성공/실패 분리)
- CSV 정렬/정규화 옵션 추가

---

## 📝 진행 사항

- Metadata 수집(TMDB, NAVER 검색, Gemini) 병렬화
- Metadata 수집 병렬화 후 크롤링 시간 약 90분에서 약 19분으로 감소
- 모듈화 진행(이전 크롤링 코드 : [https://github.com/KongKongeee/IFITV-Crawling.git](https://github.com/KongKongeee/IFITV-Crawling.git))
- max\_workers 동적 조절(main.py에서 설정된 값을 Crawler 클래스에 전달)
- 채널 단위도 ThreadPoolExecutor로 묶어 2단 병렬화 진행
- 최종적으로 약 4분 이내 크롤링 완료되었으나, 서버에서 실행시 과부하 우려로 병렬실행 감소
- metadata_cache.csv 파일 생성하여 실행시간 3분 이내로 감소 및 api실행 비용 절감

