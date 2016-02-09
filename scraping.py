
import sys

import requests
from parse import *
from bs4 import BeautifulSoup
import hashlib
import subprocess

import re

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


def fetchUrls(parent, log_display = True):
	log("start fetch urls")
	r = requests.get(parent)
	log("fetched urls from "+parent, log_display)
	r.encoding = r.apparent_encoding
	log("changed encoding", log_display)
	res = BeautifulSoup(r.text, "html.parser")
	targets = []	
	for i in res.find_all("a"):
		targets.append("http://law.e-gov.go.jp" + i.get("href"))
	return targets

def diveUrls(url, log_display = True):
	log("start dive urls")
	r = requests.get(url)
	log("fetched urls from "+url, log_display)
	r.encoding = r.apparent_encoding
	log("changed encoding", log_display)
	res = BeautifulSoup(r.text, "html.parser")
	url = res.frameset.frameset.frame.get("src")
	return "http://law.e-gov.go.jp" + url
	
def scraping(url, log_display = True):
	Law = {}
	result = {}
	log("start scraping")
	r = requests.get(url)
	log("fetched data from "+url, log_display)
	r.encoding = r.apparent_encoding
	log("changed encoding", log_display)
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
	log("Law Name:"+law_name, log_display)
	parent = ""
	for i in res.find_all("div",class_="item"):
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

def gitInit(remoteRepository, storeDir):
	subprocess.call(["git","init"],cwd= storeDir)
	subprocess.call(["git","remote","add","origin",remoteRepository], cwd= storeDir)

def commit(filename):
	subprocess.call(["git","add",filename], cwd=storeDir)
	subprocess.call(["git","commit","-m","\"[Add] "+filename+"\""], cwd=storeDir)

def Class_names( log_display = True):
	log("start dive urls")
	r = requests.get("http://law.e-gov.go.jp/cgi-bin/idxsearch.cgi")
	r.encoding = r.apparent_encoding
	log("changed encoding", log_display)
	res = BeautifulSoup(r.text, "html.parser")
	result = []
	for i in res.find_all("input",attrs={"type": "submit", "value": "　"}):
		result.append(i.string.replace("　","").strip())
	return result

if __name__ == "__main__":
	class_names = Class_names()
	storeDir = "LawJson"
	for i in range(1,10):
		for j in range(0,5):
			if j != 0:
				number = str(j) + str(i)
			else:
				number = str(i)
			print(number)
			target_url = "http://law.e-gov.go.jp/cgi-bin/idxsearch.cgi?H_CTG_"+number+"=%81%40&H_CTG_GUN=1&H_NAME=0&H_NAME_YOMI=%82%A0&H_NO_GENGO=H&H_NO_YEAR=0&H_NO_TYPE=2&H_NO_NO=0&H_RYAKU=1&H_YOMI_GUN=1"
			log("==== target_url ["+target_url+"]====")
			targets = fetchUrls(target_url)
			cnt = 0
			for target in targets:
				url = diveUrls(target)
				url = url.replace("_IDX","")
				log("==== law url ["+url+"]====")
				filename = storeJson(url, storeDir, "Machine")
				#print(str(cnt) + "/" + str(len(targets)))
				cnt = cnt + 1
			print("complate!!!")

