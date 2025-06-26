import re
from lib.utils.text_cleaning import clean_name
from lib.metadata.tmdb import get_program_info_from_tmdb
from lib.metadata.naver import get_info_from_web_search, get_cast_list_from_naver
from lib.metadata.gemini import fill_missing_metadata_with_gemini, translate_cast_to_korean
from lib.config.genre_config import desc_keywords, allowed_subgenres_by_genre, genre_map

def guess_subgenre_by_desc(desc):
    desc_clean = re.sub(r'[^\w\s]', ' ', desc).lower()
    desc_clean = re.sub(r'\s+', ' ', desc_clean).strip()
    for subgenre, keywords in desc_keywords.items():
        for keyword in keywords:
            if keyword.lower().strip() in desc_clean:
                return subgenre
    return ''

def clean_subgenre_by_genre(original_genre, sub_genre):
    if sub_genre == '코미디':
        return '코미디'
    if original_genre == '예능' and sub_genre in [
        '휴먼', '로맨스', '판타지', '무협', '공포', '복수', '의학',
        '웹툰_소설 원작', '정치_권력', '법정', '청춘', '오피스 드라마',
        '사극_시대극', '타임슬립', '범죄 스릴러_수사극']:
        return ''
    if original_genre == '드라마' and sub_genre not in allowed_subgenres_by_genre['드라마']:
        return ''
    return sub_genre

def validate_and_fix_subgenre(original_genre, sub_genre, desc, genre_text):
    allowed_list = allowed_subgenres_by_genre.get(original_genre, [])

    # ✅ 1차: 정상 서브장르인지 확인
    if sub_genre:
        cleaned = [sg.strip() for sg in sub_genre.split(',') if sg.strip() in allowed_list]
        if cleaned:
            return ', '.join(cleaned)

    # ✅ 2차: 설명 기반 추론
    guessed = guess_subgenre_by_desc((genre_text or '') + " " + (desc or ''))
    guessed = clean_subgenre_by_genre(original_genre, guessed)
    if guessed in allowed_list:
        return guessed

    # ✅ 3차: 키워드 기반 fallback
    text = f"{desc or ''} {genre_text or ''}"
    keywords_kids = ['키즈', '어린이', '유아', '동요', 'TV만화', '아동']
    keywords_edu = ['교육', '학습', '영어', '수학', '학교', '과학']
    keywords_info = ['정보', '생활', '교양', '인문학', '문화', '지식']

    if any(k in text for k in keywords_kids):
        return '키즈' if original_genre == '애니' else ''
    elif any(k in text for k in keywords_edu):
        return '교육예능' if original_genre == '예능' else ''
    elif any(k in text for k in keywords_info):
        return '교양' if original_genre == '예능' else ''

    return ''

def get_program_metadata(program_name, driver, original_genre, channel):
    name = clean_name(program_name)

    # 예외 처리 테이블
    program_exceptions = {
        '세계테마기행': {
            'genre': '예능',
            'desc': '단순한 여행 정보 프로그램에서 벗어나, 자유로운 배낭여행자만이 느낄 수 있는 살아있는 체험기를 전하는 다큐멘터리 프로그램',
            'sub_genre': '여행, 다큐멘터리',
            'thumbnail': 'https://image.tmdb.org/t/p/w500/pHC70ke34d0pEOdhcx8lnWhRtqk.jpg',
            'age_rating': '전체 이용가',
            'cast': '정보 없음'
        },
    }

    # 예외
    if name in program_exceptions:
        meta = program_exceptions[name]
        genre = meta.get('genre', original_genre)
        return genre, meta['sub_genre'], meta['desc'], meta['thumbnail'], meta['age_rating'], meta['cast'], name

    # 스포츠 예외
    if original_genre == '스포츠':
        return '스포츠', '스포츠', program_name, '', '전체 이용가', '정보 없음', program_name
    
    # 보도 예외
    if original_genre == '보도':
        return '보도', '보도', program_name, '', '전체 이용가', '정보 없음', program_name

    # ✅ TMDb 정보 가져오기 (오류 출력 추가)
    try:
        desc, thumbnail, sub_genre, age_rating, cast = get_program_info_from_tmdb(name, original_genre, channel)
    except Exception as e:
        print(f"[TMDb 오류] 프로그램명: '{program_name}' → {e}")
        desc, thumbnail, sub_genre, age_rating, cast = '', '', '', '', '정보 없음'

    # NAVER 보완
    genre_text, web_thumb = get_info_from_web_search(driver, name)
    if not thumbnail:
        thumbnail = web_thumb

    # 애니 장르 정제
    if genre_text == '애니':
        original_genre = '애니'
        sub_genre = '키즈'

    # 시사/교양 → 예능 교양
    if genre_text == '시사/교양':
        original_genre = '예능'
        sub_genre = '교양'
    if genre_text == '시사/보도':
        original_genre = '보도'
        sub_genre = '보도'

    # 공연/음악 → 음악예능
    if original_genre == '공연/음악':
        original_genre, sub_genre = '예능', '음악예능'

    # 영화일 경우 예능 서브장르 제거
    if original_genre == '영화':
        forbidden = set(allowed_subgenres_by_genre['예능'] + ['범죄 스릴러_수사극'])
        if sub_genre in forbidden:
            sub_genre = ''

    # 출연진 처리
    if cast and all(ord(c) < 128 for c in cast):
        cast = translate_cast_to_korean(cast)
    if not cast or cast == '정보 없음':
        cast_from_naver = get_cast_list_from_naver(driver, program_name)
        if cast_from_naver:
            cast = cast_from_naver

    # 1차 클린징
    sub_genre = clean_subgenre_by_genre(original_genre, sub_genre)

    # 2차 이상치 제거 및 보정
    sub_genre = validate_and_fix_subgenre(original_genre, sub_genre, desc, genre_text)

    # Gemini로 보완
    if not original_genre or not desc or not sub_genre or not thumbnail or not age_rating or not cast:
        genre_out, sub_genre, desc, thumbnail, age_rating, cast = fill_missing_metadata_with_gemini(
            program_name, original_genre, desc, sub_genre, thumbnail, age_rating, cast, allowed_subgenres_by_genre
        )
        original_genre = genre_out
       
        # ✅ 보완 후 재검증
        sub_genre = validate_and_fix_subgenre(original_genre, sub_genre, desc, genre_text)
        
    # 설명 및 연령 정리
    desc = re.sub(r'\s+', ' ', desc or '').strip()
    age_rating = age_rating.strip().upper() if age_rating else '전체 이용가'
    if age_rating in ['12']: age_rating = '12세 이상'
    elif age_rating in ['7']: age_rating = '7세 이상'
    elif age_rating in ['15']: age_rating = '15세 이상'
    elif age_rating in ['18', '19', '19+']: age_rating = '19세 이상'
    elif age_rating in ['ALL', '전체', '전체 이용가']: age_rating = '전체 이용가'

    if original_genre == '다큐':
        original_genre, sub_genre = '예능', '다큐멘터리'
    if original_genre == '애니':
        original_genre, sub_genre = '애니', '키즈'
    if original_genre == '교육':
        original_genre, sub_genre = '예능', '교육예능'

    return original_genre, sub_genre, desc, thumbnail, age_rating, cast, program_name