#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from opencc import OpenCC
import time

cc = OpenCC('t2s')

# RSSHub 早报国际版路由
RSSHUB_URL = 'https://rsshub.app/zaobao/realtime/world'
OUTPUT_FILE = 'zaobao_feed.xml'

def fetch_with_retry(url, max_retries=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
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

def extract_article(html):
    """提取早报文章正文"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 移除干扰元素
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'div.ad']):
        tag.decompose()
    
    # 早报的正文容器
    article = (soup.find('article') or 
               soup.find('div', class_=re.compile(r'article-content|story-content|content-detail')) or
               soup.find('div', {'itemprop': 'articleBody'}))
    
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
    print(f"抓取 RSSHub 早报源: {RSSHUB_URL}")
    
    # 1. 从 RSSHub 获取文章列表
    resp = fetch_with_retry(RSSHUB_URL)
    soup = BeautifulSoup(resp.text, 'xml')  # RSSHub 返回的是 XML
    
    # 解析 RSS 条目
    items = soup.find_all('item')
    print(f"获取到 {len(items)} 篇文章")
    
    rss_items = []
    for idx, item in enumerate(items[:15]):
        title = item.find('title').get_text(strip=True) if item.find('title') else ''
        link = item.find('link').get_text(strip=True) if item.find('link') else ''
        pub_date = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ''
        
        print(f"[{idx+1}] 处理: {title[:50]}...")
        
        try:
            # 2. 抓取原文完整正文
            article_resp = fetch_with_retry(link)
            raw_text = extract_article(article_resp.text)
            cleaned = cc.convert(raw_text)
            
            if len(cleaned) < 100:
                # 正文太短，使用 RSS 摘要
                description = item.find('description')
                summary = description.get_text(strip=True) if description else ''
                cleaned = cc.convert(summary) if summary else cleaned
                print(f"  ⚠ 正文过短({len(cleaned)}字)，使用摘要")
            else:
                print(f"  ✓ 正文长度: {len(cleaned)} 字符")
            
            # 日期处理
            if not pub_date:
                pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
            
        except Exception as e:
            print(f"  ❌ 出错: {e}")
            cleaned = ""
            if not pub_date:
                pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        rss_items.append({
            'title': cc.convert(title),
            'link': link,
            'description': cleaned,
            'pubDate': pub_date,
            'guid': link,
        })
    
    # 3. 生成新的全文 RSS
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n<channel>\n'
    xml += '  <title>联合早报新闻 RSS（简体/全文）</title>\n'
    xml += '  <link>https://www.zaobao.com/</link>\n'
    xml += '  <description>联合早报国际新闻全文抓取、繁转简</description>\n'
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
