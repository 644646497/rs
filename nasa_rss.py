#!/usr/bin/env python
# -*- coding: utf-8 -*-
import feedparser
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
import time
import re

# 英译简
try:
    from googletrans import Translator
    translator = Translator()
    CAN_TRANSLATE = True
except ImportError:
    CAN_TRANSLATE = False
    print("警告: googletrans 未安装，将保持英文原文")

RSS_URL = 'https://www.nasa.gov/rss/dyn/breaking_news.rss'
OUTPUT_FILE = 'nasa_feed.xml'

def translate_to_simplified(text):
    """将英文文本翻译成简体中文"""
    if not CAN_TRANSLATE or not text or len(text) < 50:
        return text
    try:
        translated = translator.translate(text, dest='zh-cn')
        return translated.text
    except Exception as e:
        print(f"翻译出错: {e}")
        return text

def fetch_full_content(url):
    """抓取 NASA 文章完整正文"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        article = soup.find('article') or soup.find('div', class_=re.compile(r'entry-content|field-body|article-content'))
        if article:
            paragraphs = article.find_all('p')
            text = '\n\n'.join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40)
            if len(text) > 200:
                return text
        return None
    except Exception as e:
        print(f"抓取正文失败: {e}")
        return None

def fetch_and_convert():
    print(f"抓取 NASA RSS: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)
    print(f"获取到 {len(feed.entries)} 篇文章")
    
    rss_items = []
    for idx, entry in enumerate(feed.entries[:15]):
        print(f"[{idx+1}] 处理: {entry.title[:60]}...")
        
        # 抓取完整正文
        full_text = fetch_full_content(entry.link)
        if full_text:
            raw_text = full_text
            print(f"  ✓ 抓取到完整正文，长度: {len(raw_text)} 字符")
        else:
            raw_text = entry.summary
            print(f"  ⚠ 使用 RSS 摘要，长度: {len(raw_text)} 字符")
        
        # 翻译
        print(f"  🔄 翻译中...")
        translated_title = translate_to_simplified(entry.title)
        translated_text = translate_to_simplified(raw_text)
        print(f"  ✓ 翻译完成，长度: {len(translated_text)} 字符")
        
        pub_date = entry.get('published', datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT'))
        
        rss_items.append({
            'title': translated_title,
            'link': entry.link,
            'description': translated_text,
            'pubDate': pub_date,
            'guid': entry.link,
        })
    
    # 生成 XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n<channel>\n'
    xml += '  <title>NASA 新闻 RSS（简体中文版）</title>\n'
    xml += '  <link>https://www.nasa.gov/</link>\n'
    xml += '  <description>NASA 官方新闻 + 英译简</description>\n'
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
    
    print(f"\n✅ 完成！已生成 {len(rss_items)} 篇简体中文新闻 -> {OUTPUT_FILE}")

def escape_xml(text):
    if not text:
        return ''
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

if __name__ == '__main__':
    fetch_and_convert()
