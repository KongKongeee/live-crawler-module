import os
import json

base_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(base_dir, '..', 'json', 'categories.json')

with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)
    desc_keywords = data['desc_keywords']


USE_TMDB_DESC_PRIORITY = True
USE_TMDB_SUBGENRE_PRIORITY = True

tmdb_genre_map = {
    28: '액션',
    12: '모험',
    16: '애니메이션',
    35: '코미디',
    80: '스릴러',
    99: '다큐멘터리',
    18: '드라마',
    14: '판타지',
    27: '공포',
    9648: '미스터리',
    10749: '로맨스',
    878: 'SF',
    10770: '드라마',
    53: '스릴러',
    10752: '액션',
    37: '모험'
}

allowed_subgenres_by_genre = {
    '드라마': [
        '해외드라마', '미국드라마', '영국드라마', '중국드라마', '일본드라마',
        '로맨스', '코미디', '판타지', '무협', '공포', '복수', '휴먼', '범죄 스릴러_수사극',
        '의학', '웹툰_소설 원작', '정치_권력', '법정', '청춘', '오피스 드라마', '사극_시대극', '타임슬립'
    ],
    '예능': [
        '버라이어티', '다큐멘터리', '여행', '쿡방_먹방', '연애리얼리티', '게임', '토크쇼', '서바이벌',
        '관찰리얼리티', '스포츠예능', '교육예능', '힐링예능', '아이돌', '음악서바이벌', '음악예능',
        '코미디', '가족예능', '뷰티', '애니멀', '교양'
    ],
    '영화': [
        '드라마', '로맨스', '코미디', '애니메이션', '스릴러', '미스터리',
        '모험', '액션', '판타지', 'SF', '공포', '다큐멘터리'
    ],
    '애니': ['키즈'],
    '보도': ['보도']
}

genre_name_to_kor = {
    "Action": "액션",
    "Thriller": "스릴러",
    "Comedy": "코미디",
    "Drama": "드라마",
    "Romance": "로맨스",
    "Fantasy": "판타지",
    "Science Fiction": "SF",
    "Mystery": "미스터리",
    "Animation": "애니메이션",
    "Horror": "공포",
    "Documentary": "다큐멘터리",
    "Adventure": "모험",
    "Talk": "토크쇼",
    "Reality": "버라이어티",
    "Sci-Fi & Fantasy": "판타지"
}

genre_map = {'연예/오락': '예능', '뉴스/정보': '보도', '만화': '애니'}
