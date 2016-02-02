

import requests
from parse import *
from bs4 import BeautifulSoup

def log(msg, display = True):
	from datetime import datetime
	now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
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



def scraping(url, log_display = True):
	log("start scraping")
	r = requests.get(url)
	log("fetched data from "+url, log_display)
	r.encoding = r.apparent_encoding
	log("changed encoding", log_display)
	res = BeautifulSoup(r.text,"html.parser")
	law_name = res.b.text.replace('\n','')
	log("Law Name:"+law_name, log_display)
	result = {}
	parent = ""
	for i in res.find_all("div",class_="item"):
		name = i.b

		content = i.text.strip()
#		if "\n\n" in i.text:
#			content =  "".join(map(str, i.text.split("\n\n")[1:-1]))

		if name.a and parent != "":
			result[parent].append_sub(name.a.string, Provision(content))
		else:
			result[name.string] = Provision(content)
			parent = name.string

	import json
	result = dict([(k, json.loads(v.json())) for k,v in result.items()])    
	return law_name, result



name, contents = scraping("http://law.e-gov.go.jp/htmldata/H10/H10HO025.html", False)

print("====================")
print(name)
print("=======")
import json
"""
for key, val in contents.items():
	print(key)
	print(val)
"""
print(json.dumps( contents, ensure_ascii=False, default=support_provision_default))
"""
name, contents = scraping("http://law.e-gov.go.jp/htmldata/S35/S35HO105.html")
print("====================")
print(name)
print("=======")
print(contents["第一条"])
"""