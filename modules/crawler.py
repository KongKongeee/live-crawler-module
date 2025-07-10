import os
import re
import time
import traceback
import pandas as pd
import numpy as np
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

    def __init__(self, max_workers=5, target_day_offset=0):
        self.max_workers = max_workers
        self.target_day_offset = target_day_offset  # ✅ 기준 날짜 offset
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
                'title', 'genre', 'subgenre', 'description', 'thumbnail', 'age_rating', 'cast'
            ])
    
    def fetch_metadata(self, driver, channel, airtime, title, genre, runtime, metadata_cache_df):
        try:
            # ✅ 1. 캐시 조회
            cached = metadata_cache_df[metadata_cache_df['title'] == title]
            if not cached.empty:
                row = cached.iloc[0]
                return [
                    channel, airtime, title,
                    row['genre'], row['subgenre'], runtime,
                    row['description'], row['thumbnail'],
                    row['age_rating'], row['cast']
                ]
    
            # ✅ 2. 캐시에 없다면 외부 메타데이터 수집
            genre_out, subgenre, desc, thumbnail, age_rating, cast, _ = get_program_metadata(title, driver, genre, channel)
    
            # ✅ 3. 캐시 업데이트 (동시성 고려)
            new_row = {
                'title': title,
                'genre': genre_out,
                'subgenre': subgenre,
                'description': desc,
                'thumbnail': thumbnail,
                'age_rating': age_rating,
                'cast': cast
            }
    
            # ✅ 4. 결과 반환
            return [
                channel, airtime, title,
                genre_out, subgenre, runtime,
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
        
        df.replace("정보 없음", np.nan, inplace=True)
        df['subgenre'] = df['subgenre'].apply(lambda x: x.replace('"', '') if isinstance(x, str) else x)
        df = df.sort_values(by=['channel', 'airtime']).reset_index(drop=True)
        df.insert(0, 'program_id', df.index + 1 + last_id)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"[저장 완료] → {filename}")
        return df



    def update_metadata_cache(self, all_data, metadata_cache_df, cache_path):
        new_rows = []
    
        for row in all_data:
            title = row[2]
            title_lower = title.strip().lower()
    
            # ✅ '클래스 e'로 정확히 시작하는 경우에만 예외 처리
            if '클래스e' in title_lower or re.match(r'^클래스\s*e\b', title_lower):
                genre = '예능'
                subgenre = '교양'
                description = '세상을 살아가기 위한 가장 간편하고 지적인 방법'
                thumbnail = 'https://search.pstatic.net/common?type=f&size=176x244&quality=100&direct=true&src=https%3A%2F%2Fcsearch-phinf.pstatic.net%2F20201008_216%2F1602147482205904L6_JPEG%2F57_poster_image_1602147482169.jpg'
                age_rating = '전체 이용가'
                
            elif 'EBS평생학교' in title:
                genre = '예능'
                subgenre = '교양'
                description = '고령화 사회로 진입하면서 교육 콘텐츠로부터 소외받는 시니어 층을 위해 평생교육법을 바탕으로 7개 주제로 나눈 신개념 평생교육 프로그램'
                thumbnail = 'https://search.pstatic.net/common?type=f&size=176x244&quality=100&direct=true&src=https%3A%2F%2Fcsearch-phinf.pstatic.net%2F20230403_68%2F1680510606322Wo3DU_JPEG%2F57_31285970_poster_image_1680510606307.jpg'
                age_rating = '전체 이용가'
            
            elif '버섯도리 패밀리 대작전 3' in title:
                genre = '애니'
                subgenre = '키즈'
                descrpition = '버섯도리 가족에게 새로운 사건이 발생했다! 수상한 용의자들! 똥촉이 난무하는 추리! 미궁에 빠지는 사건! 과연 범인은 누구?! 버섯도리와 함께 이번 사건도 해결!'
                thumbnail = 'https://search.pstatic.net/common?type=f&size=176x244&quality=100&direct=true&src=https%3A%2F%2Fcsearch-phinf.pstatic.net%2F20240419_176%2F1713497424475OzSAv_JPEG%2F57_poster_image_1713497424444.jpg'
                age_rating = '12세 이상'
            
            elif '위대한 수업 그레이트 마인즈' in title:
                genre = '예능'
                subgenre = '교양'
                description = '세계적 지적 유산들을 성실히 기록하며, 한국 사회에 의미 있는 담론을 형성하는 프로그램'
                thumbnail = 'https://search.pstatic.net/common?type=f&size=176x244&quality=100&direct=true&src=https%3A%2F%2Fcsearch-phinf.pstatic.net%2F20240926_216%2F1727336972138NxBJg_JPEG%2F57_poster_image_1727336972119.jpg'
                age_rating = '전체 이용가'
                
            else:
                genre = row[4]
                subgenre = row[5]
                description = row[7]
                thumbnail = row[8]
                age_rating =  row[9]
    
            new_rows.append({
                'title': title,
                'genre': genre,
                'subgenre': subgenre,
                'description': description,
                'thumbnail': thumbnail,
                'age_rating': age_rating,
                'cast': row[10]
            })
    
        new_cache_df = pd.DataFrame(new_rows)
        before_count = len(metadata_cache_df)
    
        combined = pd.concat([metadata_cache_df, new_cache_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=['title'], keep='last')
    
        after_count = len(combined)
        added_count = after_count - before_count
    
        combined.to_csv(cache_path, index=False, encoding='utf-8-sig')
        print(f"[캐시 갱신 완료] → {cache_path} (신규 추가: {added_count}개)")


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
                    target_date = datetime.now() + timedelta(days=self.target_day_offset)
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
    
        # run() 내 날짜 설정
        target_date = datetime.now() + timedelta(days=self.target_day_offset)
        target_date_str = target_date.strftime('%Y-%m-%d')
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
            'title', 'genre', 'subgenre', 'description',
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
