#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from opencc import OpenCC
import time

cc = OpenCC('t2s')

# 改用 /feed 地址
RSS_URL = 'https://technews.tw/feed'
OUTPUT_FILE = 'technews_feed.xml'

def fetch_with_retry(url, max_retries=3):
    """带重试的请求"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://technews.tw/',
    }
    for i in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp
        except Exception as e:
            if i == max_retries - 1:
                raise
            time.sleep(2)

def extract_full_text(html):
    """提取正文"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 移除干扰元素
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'iframe']):
        tag.decompose()
    
    # 尝试多个正文选择器
    article = None
    for selector in ['article', '.entry-content', '.post-content', '.article-content', '.content', '#main', '.single-content']:
        article = soup.select_one(selector)
        if article:
            break
    
    if not article:
        article = soup.body
    
    # 提取段落
    paragraphs = article.find_all('p')
    if not paragraphs:
        return soup.get_text(strip=True)
    
    # 过滤太短的段落（可能是导航或广告）
    valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
    
    text = '\n\n'.join(valid_paragraphs)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text

def fetch_and_convert():
    print(f"抓取 RSS: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)
    print(f"获取到 {len(feed.entries)} 篇文章")
    
    rss_items = []
    for idx, entry in enumerate(feed.entries[:15]):
        article_url = entry.link
        print(f"[{idx+1}] 处理: {entry.title[:50]}...")
        
        try:
            resp = fetch_with_retry(article_url)
            raw_text = extract_full_text(resp.text)
            cleaned = cc.convert(raw_text)
            
            if len(cleaned) < 100:
                print(f"  ⚠ 正文过短({len(cleaned)}字)，使用摘要")
                cleaned = cc.convert(entry.summary)
            else:
                print(f"  ✓ 正文长度: {len(cleaned)} 字符")
            
            pub_date = entry.get('published', datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT'))
        except Exception as e:
            print(f"  ❌ 出错: {e}")
            cleaned = cc.convert(entry.summary)
            pub_date = entry.get('published', datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT'))
        
        rss_items.append({
            'title': cc.convert(entry.title),
            'link': article_url,
            'description': cleaned,
            'pubDate': pub_date,
            'guid': article_url,
        })
    
    # 生成 XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n<channel>\n'
    xml += '  <title>科技新报全文 RSS（简体）</title>\n'
    xml += '  <link>https://technews.tw/</link>\n'
    xml += '  <description>全文抓取、繁转简、去广告</description>\n'
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
    
    print(f"\n✅ 完成！已生成 {len(rss_items)} 篇 -> {OUTPUT_FILE}")

def escape_xml(text):
    if not text:
        return ''
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

if __name__ == '__main__':
    fetch_and_convert()
