import requests
import feedparser
import trafilatura
from datetime import datetime
import time
import re

RSS_URL = "https://feedx.net/rss/nikkei.xml"
OUTPUT_FILE = "feed.xml"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def fetch_fulltext(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            result = trafilatura.extract(resp.text, include_formatting=True)
            if result:
                return result
    except Exception as e:
        print(f"  全文提取失败: {e}")
    return None

def main():
    print("开始抓取日经中文网...")
    
    try:
        resp = requests.get(RSS_URL, headers=HEADERS, timeout=30)
        print(f"HTTP状态码: {resp.status_code}")
        feed = feedparser.parse(resp.content)
        print(f"找到 {len(feed.entries)} 篇文章")
    except Exception as e:
        print(f"抓取RSS失败: {e}")
        return
    
    rss_items = []
    
    for i, entry in enumerate(feed.entries[:10]):
        title = entry.get('title', '无标题')
        link = entry.get('link')
        if not link:
            continue
        
        print(f"[{i+1}] 抓取: {title[:50]}...")
        
        content = fetch_fulltext(link)
        if not content:
            content = entry.get('summary', entry.get('description', ''))
        
        pubdate = entry.get('published_parsed')
        if pubdate:
            pubdate = datetime(*pubdate[:6])
        else:
            pubdate = datetime.now()
        
        rss_items.append({
            'title': title,
            'link': link,
            'description': content,
            'pubdate': pubdate
        })
        
        time.sleep(1)
    
    rss_output = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>日经中文网 - 全文版</title>
<link>https://cn.nikkei.com</link>
<description>自动抓取的日经中文全文</description>
<lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>
'''
    
    for item in rss_items:
        rss_output += f'''
<item>
    <title><![CDATA[{item['title']}]]></title>
    <link>{item['link']}</link>
    <pubDate>{item['pubdate'].strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate>
    <description><![CDATA[
        <h2>{item['title']}</h2>
        <hr/>
        {item['description']}
        <hr/>
        <p><a href="{item['link']}">📖 阅读原文</a></p>
    ]]></description>
</item>'''
    
    rss_output += '\n</channel>\n</rss>'
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(rss_output)
    
    print(f"\n✅ 完成！共 {len(rss_items)} 篇文章")

if __name__ == "__main__":
    main()
