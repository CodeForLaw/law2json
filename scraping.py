
import sys
import json

import requests
from parse import *
from bs4 import BeautifulSoup
import hashlib
import subprocess

import re

display = False

host = "https://elaws.e-gov.go.jp"

tt_ksuji = str.maketrans('一二三四五六七八九〇壱弐参', '1234567890123')

re_suji = re.compile(r'[十拾百千万億兆\d]+')
re_kunit = re.compile(r'[十拾百千]|\d+')
re_manshin = re.compile(r'[万億兆]|[^万億兆]+')

TRANSUNIT = {'十': 10,
             '拾': 10,
             '百': 100,
             '千': 1000}
TRANSMANS = {'万': 10000,
             '億': 100000000,
             '兆': 1000000000000}


def kansuji2arabic(string, sep=False):
    """漢数字をアラビア数字に変換"""

    def _transvalue(sj, re_obj=re_kunit, transdic=TRANSUNIT):
        unit = 1
        result = 0
        for piece in reversed(re_obj.findall(sj)):
            if piece in transdic:
                if unit > 1:
                    result += unit
                unit = transdic[piece]
            else:
                val = int(piece) if piece.isdecimal() else _transvalue(piece)
                result += val * unit
                unit = 1

        if unit > 1:
            result += unit

        return result

    transuji = string.translate(tt_ksuji)
    for suji in sorted(set(re_suji.findall(transuji)), key=lambda s: len(s),
                           reverse=True):
        if not suji.isdecimal():
            arabic = _transvalue(suji, re_manshin, TRANSMANS)
            arabic = '{:,}'.format(arabic) if sep else str(arabic)
            transuji = transuji.replace(suji, arabic)

    return transuji



def log(msg):
    from datetime import datetime
    now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    if display:
        print("["+now+"] "+msg)

class Item:
    def __init__( self, title, text):
        self.title = title.strip()
        if len(text.strip().split("　", 1)) != 1:
            self.text = text.strip().split("　", 1)[1]
        else:
            self.text = text.strip()

    def json(self):
        return {
                "title": self.title,
                "text": self.text,
        }

    def __str__(self):
        return "- {}: {}".format(self.title,self.text)

class Paragraph:
    
    def __init__( self, title = "", num = "", text = ""):
        self.num = num.strip()
        self.title = title.strip()
        if len(text.strip().split("　", 1)) != 1:
            self.text = text.strip().split("　", 1)[1]
        else:
            self.text = text.strip()
        self.items = []

    def json(self):
        res = {
                "title": self.title,
                "text": self.text,
        }
        if len(self.items) != 0:
            res["items"] = self.items
        if self.num:
            res["number"] = self.num
        return res

    def add_item(self, items):
        self.items = items

    def __str__(self):
        if self.num:
            res = "{}/{}: \n".format(
                self.title,self.num)
        else:
            res = "{}: \n".format(self.title)
        res += "{}\n".format(self.text)
        if len(self.items) != 0:
            for i in self.items:
                res += " {}\n".format(str(i))
        return res

class Chapter:
    def __init__( self, title):
        self.title = title
        self.articles = []

    def json(self):
        return {
            "title": self.title,
            "articles": self.articles,
        }

    def add_article(self, article):
        self.articles.append(article)

    def __str__(self):
        print("# Chapter\n----")

class Article:
    def __init__( self):
        self.caption = ""
        self.paragraphs = []

    def json(self):
        res = {
            "paragraphs": self.paragraphs
        }
        if self.caption:
            res["caption"] = self.caption,
        return res

    def add_caption(self, caption):
        self.caption = caption

    def add_paragraph(self, paragraph):
        self.paragraphs.append(paragraph)

class ParagraphEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Chapter):
            return obj.json()
        elif isinstance(obj, Article): 
            return obj.json()
        elif isinstance(obj, Paragraph): 
            return obj.json()
        elif isinstance(obj, Item):
            return obj.json()
        else:
            return json.JSONEncoder.default(self, obj)

def fetch_content_from_url(parent):
    r = requests.get(parent)
    r.encoding = r.apparent_encoding
    return BeautifulSoup(r.text, "html.parser")

def get_law_url_from_bs_data(bs_data):
    targets = []    
    for i in bs_data.find_all("a", class_="detail_link"):
        print(i.string)
        targets.append(host + i.get("href"))
    return targets

def parse_paragraph(bs_data, prev_title = ""):
    title = bs_data.find(class_="ArticleTitle")
    number = None
    if not title:
        number = bs_data.find(class_="ParagraphNum")

    paragraph = bs_data.find(class_="ParagraphSentence")
    if title and paragraph and prev_title:
        return None

    if paragraph:
        paragraph = paragraph.text

    res = None
    if number:
        res = Paragraph(title=prev_title, num=number.text, text=paragraph)
    else:
        res = Paragraph(title=title.text, text=paragraph)

    bitems = bs_data.find_all(class_="ItemSentence")
    items = []
    for i in bitems:
        items.append(Item(
            i.find(class_="ItemTitle").string,
            i.text
        ))
    if len(items) != 0:
        res.add_item(items)

    return res

def parse_article(bs_data):
    article = Article()
    caption = bs_data.find(class_="ArticleCaption")
    if caption:
        article.add_caption(caption.text)

    prev = Paragraph()
    for p in bs_data.find_all(class_="Paragraph"):
        paragraph = parse_paragraph(p, prev_title=prev.title)
        if not paragraph:
            continue
        article.add_paragraph(paragraph)
        prev = paragraph

    return article

def parse_chapter(bs_data):
    title = bs_data.find(class_="ChapterTitle").string
    chapter = Chapter(title)
    for a in bs_data.find_all(class_="Article"):
        chapter.add_article(parse_article(a))
    return chapter

def scraping(url):
    Law = {}
    result = {}
    log("start scraping")
    r = requests.get(url)
    r.encoding = r.apparent_encoding
    res = BeautifulSoup(r.text,"html.parser")
    law_name = res.b.text.replace('\n','')
    if "（" in law_name:
        titles = parse("{}（{}）",law_name)
        if titles:
            law_name = titles[0]
            Law["number"] = titles[1]

    from datetime import datetime
    Law["date"] = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    Law["url"] = url
    Law["name"] = law_name
    log("Law Name:"+law_name)

    result = []

    for i in res.find_all("div",class_="MainProvision"):
        for a in i.find_all("div", class_="Chapter"):
            result.append(parse_chapter(a))
                    
    Law["provision"] = result    
    return law_name, Law

def storeJson(url, storeDir, class_dir):
    name, contents = scraping(url, True)
    print(str(contents).replace("'",'"'))
    return
    print("====================")
    print(class_dir +" / "+ name)
    print("=======")

    import os
    if not os.path.isdir(storeDir +"/"+class_dir):
        os.mkdir(storeDir +"/"+ class_dir)
    name = hashlib.md5(name).hexdigest()
    filename = name+".json"
    log("Store "+filename)
    if len(filename) > 250:
        print("ERROR")
        return class_dir+"/"+filename
    import json
    f = open(storeDir + "/"+class_dir+"/" + filename,"w")
    f.write(json.dumps( contents, ensure_ascii=False))
    f.write("")
    f.close()
    return class_dir+"/"+filename


def get_laws_by_hiragana(hiragana):
    target = "{}/search/elawsSearch/elaws_search/lsg0100/search?searchType=3&initialIndex={}&category=1".format(host,hiragana)
    data = fetch_content_from_url(target)
    urls = get_law_url_from_bs_data(data)
    return 

if __name__ == "__main__":
    resultDir = "LawJson"
    url = host + "/search/elawsSearch/elaws_search/lsg0500/detail?lawId=420AC0000000083"
    title, contents = scraping(url)
    print(json.dumps(contents, ensure_ascii=False, cls=ParagraphEncoder)),

    quit()

    for h in [chr(i) for i in range(12353, 12436)]:
        get_laws_by_hiragana(h)

