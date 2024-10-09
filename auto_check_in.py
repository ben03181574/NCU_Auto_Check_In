import os
import sys
import time
import json
import argparse
from datetime import datetime
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.common.exceptions import NoSuchElementException
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler

import smtplib
from smtplib import SMTPAuthenticationError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from telegram import Bot
from telegram.ext import Updater, CommandHandler




# check for send_telegram_message
def send_telegram_message(message):
    try:
        bot.send_message(chat_id=telegram_chat_id, text=message)
        print(f"=====Telegram 訊息傳送成功: {message}=====")
    except Exception as e:
        print(f"=====Telegram 訊息傳送失敗: {e}=====")


def send_email(args, title):

    # create MIMEMultipart
    msg = MIMEMultipart()

    # define sender and receiver
    msg['From'] = args['email_account']
    msg['To'] = args['email_account']
    
    msg['Subject'] = title

    html = """ \
        <html>
          <head></head>
          <body>
            <p>您好，<br>
               詳細簽到/簽退資訊可至<a href="https://cis.ncu.edu.tw/HumanSys/student/stdSignIn">簽到系統</a>查看。
            </p>
          </body>
        </html>
    """
    # create html content
    msg.attach(MIMEText(f'{html}\n\n', "html"))
    
    # 建立 SMTP 服務
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.login(args['email_account'],  args['email_passwd'])

    server.send_message(msg)  # send email
    server.quit()  # close the email channel
    
    print("=====郵件寄送成功=====")

def login(driver, args):
    driver.get('https://portal.ncu.edu.tw/login')

    account = driver.find_element(By.ID, "inputAccount")
    passwd = driver.find_element(By.ID, "inputPassword")
    send_btn = driver.find_element(By.CLASS_NAME, "btn-primary")
    
    ActionChains(driver) \
        .send_keys_to_element(account, args['account']) \
        .send_keys_to_element(passwd, args['passwd']) \
        .click(send_btn) \
        .perform()

def check_in(driver, args):
    
    reset_btn = driver.find_element(By.ID, "resetTime")
    signin_btn = driver.find_element(By.ID, "signin")
    
    current_time = time.strftime("%Y/%m/%d-", time.localtime())+driver.find_element(By.ID, "timer").text
    
    ActionChains(driver) \
        .click(reset_btn) \
        .click(signin_btn) \
        .perform()
    print("=====人事簽到成功=====")
    print("args['send_telegram_bot']: ",args['send_telegram_bot'])
    # if args['send_email']:
    #     send_email(args, "簽到成功-"+current_time)
    if args['send_telegram_bot'] == "True":
        print("簽到成功")
        current_time = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())
        send_telegram_message(f"簽到成功，簽到時間為 {current_time}")
def check_out(driver, args):
    
    reset_btn = driver.find_element(By.ID, "resetTime")
    work_field = driver.find_element(By.ID, "AttendWork")
    signout_btn = driver.find_elements(By.ID, "signout")

    current_time = time.strftime("%Y/%m/%d-", time.localtime())+driver.find_element(By.ID, "timer").text
    
    if signout_btn:
        signout_btn = signout_btn[0]
    else:
        raise NoSuchElementException("=====人事尚未簽到=====")        
    ActionChains(driver) \
        .click(reset_btn) \
        .send_keys_to_element(work_field, args['work']) \
        .click(signout_btn) \
        .perform()
    print("=====人事簽退成功=====")
    
    # if args['send_email']:
    #     send_email(args, "簽退成功-"+current_time)
    if args['send_telegram_bot'] == "True":
        current_time = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())
        send_telegram_message(f"簽退成功，簽退時間為 {current_time}")
def main(args, mission):
    try:
        service = Service(executable_path=args['driver_path']+'/msedgedriver.exe')
        options = webdriver.EdgeOptions()
        driver = webdriver.Edge(service=service, options=options)

        # login
        login(driver,args)

        # jump to HumanSys page
        driver.get("https://cis.ncu.edu.tw/HumanSys/student/stdSignIn")
        jumpBtn = driver.find_elements(By.CSS_SELECTOR, ".jumbotron .btn.btn-primary")
        if jumpBtn:
            jumpBtn[0].click()
        else:
            raise NoSuchElementException("=====帳號密碼錯誤=====")

        # find the target row
        table = driver.find_element(By.ID, "table1")
        rows = table.find_elements(By.TAG_NAME, "tr")
        tgt_row = None
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if cells and cells[1].text == args['case']:
                tgt_row = cells

        # jump to check-in page
        tgt_row[5].find_element(By.TAG_NAME, "a").click()

        # check-in & check-out
        if mission == "check-in":
            check_in(driver, args)
        elif mission == "check-out":
            check_out(driver, args)
        
    except NoSuchElementException as e:
        print(str(e).split("Message: ", 1)[-1])
    except SMTPAuthenticationError:
        print("=====郵件寄送失敗=====")
    finally:
        #quit
        driver.quit()

if __name__ == "__main__":
    
    args = dict()
    with open(os.path.dirname(__file__)+'./config.json', 'r', encoding='utf-8') as f:
        args.update(json.load(f))

    # telegram bot setting 
    telegram_chat_id=args['telegram_chat_id']
    telegram_bot_token=args['telegram_bot_token']
    bot = Bot(token=telegram_bot_token)

    updater = Updater(token=telegram_bot_token, use_context=True)
    dispatcher = updater.dispatcher
    # telegram bot setting 

    work_hours = []
    work_hour = args["work_hour"]
    max_hour_per_day = args["max_hour_per_day"]
    work_dates = args["work_dates"]
    work_date = int(work_hour/max_hour_per_day) if work_hour%max_hour_per_day==0 else int(work_hour/max_hour_per_day)+1

    if work_date > len(work_dates):
        print("=====設定天數不足=====")
    elif max_hour_per_day > 8:
        print("=====設定工時過長=====")
    else:  
        for i in range(work_date):
            work_hours.append(max_hour_per_day if work_hour-max_hour_per_day>0 else work_hour)
            work_hour = work_hour-max_hour_per_day

        assert len(work_hours)<=len(work_dates)

        scheduler = BlockingScheduler(timezone="Asia/Taipei")
        for i in range(len(work_hours)):
            scheduler.add_job(main, 'date', \
                              run_date=datetime(int(work_dates[i].split('/')[0]), \
                                                int(work_dates[i].split('/')[1]), \
                                                int(work_dates[i].split('/')[2]), \
                                                9, 0, 0), \
                              args=[args, "check-in"])
            scheduler.add_job(main, 'date', \
                              run_date=datetime(int(work_dates[i].split('/')[0]), \
                                                int(work_dates[i].split('/')[1]), \
                                                int(work_dates[i].split('/')[2]), \
                                                9+work_hours[i], 0, 0), \
         
                              args=[args, "check-out"])

        scheduler.start()
        print("start...")

# scheduler.shutdown(wait=False)
# print(scheduler.get_jobs())