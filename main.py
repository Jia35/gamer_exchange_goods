import json
import queue
import random
import threading
import time
import configparser

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')


def save_cookie():
    """登入巴哈網站，儲存 cookie"""
    options = webdriver.ChromeOptions()
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    driver = webdriver.Chrome(options=options)
    driver.get("https://user.gamer.com.tw/login.php")
    try:
        userid = config['login']['userid']
        password = config['login']['password']
        driver.find_element_by_css_selector('#form-login [name=userid]').send_keys(userid)
        driver.find_element_by_css_selector('#form-login [name=password]').send_keys(password)
        time.sleep(random.uniform(1, 2))
        driver.find_element_by_id("btn-login").click()
        time.sleep(random.uniform(2, 3))

        with open('login_cookie.json', 'w', newline='') as f:
            json.dump(driver.get_cookies(), f)
    except:
        print('登入失敗')


def get_goods_url():
    """取得可透過觀看廣告兌換的商品網址"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.92 Safari/537.36',
    }
    fuli_url = 'https://fuli.gamer.com.tw/'

    goods_list = []
    for i in range(3):
        r = requests.get(f'{fuli_url}?page={i+1}', headers=headers)
        if r.status_code != requests.codes.ok:
            print('網頁抓取失敗:', r.status_code)
        soup = BeautifulSoup(r.text, 'html.parser')
        items_element = soup.select('.item-list-box .items-card')

        for item_element in items_element:
            if item_element.select_one('.type-tag').text.strip() != '抽抽樂':
                continue
            url = item_element.get('href')
            name = item_element.select_one('h2').text.strip()
            price = item_element.select_one('.price .digital').text.strip()
            goods = {
                'name': name,
                'price': price,
                'url': url
            }
            if goods not in goods_list:
                goods_list.append(goods)

    print('=' * 30)
    for goods in goods_list:
        print('●', goods['name'], goods['price'])
        print('--->', goods['url'])
    print('=' * 30)
    user_input_text = input(f'(數量:{len(goods_list)}) 確認是否抓取？')
    if user_input_text == 'y' or user_input_text == 'Y':
        return goods_list
    return None


class exchangeGoodsThread(threading.Thread):
    def __init__(self, index, url_queue, error_queue):
        threading.Thread.__init__(self)

        if url_queue.qsize() == 0:
            print(f'結束：{index}')
            return
        self.index = index
        self.url_queue = url_queue
        self.error_queue = error_queue
        self.driver = None
        self.url = None

    def run(self):
        """觀看廣告，兌換商品"""
        self.create_driver()
        self.load_cookie()

        while self.url_queue.qsize() > 0:
            # 取得商品的 URL
            self.url = self.url_queue.get()
            self.goto_goods_page()
            if not self.is_login():
                return

            # 重複觀看此商品廣告
            for i in range(int(config['settings']['watch_num'])):
                print(f'{self.index}：第 {i+1} 次執行：{self.url}')
                # 點擊前往"觀看廣告"
                need_break = self.click_watch_ad(timeout=15)
                if need_break:
                    break

                time.sleep(5)
                # 判斷是否已經自動跳到抽獎
                if 'buyD' not in self.driver.current_url:
                    # 點擊"確認觀看廣告"
                    need_break = self.click_confirm_watch_ad(timeout=10)
                    if need_break:
                        break
                    # 切換到廣告視窗 iframe 內
                    need_break = self.switch_to_ad_iframe(timeout=10)
                    if need_break:
                        break

                    time.sleep(5)
                    # 如果出現"繼續有聲播放"按鈕需點擊後繼續
                    self.click_continue_watch_ad(timeout=20)

                    time.sleep(10)
                    # 影片"播放完畢"或"可跳過"，則關閉影片
                    need_break = self.close_ad_iframe(timeout=10)
                    if need_break:
                        break

                time.sleep(3)
                # 看完廣告，送出抽獎資料
                need_break = self.send_lottery_info(timeout=10)
                if need_break:
                    break

                # 點擊'確認兌換商品'彈跳視窗
                need_break = self.click_continue_exchange_goods(timeout=10)
                if need_break:
                    break

                # 看完廣告、送出資料，返回商品頁
                self.goto_goods_page()

        print(f'--- 結束：{self.index} ---')
        self.driver.quit()

    def create_driver(self):
        """創建瀏覽器"""
        options = webdriver.ChromeOptions()
        options.add_argument("--mute-audio")    # 靜音
        # options.add_argument('--no-sandbox')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.driver = webdriver.Chrome(options=options)

        self.driver.set_page_load_timeout(15)
        try:
            self.driver.get("https://www.gamer.com.tw/")
        except TimeoutException:
            print(f'{self.index}: time out after 15 seconds when loading page')
            self.driver.execute_script('window.stop()')

    def load_cookie(self):
        """載入已登入的 cookie"""
        with open('login_cookie.json', 'r', newline='') as f:
            cookies = json.load(f)
        for cookie in cookies:
            self.driver.add_cookie(cookie)

    def goto_goods_page(self):
        """前往商品頁面"""
        try:
            self.driver.get(self.url)
        except TimeoutException:
            print(f'{self.index}: time out after 15 seconds when loading page')
            self.driver.execute_script('window.stop()')

    def is_login(self, timeout=10):
        """是否已登入"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.topbar_member-home'))
            )
        except Exception as e:
            print('登入失敗，退出')
            self.error_queue.put([self.url, '登入失敗'])
            self.driver.quit()
            return False
        return True

    def click_watch_ad(self, timeout=15):
        """點擊前往'觀看廣告'"""
        need_break = False
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.c-accent-o'))
            )
            btn_ad = self.driver.find_element_by_css_selector('a.c-accent-o')
            if 'is-disable' in btn_ad.get_attribute("class"):
                print(f'{self.index}：本日免費兌換次數已用盡')
                need_break = True
            btn_ad.click()
        except Exception as e:
            print(f'{self.index}：找不到"看廣告免費兌換"按鈕')
            self.error_queue.put([self.url, '找不到"看廣告免費兌換"按鈕'])
            need_break = True
        return need_break

    def click_confirm_watch_ad(self, timeout=10):
        """點擊'確認觀看廣告'"""
        # 判斷順序：確認觀看廣告 > 新商品答題 > 廣告能量補充中
        need_break = False
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'form [type="submit"]'))
            )
            self.driver.find_element_by_css_selector('form [type="submit"]').click()
        except Exception as e:
            try:
                # TODO:自動答題(新商品)
                WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '#question-1'))
                )
                print(f'{self.index}：第一次觀看需答題')
                self.error_queue.put([self.url, '第一次觀看需答題'])
                need_break = True
            except Exception as e:
                try:
                    WebDriverWait(self.driver, 3).until(
                        EC.text_to_be_present_in_element(
                            (By.CSS_SELECTOR, '.dialogify__body'),
                            "廣告能量補充中"
                        )
                    )
                    print(f'{self.index}：廣告能量補充中')
                    self.error_queue.put([self.url, '廣告能量補充中'])
                    need_break = True
                except Exception as e:
                    print(f'{self.index}：找不到"觀看廣告>確認"按鈕')
                    self.error_queue.put([self.url, '找不到"觀看廣告>確認"按鈕'])
                    time.sleep(180)
                    need_break = True
        return need_break

    def switch_to_ad_iframe(self, timeout=10):
        """切換到廣告視窗 iframe 內"""
        need_break = False
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, 'ins > div > iframe'))
            )
        except Exception as e:
            print(f'{self.index}：找不到"廣告"視窗')
            self.error_queue.put([self.url, '找不到"廣告"視窗'])
            # time.sleep(10)
            self.driver.quit()
            need_break = True
        return need_break

    def click_continue_watch_ad(self, timeout=20):
        """點擊'繼續有聲播放'按鈕，沒有則不需處理"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.videoAdUi .rewardDialogueWrapper:last-of-type .rewardResumebutton'))
            )
            self.driver.find_element_by_css_selector('.videoAdUi .rewardDialogueWrapper:last-of-type .rewardResumebutton').click()
        except Exception:
            pass

    def close_ad_iframe(self, timeout=10):
        """關閉影片，影片播放完畢或可跳過"""
        need_break = False
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 
                                            '.videoAdUiSkipButtonExperimentalText, ' +
                                            '#close_button #close_button_icon, ' +
                                            '#google-rewarded-video > img:nth-child(4)'))
            )
            self.driver.find_element_by_css_selector(
                '.videoAdUiSkipButtonExperimentalText, ' +
                '#close_button #close_button_icon, ' +
                '#google-rewarded-video > img:nth-child(4)'
                ).click()
        except Exception:
            # 判斷是否已經自動跳到抽獎
            try:
                WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '.agree-confirm-box'))
                )
            except Exception:
                try:
                    # 出現"發生錯誤，請重新嘗試(1)"視窗
                    WebDriverWait(self.driver, 3).until(
                        EC.text_to_be_present_in_element(
                            (By.CSS_SELECTOR, '.dialogify__body'), "發生錯誤"
                        )
                    )
                    print(f'{self.index}：發生錯誤，請重新嘗試')
                    self.error_queue.put([self.url, '發生錯誤，請重新嘗試'])
                    # driver.quit()
                    need_break = True
                except Exception as e:
                    print(f'{self.index}：廣告播放失敗 或 找不到關閉影片按鈕')
                    self.error_queue.put([self.url, '廣告播放失敗 或 找不到關閉影片按鈕'])
                    time.sleep(180)
                    need_break = True
        return need_break

    def send_lottery_info(self, timeout=10):
        """送出抽獎資料 (已看完廣告)"""
        need_break = False
        try:
            # "我已閱讀注意事項，並確認兌換此商品"選擇 checkbox
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.agree-confirm-box'))
            )
            self.driver.find_element_by_css_selector(".agree-confirm-box").click()
            # "確認兌換"按鈕
            WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.pbox-btn a.c-primary'))
            )
            self.driver.find_element_by_css_selector(".pbox-btn a.c-primary").click()
        except Exception:
            print(f'{self.index}：找不到"我已閱讀注意事項，並確認兌換此商品"或"確認兌換"按鈕')
            self.error_queue.put([self.url, '找不到"我已閱讀注意事項，並確認兌換此商品"或"確認兌換"按鈕'])
            # time.sleep(10)
            need_break = True
        return need_break

    def click_continue_exchange_goods(self, timeout=10):
        """點擊'確認兌換商品'彈跳視窗"""
        need_break = False
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.dialogify__content [type="submit"]'))
            )
            self.driver.find_element_by_css_selector('.dialogify__content [type="submit"]').click()
        except Exception:
            print(f'{self.index}：找不到"彈跳視窗內確定"按鈕')
            self.error_queue.put([self.url, '找不到"彈跳視窗內確定"按鈕'])
            # time.sleep(10)
            need_break = True
        return need_break


def exchange_all_goods(is_crawl=True, goods_urls=None):
    """兌換全部商品(觀看廣告)，使用多執行緒"""
    if is_crawl:
        items_url = get_goods_url()
        urls = [items['url'] for items in items_url]
    else:
        urls = goods_urls

    if not urls:
        print('沒有商品網址')

    time_start = time.time()
    # 建立商品網址的 Queue
    url_queue = queue.Queue()
    # 建立失敗商品網址的 Queue
    error_queue = queue.Queue()

    # 將資料放入 Queue
    for url in urls:
        url_queue.put(url)

    # 設定執行緒數量
    # 同時執行太多，容易變慢或出現"廣告能量補充中"
    thread_num = int(config['settings']['thread_num'])
    if len(urls) < thread_num:
        thread_num = len(urls)
    threads = []
    for index in range(thread_num):
        threads.append(exchangeGoodsThread(index, url_queue, error_queue))
        threads[index].start()
        print(f'執行緒 {index} 開始運行')
        time.sleep(3)

    # 等待所有子執行緒結束
    for index in range(len(threads)):
        threads[index].join()

    print('========== 全數結束 ==========')
    print(f'耗時：{time.time()-time_start:.0f} 秒')
    # 列出發生錯誤的網址
    while error_queue.qsize() > 0:
        print(error_queue.get())


if __name__ == "__main__":
    # goods_urls = [
    #     'https://fuli.gamer.com.tw/shop_detail.php?sn=2246',
    #     'https://fuli.gamer.com.tw/shop_detail.php?sn=2219',
    #     'https://fuli.gamer.com.tw/shop_detail.php?sn=2221',
    # ]
    # exchange_all_goods(is_crawl=False, goods_urls=goods_urls)
    exchange_all_goods(is_crawl=True)


    # 登入巴哈網站，儲存 cookie
    # save_cookie()
