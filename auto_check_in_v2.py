import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
import time
from telegram import Bot
from telegram.ext import Updater

# check for send_telegram_message
def send_telegram_message(message):
    try:
        bot.send_message(chat_id=telegram_chat_id, text=message)
        print(f"=====Telegram 訊息傳送成功: {message}=====")
    except Exception as e:
        print(f"=====Telegram 訊息傳送失敗: {e}=====")

def login():
    # 建立 session 共享 Cookie
    session = requests.Session()
    
    # 取得 Portal 網站的 CSRF Token
    response = session.get('https://portal.ncu.edu.tw/login')
    csrf_token = session.cookies.get('XSRF-TOKEN')
    
    print("CSRF Token:", csrf_token)
    
    # 使用 CSRF Token 發送 POST 請求進行登入
    login_payload = {
        'username': PARAMS['username'],
        'password': PARAMS['password'],
        '_csrf': csrf_token
    }
    
    login_response = session.post('https://portal.ncu.edu.tw/login', data=login_payload)
    
    # 發送 GET 請求取得 JSON 數據
    response = session.get('https://portal.ncu.edu.tw/backends/menu')
    json_data = response.json()
    
    # 遍歷 menuEntries 以取得人事系統 URL
    human_sys_url = ""
    for entry in json_data['menuEntries']:
        for subentry in entry['submenu']:
            for item in subentry['submenu']:
                if item['data'] and item['data']['englishName'] == "Human Resource System":
                    human_sys_url = item['url']
                    break
    
    # 檢查是否找到 Human Resource System URL
    if human_sys_url:
        print(f"Human Resource System URL: {human_sys_url}")
    else:
        print("Human Resource System URL not found.")
    
    # 透過 portal 進入人事系統 (避免檢核)
    
    response = session.get('https://portal.ncu.edu.tw'+human_sys_url)

    return session

def get_token_value(session):
    response = session.get('https://cis.ncu.edu.tw/HumanSys/student/stdSignIn')
    
    # BeautifulSoup 解析 HTML 内容
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 找出 name 為 '_token' 的 input 元素，提取 token_value
    token_input = soup.find('input', {'name': '_token'})
    token_value = token_input['value'] if token_input else None
    
    print(f"Token: {token_value}")
    
    return token_value

def get_idNo(session, id):
    # 發送 GET 請求取得 JSON 數據
    response = session.get('https://cis.ncu.edu.tw/HumanSys/student/stdSignIn/create?ParttimeUsuallyId='+id)
    # BeautifulSoup 解析 HTML 内容
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 找出 name 為 '_token' 的 input 元素，提取 token_value
    idNo_input = soup.find('input', {'id': 'idNo'})
    idNo_value = idNo_input['value'] if idNo_input else None

    return idNo_value

# 使用 CSRF Token 發送 POST 請求進行登入
def signin(session, id, token_value):
    login_payload = {
        'functionName': 'doSign',
        'idNo': '',
        'ParttimeUsuallyId': id,
        'AttendWork': '',
        '_token': token_value,
    }
    
    login_response = session.post('https://cis.ncu.edu.tw/HumanSys/student/stdSignIn_detail', data=login_payload)
    current_time = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())
    send_telegram_message(f"簽到成功，簽到時間為 {current_time}")
    print("簽到完成...")

# 使用 CSRF Token 發送 POST 請求進行登入
def signout(session, id, token_value, idNo, attendwork):
    login_payload = {
        'functionName': 'doSign',
        'idNo': idNo,
        'ParttimeUsuallyId': id,
        'AttendWork': attendwork,
        '_token': token_value,
    }
    
    login_response = session.post('https://cis.ncu.edu.tw/HumanSys/student/stdSignIn_detail', data=login_payload)
    current_time = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())
    send_telegram_message(f"簽退成功，簽退時間為 {current_time}")
    print("簽退完成...")

def main(PARAMS, mission):
    status = login()

    if mission == "check-in":
        signin(status, PARAMS['ParttimeUsuallyId'], get_token_value(status))
    elif mission == "check-out":
        signout(status, PARAMS['ParttimeUsuallyId'], get_token_value(status), get_idNo(status, PARAMS['ParttimeUsuallyId']), PARAMS['AttendWork'])

if __name__ == "__main__":
    
    PARAMS = dict()
    
    with open(os.path.dirname(__file__)+'./config_v2.json', 'r', encoding='utf-8') as f:
        PARAMS.update(json.load(f))

    scheduler = BlockingScheduler(timezone="Asia/Taipei")

    # telegram bot setting 
    telegram_chat_id=PARAMS['telegram_chat_id']
    telegram_bot_token=PARAMS['telegram_bot_token']
    bot = Bot(token=telegram_bot_token)

    updater = Updater(token=telegram_bot_token, use_context=True)
    dispatcher = updater.dispatcher
    # telegram bot setting 
    
    for datetime_str in PARAMS['checkin_datetimes']:
        date_parts = [int(part) for part in datetime_str.split('/')]
        run_date = datetime(date_parts[0], date_parts[1], date_parts[2], date_parts[3], date_parts[4])
        scheduler.add_job(main, 'date', run_date=run_date, args=[PARAMS, "check-in"])
    for datetime_str in PARAMS['checkout_datetimes']:
        date_parts = [int(part) for part in datetime_str.split('/')]
        run_date = datetime(date_parts[0], date_parts[1], date_parts[2], date_parts[3], date_parts[4])
        scheduler.add_job(main, 'date', run_date=run_date, args=[PARAMS, "check-out"])

    try:
        print("開始排程任務...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("排程停止運行")
        scheduler.shutdown()