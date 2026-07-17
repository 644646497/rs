#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from opencc import OpenCC
import time

cc = OpenCC('t2s')

# 纽约时报中文网官方 RSS（作为文章列表来源）
INDEX_URL = 'https://cn.nytimes.com/rss/'
OUTPUT_FILE = 'nytimes_feed.xml'

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

def extract_article_and_date(html):
    """提取正文和发布日期，返回 (text, date_str)"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. 提取发布时间
    pub_date = None
    time_tag = soup.find('time')
    if time_tag:
        pub_date = time_tag.get('datetime') or time_tag.get_text(strip=True)
    if not pub_date:
        meta_tag = soup.find('meta', {'name': re.compile(r'date|pubdate|publish', re.I)})
        if meta_tag:
            pub_date = meta_tag.get('content')
    if not pub_date:
        for p in soup.find_all(['div', 'span', 'p'], class_=re.compile(r'date|time|publish', re.I)):
            text = p.get_text(strip=True)
            if re.search(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}', text):
                pub_date = text
                break
    
    # 2. 清理正文
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
        tag.decompose()
    
    # 纽约时报中文网的正文容器
    article = soup.find('article', class_='article-content') or soup.find('article') or soup.find('div', class_='article-body')
    if not article:
        article = soup.body
    
    paragraphs = article.find_all('p')
    if not paragraphs:
        text = soup.get_text(strip=True)
    else:
        valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
        text = '\n\n'.join(valid_paragraphs)
        text = re.sub(r'\n\s*\n', '\n\n', text)
    
    # 3. 格式化日期
    if pub_date:
        try:
            match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', pub_date)
            if match:
                year, month, day = match.groups()
                time_match = re.search(r'(\d{1,2}):(\d{1,2}):?(\d{0,2})', pub_date)
                if time_match:
                    hour, minute, second = time_match.groups()
                    second = second if second else '00'
                    dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
                else:
                    dt = datetime(int(year), int(month), int(day))
                pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S +0800')
            else:
                pass
        except:
            pass
    else:
        pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')
    
    return text, pub_date

def fetch_and_convert():
    print(f"抓取纽约时报中文网: {INDEX_URL}")
    resp = fetch_with_retry(INDEX_URL)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # 从 RSS 中提取文章链接
    links = []
    for item in soup.find_all('item'):
        link_tag = item.find('link')
        if link_tag:
            url = link_tag.get_text(strip=True)
            title_tag = item.find('title')
            title = title_tag.get_text(strip=True) if title_tag else ''
            if title and len(title) > 5:
                links.append({'url': url, 'title': title})
    
    # 去重，取前15篇
    seen = set()
    unique_links = []
    for link in links:
        if link['url'] not in seen:
            seen.add(link['url'])
            unique_links.append(link)
    unique_links = unique_links[:15]
    
    print(f"找到 {len(unique_links)} 篇文章")
    
    rss_items = []
    for idx, link in enumerate(unique_links):
        print(f"[{idx+1}] 处理: {link['title'][:50]}...")
        try:
            article_resp = fetch_with_retry(link['url'])
            raw_text, pub_date = extract_article_and_date(article_resp.text)
            cleaned = cc.convert(raw_text)
            if len(cleaned) < 100:
                print(f"  ⚠ 正文过短({len(cleaned)}字)")
            else:
                print(f"  ✓ 正文长度: {len(cleaned)} 字符")
            print(f"  📅 发布日期: {pub_date}")
        except Exception as e:
            print(f"  ❌ 出错: {e}")
            cleaned = ""
            pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        rss_items.append({
            'title': cc.convert(link['title']),
            'link': link['url'],
            'description': cleaned,
            'pubDate': pub_date,
            'guid': link['url'],
        })
    
    # 生成 XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n<channel>\n'
    xml += '  <titl