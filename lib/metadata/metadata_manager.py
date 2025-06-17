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
    if not sub_genre or not any(sg.strip() in allowed_list for sg in sub_genre.split(',')):
        guessed = guess_subgenre_by_desc((genre_text or '') + " " + (desc or ''))
        guessed = clean_subgenre_by_genre(original_genre, guessed)
        if guessed in allowed_list:
            return guessed
        else:
            return ''
    return sub_genre

def get_program_metadata(program_name, driver, original_genre):
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

    if name in program_exceptions:
        meta = program_exceptions[name]
        genre = meta.get('genre', original_genre)
        return genre, meta['sub_genre'], meta['desc'], meta['thumbnail'], meta['age_rating'], meta['cast']

    if original_genre in ['스포츠', '애니', '만화']:
        sub_genre, desc = ('스포츠', program_name) if original_genre == '스포츠' else ('키즈', program_name)
        return '애니' if original_genre == '만화' else original_genre, sub_genre, desc, '', '전체 이용가', '정보 없음'

    desc, thumbnail, sub_genre, age_rating, cast = get_program_info_from_tmdb(name, original_genre)

    genre_text, web_thumb = get_info_from_web_search(driver, name)
    if not thumbnail:
        thumbnail = web_thumb

    if cast and all(ord(c) < 128 for c in cast):
        cast = translate_cast_to_korean(cast)

    if not cast or cast == "정보 없음":
        cast_from_naver = get_cast_list_from_naver(driver, program_name)
        if cast_from_naver:
            cast = cast_from_naver

    if genre_text == '시사/교양':
        original_genre = '예능'
        sub_genre = '교양'
    if genre_text == '시사/보도':
        original_genre = '보도'
    if genre_text == '애니':
        sub_genre = '키즈'

    if sub_genre and isinstance(sub_genre, str):
        keywords = ['교육', '어린이', 'TV만화', '키즈', '유아교육', '유아 교육', '유아/어린이']
        if any(sg.strip() in keywords for sg in sub_genre.split(',')):
            original_genre, sub_genre = '애니', '키즈'

    if sub_genre and isinstance(sub_genre, str):
        keywords = ['영어 회화', '교육', '과학', '초급 영어', '초등', '중등', '고등']
        if any(sg.strip() in keywords for sg in sub_genre.split(',')):
            original_genre, sub_genre = '예능', '교육예능'

    if original_genre in ['스포츠', '보도']:
        sub_genre = original_genre
        desc = program_name
    if original_genre == '공연/음악':
        original_genre, sub_genre = '예능', '음악예능'
    if original_genre == '영화':
        forbidden = set(allowed_subgenres_by_genre['예능'] + ['범죄 스릴러_수사극'])
        if sub_genre in forbidden:
            sub_genre = ''

    sub_genre = clean_subgenre_by_genre(original_genre, sub_genre)
    sub_genre = validate_and_fix_subgenre(original_genre, sub_genre, desc, genre_text)

    if not original_genre or not desc or not sub_genre or not thumbnail or not age_rating or not cast:
        genre_out, sub_genre, desc, thumbnail, age_rating, cast = fill_missing_metadata_with_gemini(
            program_name, original_genre, desc, sub_genre, thumbnail, age_rating, cast, allowed_subgenres_by_genre
        )
        original_genre = genre_out

    desc = re.sub(r'\s+', ' ', desc or '').strip()
    
    if age_rating:
        age_rating = age_rating.strip()
        if age_rating == '12':
            age_rating = '12세 이상'
        elif age_rating == '15':
            age_rating = '15세 이상'
        elif age_rating in ['18', '19']:
            age_rating = '19세 이상'
    else:
        age_rating = '전체 이용가'
    
    return original_genre, sub_genre, desc, thumbnail, age_rating, cast