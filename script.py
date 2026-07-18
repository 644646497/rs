import feedparser
import requests
from bs4 import BeautifulSoup

RSS_URL = "https://rss.dw.com/rdf/rss-chi-all"

feed = feedparser.parse(RSS_URL)

def clean_text(url):
    try:
        r = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0"
        })
        soup = BeautifulSoup(r.text, "lxml")

        # 去掉无用标签
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # DW正文通常在 article 或 main
        article = soup.find("article") or soup.find("main") or soup.body

        text = []
        author = None

        # 尝试提取作者
        a_tag = soup.find("meta", {"name": "author"})
        if a_tag and a_tag.get("content"):
            author = a_tag["content"]

        # 提取段落
        if article:
            for p in article.find_all("p"):
                t = p.get_text(strip=True)
                if t:
                    text.append(t)

        content = "\n".join(text)

        return content[:8000], author

    except Exception as e:
        return "无法抓取全文", None


rss = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
<title>DW Clean Full RSS</title>
<link>https://www.dw.com</link>
<description>Clean full text feed</description>
"""

for entry in feed.entries[:15]:
    title = entry.title
    link = entry.link

    content, author = clean_text(link)

    prefix = "写作其实：DW中文"
    if author:
        prefix += f"\n作者：{author}"

    full_text = prefix + "\n\n" + content

    rss += f"""
<item>
<title>{title}</title>
<link>{link}</link>
<description><![CDATA[{full_text}]]></description>
</item>
"""

rss += "</channel></rss>"

with open("feed.xml", "w", encoding="utf-8") as f:
    f.write(rss)

print("done")
