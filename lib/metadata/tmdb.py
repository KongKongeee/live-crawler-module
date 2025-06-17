import os
import re
import requests
from urllib.parse import quote
from lib.config.genre_config import tmdb_genre_map, genre_name_to_kor

from dotenv import load_dotenv
load_dotenv()

def clean_title_for_tmdb(title):
    title = re.sub(r'[\(\)\[\]〈〉“”"\':\-\|·,~!@#\$%\^&\*\+=]+', ' ', title)
    title = re.sub(r'\s+', ' ', title)
    return title.strip()

def get_program_info_from_tmdb(title, original_genre):
    api_key = os.getenv("TMDB_API_KEY")
    image_base_url = "https://image.tmdb.org/t/p/w500"

    if original_genre in ["드라마", "예능", "보도"]:
        endpoints = [("tv", "name"), ("movie", "title")]
    else:
        endpoints = [("movie", "title"), ("tv", "name")]

    cleaned_title = clean_title_for_tmdb(title)

    for content_type, title_key in endpoints:
        try:
            search_url = f"https://api.themoviedb.org/3/search/{content_type}"
            params = {"api_key": api_key, "query": title, "language": "ko-KR"}
            search_res = requests.get(search_url, params=params)
            search_res.raise_for_status()
            results = search_res.json().get("results", [])

            if not results:
                continue

            item = results[1] if title == '인간극장' and len(results) > 1 else results[0]
            content_id = item["id"]

            detail_url = f"https://api.themoviedb.org/3/{content_type}/{content_id}"
            detail_res = requests.get(detail_url, params={"api_key": api_key, "language": "ko-KR"})
            detail_res.raise_for_status()
            detail = detail_res.json()

            desc = detail.get("overview", "")
            poster_path = detail.get("poster_path")
            thumbnail = image_base_url + poster_path if poster_path else ''

            genre_data = detail.get("genres", [])
            genre_ids = [g.get("id") for g in genre_data if g.get("id") is not None]
            subgenres = list({tmdb_genre_map.get(gid) for gid in genre_ids if tmdb_genre_map.get(gid)})

            credits_url = f"https://api.themoviedb.org/3/{content_type}/{content_id}/credits"
            credits_res = requests.get(credits_url, params={"api_key": api_key})
            credits = credits_res.json()
            cast_list = [c["name"] for c in credits.get("cast", [])[:5]]
            cast = ', '.join(cast_list)

            age_rating = ''
            try:
                if content_type == "tv":
                    rating_url = f"https://api.themoviedb.org/3/tv/{content_id}/content_ratings"
                else:
                    rating_url = f"https://api.themoviedb.org/3/movie/{content_id}/release_dates"

                rating_res = requests.get(rating_url, params={"api_key": api_key})
                rating_res.raise_for_status()
                rating_json = rating_res.json()

                if content_type == "tv":
                    for entry in rating_json.get("results", []):
                        if entry.get("iso_3166_1") == "KR":
                            age_rating = entry.get("rating", "")
                            break
                else:
                    for entry in rating_json.get("results", []):
                        if entry.get("iso_3166_1") == "KR":
                            for release in entry.get("release_dates", []):
                                if release.get("certification"):
                                    age_rating = release["certification"]
                                    break
            except:
                age_rating = ''

            if not subgenres:
                fallback_names = [genre_name_to_kor.get(g.get("name"), '') for g in genre_data]
                subgenres = [name for name in fallback_names if name]

            sub_genre = ', '.join(subgenres).strip()

            return desc, thumbnail, sub_genre, age_rating, cast

        except Exception as e:
            print(f"[TMDb 오류 - {content_type.upper()}] {title}: {e}")
            continue

    return '', '', '', '', ''
