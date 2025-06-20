import os
import re
import time
import traceback
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from bs4 import BeautifulSoup
from lib.config.genre_config import genre_map
from lib.metadata.metadata_manager import get_program_metadata
from lib.utils.text_cleaning import clean_name

def get_last_program_id_by_yesterday():
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    filename = f'./data_crawling_tmdb_gemini/{yesterday}_실시간_방영_프로그램_리스트.csv'
    if not os.path.exists(filename):
        print(f"[ID 초기화] 어제 파일 없음 → 오늘은 program_id 1부터 시작")
        return 0
    try:
        df = pd.read_csv(filename, encoding='utf-8-sig')
        return int(df['program_id'].max())
    except Exception as e:
        print(f"[ID 이어붙이기 오류] {filename} 파일 읽기 실패: {e}")
        return 0


class Crawler:
    def __init__(self, max_workers=5):
        self.max_workers = max_workers
        os.makedirs('./data_crawling_tmdb_gemini', exist_ok=True)

    def setup_driver(self):
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 13)
        return driver, wait

    def calculate_runtime(self, programs):
        new_list = []
        for i in range(len(programs)):
            current_time = datetime.strptime(programs[i][1], "%H:%M:%S")
            if i < len(programs) - 1:
                next_time = datetime.strptime(programs[i + 1][1], "%H:%M:%S")
                if next_time < current_time:
                    next_time += timedelta(days=1)
                runtime = int((next_time - current_time).total_seconds() / 60)
            else:
                runtime = 60
            new_list.append(programs[i] + [runtime])
        return new_list

    def fetch_metadata(self, driver, channel, airtime, title, genre, runtime, metadata_cache):
        try:
            if title in metadata_cache:
                genre_out, sub_genre, desc, thumbnail, age_rating, cast = metadata_cache[title]
            else:
                genre_out, sub_genre, desc, thumbnail, age_rating, cast = get_program_metadata(title, driver, genre)
                metadata_cache[title] = (genre_out, sub_genre, desc, thumbnail, age_rating, cast)
            return [channel, airtime, title, genre_out, sub_genre, runtime, desc, thumbnail, age_rating, cast]
        except Exception as e:
            print(f"[메타데이터 오류] {title}: {e}")
            return None

    def process_channel(self, channel):
        driver, wait = self.setup_driver()
        url = 'https://www.lguplus.com/iptv/channel-guide'
        table_btn_xpath = '//a[contains(text(), "채널 편성표 안내")]'
        all_channel_btn_xpath = '//a[contains(text(), "전체채널")]'

        try:
            driver.get(url)
            driver.execute_script("document.body.style.zoom='50%'")
            time.sleep(1)

            wait.until(EC.element_to_be_clickable((By.XPATH, table_btn_xpath))).click()
            time.sleep(1)
            wait.until(EC.element_to_be_clickable((By.XPATH, all_channel_btn_xpath))).click()
            time.sleep(2)
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.c-btn-outline-2-s.open"))).click()
            time.sleep(1)

            channel_xpath = f'//a[contains(text(), "{channel}")]'
            wait.until(EC.element_to_be_clickable((By.XPATH, channel_xpath))).click()
            time.sleep(2)

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            program_soup_list = soup.select('tr.point')

            temp_list = []
            for item in program_soup_list:
                try:
                    tds = item.select('td')
                    time_text = tds[0].text.strip()
                    name_parts = tds[1].text.split('\n')
                    raw_name = name_parts[1].strip() if len(name_parts) > 1 else tds[1].text.strip()
                    name = clean_name(raw_name)
                    if name in ["방송 시간이 아닙니다", "방송시간이 아닙니다.", "방송시간이 아닙니다"]:
                        continue
                    genre = genre_map.get(tds[2].text.strip(), tds[2].text.strip())
                    temp_list.append([channel, time_text, name, genre])
                except Exception as e:
                    print(f"[파싱 오류] {e}")
                    continue

            temp_list = self.calculate_runtime(temp_list)

            merged_programs = []
            skip_next = False
            for i in range(len(temp_list)):
                if skip_next:
                    skip_next = False
                    continue
                if i < len(temp_list) - 1 and temp_list[i][1] == temp_list[i + 1][1]:
                    merged = temp_list[i][:]
                    merged[3] = temp_list[i][3] + temp_list[i + 1][3]
                    merged_programs.append(merged)
                    skip_next = True
                else:
                    merged_programs.append(temp_list[i])

            final_list = []
            metadata_cache = {}
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.fetch_metadata, driver, channel, airtime, title, genre, runtime, metadata_cache): title
                    for channel, airtime, title, genre, runtime in merged_programs
                }
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        final_list.append(result)
                    time.sleep(0.05)

            safe_name = re.sub(r'\s*(\[[^]]*\])', '', channel).strip()
            df = pd.DataFrame(final_list, columns=[
                'channel','airtime','title','genre','subgenre','runtime','description','thumbnail','age_rating','cast'])
            df['subgenre'] = df['subgenre'].apply(lambda x: x.replace('"', '') if isinstance(x, str) else x)
            df = df.sort_values(by='airtime')
            df.to_csv(f'./data_crawling_tmdb_gemini/{safe_name}_program_list.csv', index=False, encoding='utf-8-sig')

            print(f"[완료] {channel} → 저장 완료")
            return final_list
        except Exception as e:
            print(f"[채널 오류] {channel} 처리 중 오류:\n{traceback.format_exc()}")
        finally:
            driver.quit()
            
    def run(self):
        start_time = time.time()
        print("[크롤링 시작]")
    
        channel_list = [
            'KBS1[9]', 'KBS2[7]', 'MBC[11]', 'SBS[5]',
            'JTBC[15]', 'MBN[16]', '채널A[18]', 'TV조선[19]',
            'OBS[26]', 'tvN[3]', 'OCN[44]', '스크린[46]',
            '씨네프[47]', 'OCN Movies2[51]',
            '캐치온1[52]', '캐치온2[53]', '채널액션[54]',
            '드라마큐브[71]', 'ENA[72]', 'ENA DRAMA[73]',
            'KBS Story[74]', 'SBS플러스[33]', 'MBC드라마넷[35]',
            '투니버스[324]', '카툰네트워크[316]',
            '애니박스[327]', '애니맥스[326]', '어린이TV[322]'
        ]
        
        all_data = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.process_channel, channel): channel for channel in channel_list}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    all_data.extend(result)

        # ✅ 어제 program_id 최대값 읽기
        last_id = get_last_program_id_by_yesterday()

        # ✅ DataFrame 생성 및 정리
        df = pd.DataFrame(all_data, columns=[
            'channel', 'airtime', 'title', 'genre', 'subgenre',
            'runtime', 'description', 'thumbnail', 'age_rating', 'cast'
        ])
        df['subgenre'] = df['subgenre'].apply(lambda x: x.replace('"', '') if isinstance(x, str) else x)
        df = df.sort_values(by=['channel', 'airtime']).reset_index(drop=True)

        # ✅ 오토 인크리먼트 ID 추가
        df.insert(0, 'program_id', df.index + 1 + last_id)

        # ✅ CSV 파일 저장
        today_str = datetime.now().strftime('%Y-%m-%d')
        filename = f'./data_crawling_tmdb_gemini/{today_str}_실시간_방영_프로그램_리스트.csv'
        df.to_csv(filename, index=False, encoding='utf-8-sig')

        elapsed = time.time() - start_time
        print(f"[전체 완료] 모든 채널 크롤링 종료 (총 소요 시간: {int(elapsed // 60)}분 {int(elapsed % 60)}초)")
        print(f"[저장 완료] → {filename}")
    
