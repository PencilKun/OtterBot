#!/usr/bin/env python3
import sys
import os
import django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DJANGO_SETTINGS_MODULE'] = 'FFXIV.settings'
from FFXIV import settings
django.setup()
from ffxivbot.handlers.QQUtils import *
from asgiref.sync import async_to_sync
from ffxivbot.models import *
import re
import json
import time
import requests
import string
import random
import base64
import logging
from logging.handlers import TimedRotatingFileHandler
import traceback
from bs4 import BeautifulSoup as bs
import argparse
from channels.layers import get_channel_layer
from django.db import connection, connections

logging.basicConfig(
                level = logging.INFO,
                format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers = {
                        TimedRotatingFileHandler(
                                        "/home/FFXIVBOT/log/crawl_manhua.log",
                                        when="D",
                                        backupCount = 10
                                    )
                        }
            )
channel_layer = get_channel_layer()

def GetConfig():
    parser = argparse.ArgumentParser(description='Territory Auto-Sync Script')

    parser.add_argument('-n', '--new', action='store_true',
                        help='Crawl new comic page.')
    # Parse args.
    args = parser.parse_args()
    # Namespace => Dictionary.
    kwargs = vars(args)
    return kwargs

def GetXingQiYi():
    try:
        Headers ={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"}
        Url = "https://forum.gamer.com.tw/search.php?bsn=47157&q=%E3%80%90%E6%83%85%E5%A0%B1%E3%80%91%E3%80%8A%E6%98%9F%E6%9C%9F%E4%B8%80%E7%9A%84%E8%B1%90%E6%BB%BF%E3%80%8B%E5%85%B6+&page=1&field=title&advancedSearch=1&dateType=2week"
        with open("/home/FFXIVBOT/collectstatic/xingqiyi/dmID.txt","r") as f:
            ID = int(f.read())
            f.close()
        with open("/home/FFXIVBOT/collectstatic/xingqiyi/dmTitle.txt","r") as f:
            Old_Title = f.read()
            f.close()
        logging.info("Start crawl XingQiYi")
        Results = requests.get(url=Url,headers=Headers)
        Results = bs(Results.text,"html.parser")
        Results = Results.findAll(attrs={"class":"flex"})
        logging.info("Comics are being filtered")
        for Result in Results:
            Title = Result.find('a').getText().strip()
            Title = re.findall(r"《星期一的豐滿》其 (\d+)(.*)",Title)
            if Title:
                logging.info("Found comics,starting comparison")
                Img_Url = Result.find('img').get('src',"").replace("pbs.twimg.com","twimg.pencilss.top")
                if int(Title[0][0]) > ID:
                    Img_Content = requests.get(Img_Url, headers=Headers).content
                    ID = Title[0][0]
                    Title = "".join(Title[0])
                    with open("/home/FFXIVBOT/collectstatic/xingqiyi/{}.jpg".format(ID),'wb') as fp:
                        fp.write(Img_Content)
                        fp.close()
                    with open("/home/FFXIVBOT/collectstatic/xingqiyi/dmTitle.txt","w") as f:
                        f.write(Title)
                        f.close()
                    with open("/home/FFXIVBOT/collectstatic/xingqiyi/dmID.txt","w") as f:
                        f.write(str(ID))
                        f.close()
                    logging.info("Save comics OK")
                    PushMsg(Img_Url,Title,True)
                    break
            else:
                continue
        return True
    except Exception as e:
        logging.error(traceback.print_exc())
        logging.error('Func GetXingQiYi error:', e)
        return False


def PushMsg(url,title,push=False):
    logging.info("Start pushing messages")
    Groups = QQGroup.objects.filter(milk=True)
    Bots = QQBot.objects.all()
    try:
        for Group in Groups:
            for Bot in Bots:
                if isinstance(json.loads(Bot.group_list),list):
                    Group_ID_List = [str(item.get("group_id","")) for item in json.loads(Bot.group_list)] if json.loads(Bot.group_list) else []
                if str(Group.group_id) not in Group_ID_List: continue
                Msg = f"星期一的丰满{title}:\n[CQ:image,file={url}]"
                JData = {
                            "action":"send_group_msg",
                            "params":{"group_id":int(Group.group_id),"message":Msg},
                            "echo":"",
                }
                logging.info(f"Pushing to group: {Group}")
                if not push: continue
                if not Bot.api_post_url:
                    async_to_sync(channel_layer.send)(Bot.api_channel_name, {"type": "send.event","text": json.dumps(JData),})
                else:
                    Url = os.path.join(Bot.api_post_url, "{}?access_token={}".format(JData["action"], Bot.access_token))
                    Headers = {"Content-Type": "application/json",
                               "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0"
                    }
                    R = requests.post(url=Url, headers=Headers, data=json.dumps(JData["params"]), timeout=5)
                    if R.status_code!=200:
                        logging.error(R.text)
        logging.info("Messages push completed")
    except Exception as e:
        logging.error(traceback.print_exc())
        logging.error(f"Func PushMsg error:{e}")
    return

if __name__ == "__main__":
    print("Crawling XingQiyi Start, check log file log/crawl_manhua.log")
    GetXingQiYi()
