import os
import re
import time
import traceback
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

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

# options.add_argument('--headless')
class Crawler:
    
    def __init__(self, max_workers=5):
        self.max_workers = max_workers
        self.cache_lock = Lock()
        os.makedirs('./data_crawling_tmdb_gemini', exist_ok=True)

    def setup_driver(self):
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--headless')
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
    
    def load_metadata_cache(self):
        path = './cache/metadata_cache.csv'
        if os.path.exists(path):
            return pd.read_csv(path)
        else:
            return pd.DataFrame(columns=[
                'title', 'genre', 'sub_genre', 'description', 'thumbnail', 'age_rating', 'cast'
            ])
    
    def fetch_metadata(self, driver, channel, airtime, title, genre, runtime, metadata_cache_df):
        try:
            # ✅ 1. 캐시 조회
            cached = metadata_cache_df[metadata_cache_df['title'] == title]
            if not cached.empty:
                row = cached.iloc[0]
                return [
                    channel, airtime, title,
                    row['genre'], row['sub_genre'], runtime,
                    row['description'], row['thumbnail'],
                    row['age_rating'], row['cast']
                ]
    
            # ✅ 2. 캐시에 없다면 외부 메타데이터 수집
            genre_out, sub_genre, desc, thumbnail, age_rating, cast, _ = get_program_metadata(title, driver, genre, channel)
    
            # ✅ 3. 캐시 업데이트 (동시성 고려)
            new_row = {
                'title': title,
                'genre': genre_out,
                'sub_genre': sub_genre,
                'description': desc,
                'thumbnail': thumbnail,
                'age_rating': age_rating,
                'cast': cast
            }
    
            # ✅ 4. 결과 반환
            return [
                channel, airtime, title,
                genre_out, sub_genre, runtime,
                desc, thumbnail, age_rating, cast
            ]
    
        except Exception as e:
            print(f"[TMDb 메타데이터 오류] '{title}' (채널: {channel}, 시간: {airtime}) → {e}")
            traceback.print_exc()
            return None





    def click_left_buttons(self, driver, times=2):
        for i in range(1, times + 1):
            try:
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.3)
    
                # ✅ _uid_233 버튼을 직접 찾기
                left_btn = driver.find_element(By.ID, "_uid_233")
    
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", left_btn)
                time.sleep(0.3)
    
                # ✅ 가리는 요소 제거
                driver.execute_script("""
                    let modal = document.querySelector('.modal');
                    if (modal) modal.style.display = 'none';
                    let header = document.querySelector('header');
                    if (header) header.style.zIndex = '0';
                """)
    
                # ✅ 클릭 강행
                driver.execute_script("arguments[0].click();", left_btn)
                print(f"✅ {i}번째 `<` 버튼 (#_uid_233) 클릭 완료")
                time.sleep(1.2)
    
            except Exception as e:
                print(f"❌ {i}번째 `<` 버튼 (#_uid_233) 클릭 중 오류:", e)
                time.sleep(1)

    def crawl_all_channels(self, channel_list, metadata_cache_df):
        all_data = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.process_channel_with_cache, ch, metadata_cache_df): ch
                for ch in channel_list
            }
            for future in as_completed(futures):
                channel = futures[future]
                try:
                    result = future.result()
                    if result:
                        all_data.extend(result)
                except Exception as e:
                    print(f"[❌ 병렬 실행 오류] {channel} → {e}")
                    traceback.print_exc()
        return all_data

    def save_final_program_data(self, all_data, filename):
        last_id = get_last_program_id_by_yesterday()
        df = pd.DataFrame(all_data, columns=[
            'channel', 'airtime', 'title', 'episode', 'genre', 'subgenre',
            'runtime', 'description', 'thumbnail', 'age_rating', 'cast'
        ])
        df['subgenre'] = df['subgenre'].apply(lambda x: x.replace('"', '') if isinstance(x, str) else x)
        df = df.sort_values(by=['channel', 'airtime']).reset_index(drop=True)
        df.insert(0, 'program_id', df.index + 1 + last_id)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[저장 완료] → {filename}")
        return df

    def update_metadata_cache(self, all_data, metadata_cache_df, cache_path):
        new_rows = [{
            'title': row[2],
            'genre': row[4],
            'sub_genre': row[5],
            'description': row[7],
            'thumbnail': row[8],
            'age_rating': row[9],
            'cast': row[10]
        } for row in all_data]
    
        new_cache_df = pd.DataFrame(new_rows)
        combined = pd.concat([metadata_cache_df, new_cache_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=['title'], keep='last')
        combined.to_csv(cache_path, index=False, encoding='utf-8-sig')
        print(f"[캐시 갱신 완료] → {cache_path}")

        



    def process_channel_with_cache(self, channel, metadata_cache_df):
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
            time.sleep(1.5)
    
            channel_xpath = f'//a[contains(text(), "{channel}")]'
            wait.until(EC.element_to_be_clickable((By.XPATH, channel_xpath))).click()
            time.sleep(2)
    
    
            # 날짜 탭 클릭
            for attempt in range(2):
                try:
                    target_date = datetime.now() + timedelta(days=2)
                    month_day = f"{target_date.month}월 {target_date.day}일"
                    day_of_week = ['(월)', '(화)', '(수)', '(목)', '(금)', '(토)', '(일)'][target_date.weekday()]
                    date_label = f"{month_day} {day_of_week}"

                    
                    date_btn = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, f'//a[contains(text(), "{date_label}")]'))
                    )
                    driver.execute_script("arguments[0].click();", date_btn)
                    print(f"✅ 날짜 버튼 클릭 완료 - {channel}")
                    time.sleep(1)
                    break
                except Exception as e:
                    print(f"❌ {attempt+1}번째 날짜 버튼 클릭 실패", e)
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
                    if raw_name in ["방송 시간이 아닙니다", "방송시간이 아닙니다.", "방송시간이 아닙니다"]:
                        continue
                    genre = genre_map.get(tds[2].text.strip(), tds[2].text.strip())
                    temp_list.append([channel, time_text, raw_name, genre])
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
                    
            episode_list = []
            for item in merged_programs:
                raw_title = item[2]
                match = re.search(r'(\d{1,4}회)', raw_title)
                episode = match.group(1) if match else ''
                clean_title = clean_name(raw_title.replace(episode, '').strip())
                item[2] = clean_title
                episode_list.append(episode)


            final_list = []
            
            for idx, (channel, airtime, title, genre, runtime) in enumerate(merged_programs):
                result = self.fetch_metadata(driver, channel, airtime, title, genre, runtime, metadata_cache_df)
                if result:
                    result.insert(3, episode_list[idx])  # ✅ 3번째 위치(episode 자리)에 회차 삽입
                    final_list.append(result)

    
            safe_name = re.sub(r'\s*(\[[^]]*\])', '', channel).strip()
            df = pd.DataFrame(final_list, columns=[
                'channel', 'airtime', 'title', 'episode', 'genre', 'subgenre',
                'runtime', 'description', 'thumbnail', 'age_rating', 'cast'
            ])
            
            df['subgenre'] = df['subgenre'].apply(lambda x: x.replace('"', '') if isinstance(x, str) else x)
            df = df.sort_values(by='airtime')
            df.to_csv(f'./data_crawling_tmdb_gemini/{safe_name}_program_list.csv', index=False, encoding='utf-8-sig')
    
            print(f"[완료] {channel} → 저장 완료")
            return final_list
    
        except Exception as e:
            print(f"[채널 오류] {channel} 처리 중 오류:\n{traceback.format_exc()}")
            return []
    
        finally:
            driver.quit()

            
    def run(self):
        start_time = time.time()
        print("[크롤링 시작]")
    
        today_str = datetime.now().strftime('%Y-%m-%d')
        target_date_str = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        filename = f'./data_crawling_tmdb_gemini/{target_date_str}_실시간_방영_프로그램_리스트.csv'
        cache_path = './cache/metadata_cache.csv'
    
        channel_list = [
            '투니버스[324]', '어린이TV[322]',
            
            'KBS1[9]', 'KBS2[7]', 'MBC[11]', 'SBS[5]', 'EBS1[14]',
            
            'JTBC[15]', 'TV조선[19]', 'tvN[3]', 'ENA[72]',
            
            'OCN[44]', '스크린[46]', '캐치온1[52]',
            
            '드라마큐브[71]', 'ENA DRAMA[73]', 'MBC드라마넷[35]',
        ]
    
        # ✅ 캐시 로딩
        metadata_cache_df = pd.read_csv(cache_path) if os.path.exists(cache_path) else pd.DataFrame(columns=[
            'title', 'genre', 'sub_genre', 'description',
            'thumbnail', 'age_rating', 'cast'
        ])
    
        # ✅ 채널 병렬 처리
        all_data = self.crawl_all_channels(channel_list, metadata_cache_df)
    
        if not all_data:
            print("[경고] 수집된 데이터 없음")
            return
    
        # ✅ 결과 저장
        df = self.save_final_program_data(all_data, filename)
    
        # ✅ 캐시 저장
        self.update_metadata_cache(all_data, metadata_cache_df, cache_path)
    
        elapsed = time.time() - start_time
        print(f"[전체 완료] 크롤링 종료 (총 소요: {int(elapsed // 60)}분 {int(elapsed % 60)}초)")
