import os
import re
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

def fill_missing_metadata_with_gemini(program_name, original_genre, desc, sub_genre, thumbnail, age_rating, cast, allowed_subgenres_by_genre):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(model_name="gemini-2.0-flash-lite")

    genre_safe = original_genre if original_genre else "비어 있음"
    genre_list = ['영화', '드라마', '예능', '애니']

    prompt = f"""
다음은 IPTV 프로그램의 메타데이터입니다. 비어 있는 항목(desc, genre, sub_genre, thumbnail 등)이 있다면 추론하여 채워주세요.

프로그램명: {program_name}
장르(genre): {genre_safe}
설명(desc): {desc or '비어 있음'}
서브장르(sub_genre): {sub_genre or '비어 있음'}
썸네일(thumbnail): {thumbnail or '비어 있음'}
연령등급(age_rating): {age_rating or '비어 있음'}
출연진(cast): {cast or '비어 있음'}

가능한 서브장르 목록:
{', '.join(allowed_subgenres_by_genre.get(original_genre, []))}

❗️주의사항:
- '장르'가 비어 있는 경우에는 반드시 다음 중 하나로만 추론해 주세요: **{', '.join(genre_list)}**
- '서브장르'는 반드시 **해당 장르에 속하는 사전 정의된 목록 중에서만** 추론해 주세요.
- '썸네일'은 반드시 실제 이미지 URL만 작성해 주세요 (예: https://...).
- AI가 상상한 이미지나 일반 묘사일 경우 '정보 없음'으로 작성하세요.
- '연령등급'은 반드시 '전체 이용가', '12세 이상', '15세 이상', '19세 이상' 중 하나로 작성하세요.
- 출연진에 영어 이름이 있다면 반드시 한글로 번역해 주세요 (예: Tom Cruise → 톰 크루즈).

🧾 아래 형식으로만 출력해 주세요 (형식 엄수):
장르: ...
설명: ...
서브장르: ...
썸네일: ...
연령등급: ...
출연진: ...
"""
    try:
        response = model.generate_content(prompt)
        content = response.text.strip()

        genre_out = original_genre or "정보 없음"
        desc_out = desc or "정보 없음"
        sub_out = sub_genre or "정보 없음"
        thumb_out = thumbnail or "정보 없음"
        age_out = age_rating or "정보 없음"
        cast_out = cast or "정보 없음"

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        for line in lines:
            if line.startswith("장르:"):
                genre_out = line.replace("장르:", "").strip() or genre_out
            elif line.startswith("설명:"):
                desc_out = line.replace("설명:", "").strip() or desc_out
            elif line.startswith("서브장르:"):
                sub_out = line.replace("서브장르:", "").strip() or sub_out
            elif line.startswith("썸네일:"):
                thumb_out = line.replace("썸네일:", "").strip() or thumb_out
            elif line.startswith("연령등급:"):
                age_out = line.replace("연령등급:", "").strip() or age_out
            elif line.startswith("출연진:"):
                cast_out = line.replace("출연진:", "").strip() or cast_out

        return genre_out, sub_out, desc_out, thumb_out, age_out, cast_out

    except Exception as e:
        print(f"[Gemini 오류] {program_name}: {e}")
        return original_genre or "정보 없음", sub_genre or "정보 없음", desc or "정보 없음", thumbnail or "정보 없음", age_rating or "정보 없음", cast or "정보 없음"

def translate_cast_to_korean(cast_english):
    if not cast_english:
        return ''

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(model_name="gemini-2.0-flash-lite")

    cast_list = [name.strip() for name in cast_english.split(',') if name.strip()]
    cast_bullet = '\n'.join(f"- {name}" for name in cast_list)

    prompt = f"""
다음 영어 이름들을 한국어 이름으로 자연스럽게 번역해서 쉼표로 구분된 한 줄로 출력해줘.
- 반드시 원본과 순서를 맞춰서 번역하고, 번역 불가하면 생략하지 말고 그대로 출력해.
- 줄바꿈 없이, '홍길동, 김철수' 형식으로만 출력해.
- 말투나 설명 없이 번역 결과만 출력해.

영어 이름 목록:
{cast_bullet}
"""
    try:
        response = model.generate_content(prompt)
        translated = response.text.strip()
        translated = re.sub(r'\s+', ' ', translated)
        translated = translated.replace(' ,', ',').replace(', ', ',').replace(',', ', ')
        return translated.strip()

    except Exception as e:
        print(f"[Gemini 번역 오류 - cast] {cast_english}: {e}")
        return cast_english