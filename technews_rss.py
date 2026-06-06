#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from opencc import OpenCC

# 初始化简体转换器 (tw->cn)
cc = OpenCC('t2s')

RSS_URL = 'https://technews.tw/tn-rss/'
OUTPUT_FILE = 'technews_feed.xml'

def clean_content(html_content):
    """清理尾巴、标签，并转为简体"""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. 删除广告 / 赞助 / 相关阅读区块
    for ad in soup.find_all('div', class_=re.compile(r'ad|coffee|donate|related|also-read|tag-cloud')):
        ad.decompose()
    for p in soup.find_all('p', class_=re.compile(r'ad|coffee')):
        p.decompose()

    # 2. 删除包含特定关键词的文本块（尾巴）
    keywords_to_remove = ['喝咖啡', '贊助', '延伸閱讀', '相關文章', '首圖來源', '圖片來源']
    for kw in keywords_to_remove:
        for elem in soup.find_all(string=re.compile(kw)):
            if elem.parent:
                elem.parent.decompose()

    # 3. 删除 #标签 形式的链接（如 <a>#科技</a>）
    for tag_link in soup.find_all('a', href=re.compile(r'^https?://technews.tw/.*tag/')):
        tag_link.decompose()
    for span in soup.find_all('span', class_=re.compile(r'tag|label')):
        span.decompose()

    # 4. 清理多余空白行
    text = str(soup)
    text = re.sub(r'\n\s*\n', '\n', text)

    # 5. 繁体转简体
    text = cc.convert(text)
    return text

def fetch_and_convert():
    print(f"抓取 RSS 索引: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)

    rss_items = []
    for entry in feed.entries[:15]:
        article_url = entry.link
        print(f"处理: {entry.title}")

        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(article_url, headers=headers, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            content_div = soup.find('div', class_='entry-content')
            raw_content = str(content_div) if content_div else entry.summary

            cleaned_content = clean_content(raw_content)

            if len(cleaned_content.strip()) < 50:
                cleaned_content = entry.summary

            pub_date = entry.get('published', '')
            if not pub_date:
                pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')

        except Exception as e:
            print(f"  ❌ 出错，用摘要备用: {e}")
            cleaned_content = clean_content(entry.summary)
            pub_date = entry.get('published', datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT'))

        rss_items.append({
            'title': cc.convert(entry.title),
            'link': article_url,
            'description': cleaned_content,
            'pubDate': pub_date,
            'guid': article_url,
        })

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n<channel>\n'
    xml += '  <title>科技新报全文 RSS（简体/去尾巴）</title>\n'
    xml += '  <link>https://technews.tw/</link>\n'
    xml += '  <description>精简正文、繁转简、移除赞助/标签/相关阅读</description>\n'
    xml += f'  <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")}</lastBuildDate>\n'

    for item in rss_items:
        xml += '  <item>\n'
        xml += f'    <title>{escape_xml(item["title"])}</title>\n'
        xml += f'    <link>{item["link"]}</link>\n'
        xml += f'    <guid>{item["guid"]}</guid>\n'
        xml += f'    <pubDate>{item["pubDate"]}</pubDate>\n'
        xml += f'    <description><![CDATA[{item["description"]}]]></description>\n'
        xml += '  </item>\n'

    xml += '</channel>\n</rss>'

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(xml)

    print(f"✅ 完成！已生成 {len(rss_items)} 篇简中全文 -> {OUTPUT_FILE}")

def escape_xml(text):
    if not text:
        return ''
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

if __name__ == '__main__':
    fetch_and_convert()
