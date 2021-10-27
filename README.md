# 自動觀看「巴哈姆特 勇者福利社」的廣告並參加商品抽獎

巴哈姆特的「[勇者福利社](https://fuli.gamer.com.tw/)」可以參加抽將、競標、任務，而參加抽獎(也稱為抽抽樂)除了使用巴幣，也可以使用看廣告的方式兌換抽獎資格。

本專案將看廣告參加抽獎的這一過程自動化，節省自行手動點擊的麻煩。


----------------------

## Installation

此專案會使用到以下 Python 套件，請先安裝：

* [beautifulsoup4](https://pypi.org/project/beautifulsoup4/)
* [selenium](https://pypi.org/project/selenium/)
* [requests](https://pypi.org/project/requests/)

Selenium 需使用 chromedriver.exe 驅動程式操作 Chrome 連覽器，chromedriver.exe 要跟電腦安裝的 Chrome 相同版本，前往此處下載 [Chrome 驅動](https://chromedriver.chromium.org/downloads)，將其下載檔案解壓縮後覆蓋掉源專案內同檔名檔案。

## How To Use It

為了登入巴哈姆特網站，並儲存登入後的 cookie，需先至 config.ini 檔案內設定你的巴哈帳密：

```ini
userid = <your_userid>
password = <your_password>
```

程式執行：

```python
save_cookie()
```

<br>

完成後才能開始"看廣告兌換抽獎資格"：

```python
exchange_all_goods(is_crawl=True)
```

會自動開啟瀏覽器，抓取目前"可看廣告兌換抽獎資格"的商品。

## Config

config.ini 檔案內除了巴哈姆特的帳號密碼，還有其他可以設定：

```ini
[settings]
; 最多同時執行的執行緒數量 (同時執行太多，容易變慢或"廣告能量補充中")
thread_num = 3
; 一個商品最多觀看廣告次數 (如果提前結束會跳離)
watch_num = 15
```

## Matters Needing Attention

1. 目前一種商品一天最多可以觀看 10 次廣告，也就是 10 次抽獎機會。
2. 若載入廣告發生問題，有可能是阻檔廣告的瀏覽器擴充防護功能（如：AdBlock、uBlock、Avira、Avast、Kaspersky...等）所導致，請嘗試停用或加入白名單設定，方可正常觀看廣告。
3. 點選觀看廣告時，若跳出「廣告能量補充中，請稍後再試」視窗，即表示目前無任何廣告可供觀看，請稍後再嘗試。
4. 因為某些廣告如果有其他 Chrome 在使用就不會播放，因此執行期間不要使用 Chrome 瀏覽器，或者可以使用但不要把視窗最大化。


