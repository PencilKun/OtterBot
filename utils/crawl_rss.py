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
import feedparser
import string
import random
import codecs
import urllib
import base64
import logging
from logging.handlers import TimedRotatingFileHandler
import traceback
from bs4 import BeautifulSoup as bs
from channels.layers import get_channel_layer
from django.db import connection, connections
from multiprocessing.dummy import Pool as ThreadPool

logging.basicConfig(
                level = logging.INFO,
                format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers = {
                        TimedRotatingFileHandler(
                                        "/home/FFXIVBOT/log/crawl_rss.log",
                                        when="D",
                                        backupCount = 10
                                    )
                        }
            )
Channel_Layer = get_channel_layer()

def PushGroupMsg(RSSUser,Entry,Push=False):
    Groups = RSSUser.subscribed_by.all()
    Bots = QQBot.objects.all()
    for Group in Groups:
        for Bot in Bots:
            if isinstance(json.loads(Bot.group_list),list):
                Group_ID_List = [str(item.get("group_id","")) for item in json.loads(Bot.group_list)] if json.loads(Bot.group_list) else []
            if str(Group.group_id) not in Group_ID_List: continue
            try:
                Msg = [
                    {
                        "type": "text",
                        "data": {
                            "text": f"{RSSUser.name}---{RSSUser.channel}\n{Entry['Entry_Text']}\n{Entry['Entry_Url']}"
                        }
                    },
                    {
                        "type": "image",
                        "data": {
                            "file": Entry["Entry_Img"]
                        }
                    }
                ]
                logging.info(f"Pushing {Entry['Entry_Url']} to group: {Group}")
                if Push:
                    JData = {
                        "action": "send_group_msg",
                        "params": {"group_id": int(Group.group_id), "message": Msg},
                        "echo": "active_msg"
                    }
                    if not Bot.api_post_url:
                        async_to_sync(Channel_Layer.send)(Bot.api_channel_name, {"type": "send.event", "text": json.dumps(JData)})
                    else:
                        Url = os.path.join(Bot.api_post_url, "{}?access_token={}".format(JData["action"], Bot.access_token))
                        Headers = {"Content-Type": "application/json",
                                   "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0"
                                  }
                        R = requests.post(url=Url, headers=Headers, data=json.dumps(JData["params"]), timeout=5)
                        if R.status_code!=200:
                            logging.error(R.text)
            except requests.ConnectionError as e:
                logging.error(f"Pushing {Entry['Entry_Url']} to group: {Group} ConnectionError")
            except requests.ReadTimeout as e:
                logging.error(f"Pushing {Entry['Entry_Url']} to group: {Group} timeout")
            except Exception as e:
                logging.error(traceback.print_exc())
                logging.error(f"Error at pushing to {Group}: {e}\n{JData}")


def CrawlRSS(RSSUser):
    Uid = RSSUser.uid
    Name = RSSUser.name
    Channel = RSSUser.channel
    Contents = json.loads(RSSUser.content)
    if Channel == "weibo":
        Url = f"https://rsshub.pencilss.top/weibo/user/{Uid}"
    elif Channel == "bilibili":
        Url = f"https://rsshub.pencilss.top/bilibili/user/dynamic/{Uid}"
    try:
        logging.info(f"Begin crawling 【{Name}】---【{Channel}】")
        R = feedparser.parse(Url)
        if(R.status == 200):
            if Contents:
                Entries = json.loads(json.dumps(R.entries))
                Contents = [C["link"] for C in Contents] 
                Entries = [ E for E in Entries if E["link"] not in Contents ]
            else:
                Entries = [R.entries[0]]
            if Entries:
                RSSUser.content=json.dumps(R.entries)
                RSSUser.save()
                for Entry in Entries[:2]:
                    Entry_Url = Entry["link"]
                    Entry = bs(Entry["summary"],"html.parser")
                    Entry_Text = Entry.text
                    Entry_Img = ""
                    if Entry.findAll("img"):
                        for Img in Entry.findAll("img"):
                            if Img.get("style","") == "":
                                Entry_Img = Img.get("src","")
                                break
                    Entry_Data = dict(zip(["Entry_Text","Entry_Img","Entry_Url"],[Entry_Text,Entry_Img,Entry_Url]))
                    PushGroupMsg(RSSUser, Entry_Data, True)
            else:
                logging.info(f"No new Entries 【{Name}】---【{Channel}】")
            logging.info(f"Crawled 【{Name}】---【{Channel}】")
        else:
            logging.error(f"RSS request error,code:{R.status} 【{Name}】---【{Channel}】")
    except Exception as e:
        logging.error(traceback.print_exc())
        logging.error(f"Error at Func CrawlRSS:{e}")
    return

def Crawl():
    RUS = RSSUser.objects.all()
    Pools = ThreadPool(10)
    Pools.map(CrawlRSS, RUS)


if __name__ == "__main__":
    print("Crawling RSS Service Start, check log file log/crawl_rss.log")
    try:
        Crawl()
    except Exception as e:
        logging.error(e)

