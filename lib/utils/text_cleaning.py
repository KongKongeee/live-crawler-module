import re

def clean_program_name_for_url(name):
    name = re.sub(r'\<.*?\>', '', name)
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'〈.*?〉', '', name)
    name = re.sub(r'[“”"\':\-|·,~!@#$%^&*+=]+', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def clean_text(text):
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'〈.*?〉', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r',\s*,', ',', text)
    return text

def clean_name(text):
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'\[[^]]*\]', '', text)
    text = re.sub(r'〈.*?〉', '', text)
    text = re.sub(r'\<.*?\>', '', text)

    text = re.sub(r'\b(수목드라마|월화드라마|일일드라마|재방송|특별판|스페셜|본방송|본|재|특집|종영|마지막회|최종화|HD|SD|NEW|다시보기)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\d+부', '', text)

    text = re.sub(r'[“”"\':\-|·,~!@#$%^&*+=]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    text = re.sub(r'([가-힣])\s+([A-Za-z])', r'\1\2', text)
    text = re.sub(r'([A-Za-z])\s+([가-힣])', r'\1\2', text)

    text = text.strip("()[]〈〉 ")
    return text.strip()
