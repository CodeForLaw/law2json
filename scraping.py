
import sys

import requests
from parse import *
from bs4 import BeautifulSoup
import hashlib
import subprocess

import re

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



def log(msg, display = True):
	from datetime import datetime
	now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
	if display:
		print("["+now+"] "+msg)

def support_provision_default(o):
    if isinstance(o, Provision):
        return o.json()
    raise TypeError(repr(o) + " is not JSON serializable")

class Provision:
	def __init__( self, text, name = None,ptype = None):
		self.text = text
		self.name = name
		self.ptype = ptype
		self.sub = {}
	def append_sub( self, name, sub_prov):
		self.sub[name] = sub_prov

	def text(self):
		return self.text

	def __str__(self):
		res = self.text
		if len(self.sub) != 0:
			res += self.sub
		return res

	def json(self):
		import json
		result = {}
		if self.name:
			result["name"] = self.name
		if self.ptype:
			result["type"] = self.ptype
		result["text"] = self.text
		if len(self.sub) != 0:
			for key, val in self.sub.items():
				result[key] = json.loads(val.json())
		return json.dumps(result, ensure_ascii=False)


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

def parse_article(bs_data):
    title = bs_data.find(class_="ArticleTitle")
    caption = bs_data.find(class_="ArticleCaption")
    paragraph = bs_data.find(class_="ParagraphSentence")
    if not (title and caption and paragraph):
        return
    print(title.string)
    print(caption.string)
    print(paragraph.text) 
    print('---')

def parse_chapter(bs_data):
    title = bs_data.find(class_="ChapterTitle").string
    for a in bs_data.find_all(class_="Article"):
        parse_article(a)

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
    parent = ""
    for i in res.find_all("div",class_="MainProvision"):
        for a in i.find_all("div", class_="Chapter"):
            parse_chapter(a)
        continue

        name = i.b
        tmp = i.text.strip().split("\n\n\n\u3000")
        if len(tmp) >= 2:
            content = "".join(tmp[1:])
        else:
            content = tmp[0]

        if name.a and parent != "":
            result[parent].append_sub(name.a.string, Provision(content))
        else:
            if name.string and name.string.isdigit():
                name.string = "" + name.string
                result[name.string] = Provision(content, "附則")
            elif name.string:
                print(name.string)
                tmps = parse("第{}条",name.string)				
                if tmps:
                    print(tmps)
                    result[kansuji2arabic(tmp[0])] = Provision(content, name.string, "条文")
                    parent = kansuji2arabic(tmp[0])
                else:
                    result[name.string] = Provision(content, name.string, "条文")				
                    parent = name.string

    log("converted json")
    import json
    result = dict([(k, json.loads(v.json())) for k,v in result.items()])    
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
	f.write(json.dumps( contents, ensure_ascii=False, default=support_provision_default))
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
    print(scraping(url))

    quit()

    for h in [chr(i) for i in range(12353, 12436)]:
        get_laws_by_hiragana(h)

