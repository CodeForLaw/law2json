
import sys

import requests
from parse import *
from bs4 import BeautifulSoup

import subprocess

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
	def __init__( self, text):
		self.text = text
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
			Law["法令番号"] = titles[1]

	Law["名前"] = law_name
	log("Law Name:"+law_name, log_display)
	parent = ""
	for i in res.find_all("div",class_="item"):
		name = i.b

		content = i.text.strip()

		if name.a and parent != "":
			result[parent].append_sub(name.a.string, Provision(content))
		else:
			if name.string and name.string.isdigit():
				name.string = "附則 " + name.string
			result[name.string] = Provision(content)
			parent = name.string
	log("converted json")
	import json
	result = dict([(k, json.loads(v.json())) for k,v in result.items()])    
	Law["本文"] = result
	return law_name, Law

def storeJson(url, storeDir):
	name, contents = scraping(url, True)
	print("====================")
	print(name)
	print("=======")
	filename = name+".json"
	log("Store "+filename)
	import json
	f = open(storeDir + "/" + filename,"w")
	f.write(json.dumps( contents, ensure_ascii=False, default=support_provision_default))
	f.close()
	return filename

def gitInit(remoteRepository, storeDir):
	subprocess.call(["git","init"],cwd= storeDir)
	subprocess.call(["git","remote","add","origin",remoteRepository], cwd= storeDir)

def commit(filename):
	subprocess.call(["git","add",filename], cwd=storeDir)
	subprocess.call(["git","commit","-m","\"[Add]"+filename+"\""], cwd=storeDir)

if __name__ == "__main__":
	remoteRepository="https://github.com/CodeForLaw/LawJson.git"
	storeDir = "LawJson"

# アルコール事業法
	for i in range(2,4):
		for j in range(4,9):
			if i != 0:
				number = str(i) + str(j)
			else:
				number = str(j)
			target_url = "http://law.e-gov.go.jp/cgi-bin/idxsearch.cgi?H_CTG_"+number+"=%81%40&H_CTG_GUN=1&H_NAME=0&H_NAME_YOMI=%82%A0&H_NO_GENGO=H&H_NO_YEAR=0&H_NO_TYPE=2&H_NO_NO=0&H_RYAKU=1&H_YOMI_GUN=1"
			log("==== target_url ["+target_url+"]====")
			targets = fetchUrls(target_url)
			for target in targets:
				url = diveUrls(target)
				url = url.replace("_IDX","")
				log("==== law url ["+url+"]====")
				filename = storeJson(url, storeDir)
				log("commit "+filename)
				commit(filename)
	
	print("complate!!!")	


