import time
import re
from urllib.parse import quote
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from lib.utils.text_cleaning import clean_name

def get_info_from_web_search(driver, name):
    cleaned = clean_name(name)
    query = f"{cleaned} 정보"
    driver.get(f"https://search.naver.com/search.naver?query={quote(query)}")
    time.sleep(1.5)

    try:
        genre = driver.find_element(By.CSS_SELECTOR, "div.sub_title span").text.strip()
    except:
        genre = ''

    try:
        thumbnail = driver.find_element(
            By.CSS_SELECTOR,
            '#main_pack div[class*="_broadcast_button_scroller"] div.cm_content_wrap._broadcast_normal_total > div:nth-child(1) div.detail_info a img'
        ).get_attribute("src")
    except:
        thumbnail = ''

    return genre, thumbnail

def get_cast_list_from_naver(driver, program_title):
    try:
        query = f"{program_title} 출연진"
        url = f"https://search.naver.com/search.naver?query={quote(query)}"
        driver.get(url)
        time.sleep(1.5)

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        primary_selector = (
            '#main_pack > div.sc_new._kgs_broadcast.cs_common_module._broadcast_button_scroller.case_normal.color_13 '
            '> div.cm_content_wrap._broadcast_normal_total > div > div.list_image_info._content > ul > li > div > div > span > a'
        )
        cast_tags = soup.select(primary_selector)
        cast_list = [tag.get_text(strip=True) for tag in cast_tags[:5]]

        if not cast_list:
            backup_selector = '#main_pack div.cm_content_wrap._broadcast_normal_total ul li div div strong a'
            cast_tags = soup.select(backup_selector)
            cast_list = [tag.get_text(strip=True) for tag in cast_tags[:5]]

        return ', '.join(cast_list) if cast_list else ''

    except Exception as e:
        print(f"[네이버 출연진 오류] {program_title}: {e}")
        return ''
