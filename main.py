from modules.crawler import Crawler

def main():
    crawler = Crawler(target_day_offset=0)
    crawler.run()

if __name__ == "__main__":
    main()