import requests
import feedparser
import trafilatura
from datetime import datetime
import time
import html
import re

# 建议直接访问日经中文网官方RSS，比第三方中转更稳定
RSS_URL = "https://www.nikkei.com/rss" 
OUTPUT_FILE = "feed.xml"

# 更加完整的浏览器请求头，防止被WAF/CDN拦截
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://www.nikkei.com/'
}

def fetch_fulltext(url):
    try:
        # 增加超时和重试逻辑
        downloaded = trafilatura.fetch_url(url, user_agent=HEADERS['User-Agent'], timeout=15)
        if downloaded:
            result = trafilatura.extract(downloaded, include_formatting=True, no_fallback=False)
            if result:
                return result
    except Exception as e:
        print(f"  全文提取失败: {e}")
    return None

def clean_xml_text(text):
    """清理XML中不允许的特殊控制字符，防止解析报错"""
    if not text:
        return ""
    # 移除 XML 非法的控制字符
    illegal_chars = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')
    text = illegal_chars.sub('', text)
    return text

def main():
    print("开始抓取日经中文网...")
    
    rss_items = []
    
    # 增加重试机制，应对网络波动或短暂拦截
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.get(RSS_URL, headers=HEADERS, timeout=30)
            print(f"HTTP状态码: {resp.status_code}")
            
            if resp.status_code != 200:
                print(f"请求失败，状态码: {resp.status_code}")
                if attempt < max_retries - 1:
                    print(f"等待 3 秒后重试...")
                    time.sleep(3)
                    continue
                return
                
            feed = feedparser.parse(resp.content)
            print(f"找到 {len(feed.entries)} 篇文章")
            break # 成功则跳出循环
        except Exception as e:
            print(f"抓取RSS失败: {e}")
            if attempt < max_retries - 1:
                time.sleep(3)
            else:
                return

    for i, entry in enumerate(feed.entries[:10]):
        title = clean_xml_text(entry.get('title', '无标题'))
        link = entry.get('link')
        if not link:
            continue
        
        print(f"[{i+1}] 正在抓取: {title[:40]}...")
        
        content = fetch_fulltext(link)
        if not content:
            # 如果全文提取失败，退回使用摘要，并做HTML转义防止破坏XML结构
            summary = entry.get('summary', entry.get('description', ''))
            content = html.escape(summary) if summary else "暂无内容"
        
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
        
        # 礼貌性延时，避免触发目标网站的频率限制(429错误)
        time.sleep(1.5)
    
    # 生成 RSS XML
    rss_output = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>日经中文网 - 全文版</title>
<link>https://cn.nikkei.com</link>
<description>自动抓取的日经中文全文</description>
<lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>
'''
    
    for item in rss_items:
        # 对 description 做进一步保护，如果是纯文本则包裹在 CDATA 中
        desc_content = item['description']
        rss_output += f'''
<item>
    <title><![CDATA[{item['title']}]]></title>
    <link>{item['link']}</link>
    <pubDate>{item['pubdate'].strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate>
    <description><![CDATA[
        <h2>{item['title']}</h2>
        <hr/>
        {desc_content}
        <hr/>
        <p><a href="{item['link']}">📖 阅读原文</a></p>
    ]]></description>
</item>'''
    
    rss_output += '\n</channel>\n</rss>'
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(rss_output)
    
    print(f"\n✅ 完成！共成功处理 {len(rss_items)} 篇文章，已保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
