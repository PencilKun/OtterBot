from .QQEventHandler import QQEventHandler
from .QQUtils import *
from ffxivbot.models import *
import logging
import json
import random
import requests
import feedparser
from bs4 import BeautifulSoup
from django.db.utils import IntegrityError


def SearchUser(Name,Channel="bilibili"):
    Weibo_Url = f"https://m.weibo.cn/api/container/getIndex?containerid=100103type%3D3%26q%3D{Name}&page_type=searchall"
    Bili_Url = f"https://api.bilibili.com/x/web-interface/search/type?&page=1&page_size=5&order=fans&search_type=bili_user&keyword={Name}"
    H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0"}
    S = requests.session()
    S.headers = H
    try:
        Users_Info = []
        if Channel == "weibo":
            R = S.get(Weibo_Url).json()
            Cards = R.get("data",{"cards": []}).get("cards",[])
            for Card in Cards:
                if Card.get("card_type") == 11:
                    for Card_Group in Card["card_group"][:5]:
                        User_Name = Card_Group.get("user",{}).get("screen_name","None")
                        Uid = Card_Group.get("user",{}).get("id","None")
                        Verified_Reason = Card_Group.get("user",{}).get("verified_reason","None")
                        Users_Info.append({"User_Name":User_Name,"Uid":Uid,"Verified_Reason":Verified_Reason})
                else:
                    continue
        else:
            S.get("https://www.bilibili.com")
            R = S.get(Bili_Url).json()
            Results = R.get("data",{"result": []}).get("result",[])
            for Result in Results:
                User_Name = Result.get("uname","None")
                Uid = Result.get("mid","None")
                Verified_Reason = Result.get("official_verify",{"desc": "None"}).get("desc")
                Users_Info.append({"User_Name":User_Name,"Uid":Uid,"Verified_Reason":Verified_Reason})
        return Users_Info
    except Exception as e:
        logging.error(f"Func_SearchUser_Error:{e}")
        return []


def QQGroupCommand_rss(*args, **kwargs):
    try:
        Global_Config = kwargs["global_config"]
        Group = kwargs["group"]
        User_Info = kwargs["user_info"]
        QQ_BASE_URL = Global_Config["QQ_BASE_URL"]
        Action_List = []
        Receive = kwargs["receive"]
        User_Id = Receive["user_id"]
        Group_Id = Receive["group_id"]
        Msg = ""
        Params_Msg = Receive["message"].replace("/rss","",1).strip()
        Second_Command = Params_Msg.split(" ")[0].strip()
        if Second_Command == "add":
            Params_Name = Params_Msg.replace('add','',1).strip()
            if Params_Name.startswith("w:"):
                RSS_Users = RSSUser.objects.filter(name=Params_Name[2:],channel="weibo")
            elif Params_Name.startswith("b:"):
                RSS_Users = RSSUser.objects.filter(name=Params_Name[2:],channel="bilibili")
            else:
                RSS_Users = []
            if RSS_Users:
                RSS_User = RSS_Users[0]
                RSS_Content = json.loads(RSS_User.content)[0]["title"]
                Group.rss_subscription.add(RSS_User)
                Group.save()
                Msg = f"{RSS_User.name} 的{RSS_User.channel}订阅添加成功\n{RSS_Content}"
            else:
                Msg = f"未设置 {Params_Name} 的订阅计划,自助配置\n/rss config {Params_Name}\n或未标注渠道信息,如(w:微,b:bilibili):\n/rss add w:最终幻想14 \n/rss add b:最终幻想14"

        elif Second_Command == "del":
            Params_Name = Params_Msg.replace('del','',1).strip()
            if Params_Name.startswith("w:"):
                RSS_Users = RSSUser.objects.filter(name=Params_Name[2:],channel="weibo")
            elif Params_Name.startswith("b:"):
                RSS_Users = RSSUser.objects.filter(name=Params_Name[2:],channel="bilibili")
            if(len(RSS_Users)==0):
                Msg = f"未设置 {Params_Name} 的订阅计划"
            else:
                RSS_User = RSS_Users[0]
                Group.rss_subscription.remove(RSS_User)
                Group.save()
                Msg = f"{RSS_User.name}---{RSS_User.channel} 的订阅删除成功"
        elif Second_Command == "list":
            RSS_Users = Group.rss_subscription.all()
            Msg = "本群订阅的用户有：\n"
            for RSS_User in RSS_Users:
                Msg += f"{RSS_User.name}---{RSS_User.channel}\n"
        elif Second_Command == "config":
            Params_Name = Params_Msg.replace('config','',1).strip()
            if Params_Name.startswith("w:"):
                Params_Name = Params_Name[2:]
                try:
                    Uid = int(Params_Name)
                    Name = GetRSSName(Uid,"weibo")
                    if Name == "None":
                        Msg = "未找到有效用户。"
                    else:
                        RSU, Create = RSSUser.objects.update_or_create(uid=Uid,channel="weibo",defaults={'name': Name})
                        Msg = f"已配置微博订阅信息【{Name}】--{Uid}"
                except Exception as e:
                    logging.error(f"Second_Command_configw:_Error:{e}")
                    Search_Results = SearchUser(Params_Name,"weibo")
                    Msg = f"未配置【{Params_Name}】微博订阅，请按以下搜索结果添加所需博主(只显示前五)"
                    for Result in Search_Results:
                        Msg += f"\n/rss config w:{Result['Uid']}\n【Info】:{Result['User_Name']}【V】:{Result['Verified_Reason']}"
            elif Params_Name.startswith("b:"):
                Params_Name = Params_Name[2:]
                try:
                    Uid = int(Params_Name)
                    Name = GetRSSName(Uid,"bilibili")
                    if Name == "None":
                        Msg = "未找到有效用户。"
                    else:
                        RSU, Create = RSSUser.objects.update_or_create(uid=Uid,channel="bilibili",defaults={'name': Name})
                        Msg = f"已配置B站动态订阅信息【{Name}】--{Uid}"
                except Exception as e:
                    logging.error(f"Second_Command_configb:_Error:{e}")
                    Search_Results = SearchUser(Params_Name,"bilibili")
                    Msg = f"未配置【{Params_Name}】B站动态订阅，请按以下搜索结果添加所需UP主(只显示前五)"
                    for Result in Search_Results:
                        Msg += f"\n/rss config b:{Result['Uid']}\n【Info】:{Result['User_Name']}【V】:{Result['Verified_Reason']}"
            else:
                Msg="未标注渠道信息，以w:或b:开头+名称"
        else:
            Msg = "错误的命令，二级命令有:\"add\", \"del\", \"list\", \"config\""

        Reply_Action = reply_message_action(Receive, Msg)
        Action_List.append(Reply_Action)
        return Action_List
    except Exception as e:
        Msg = "Command_rss_Error: {}"
        Action_List.append(reply_message_action(Receive, Msg.format(type(e))))
        logging.error(Msg.format(e))
        return Action_List


