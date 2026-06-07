#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from opencc import OpenCC
import time

cc = OpenCC('t2s')

INDEX_URL = 'https://udn.com/news/breaknews/1/1'
OUTPUT_FILE = 'udn_feed.xml'

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
    # 尝试找 time 标签
    time_tag = soup.find('time')
    if time_tag:
        pub_date = time_tag.get('datetime') or time_tag.get_text(strip=True)
    if not pub_date:
        # 尝试找 meta 标签
        meta_tag = soup.find('meta', {'name': re.compile(r'date|pubdate|publish', re.I)})
        if meta_tag:
            pub_date = meta_tag.get('content')
    if not pub_date:
        # 尝试找包含"年"、"月"、"日"的段落（联合报常见格式）
        for p in soup.find_all(['div', 'span', 'p'], class_=re.compile(r'date|time|publish', re.I)):
            text = p.get_text(strip=True)
            if re.search(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}', text):
                pub_date = text
                break
    
    # 2. 清理正文
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
        tag.decompose()
    
    article = soup.find('article') or soup.find('div', class_=re.compile(r'article-content|story-article|entry-content'))
    if not article:
        article = soup.body
    
    paragraphs = article.find_all('p')
    if not paragraphs:
        text = soup.get_text(strip=True)
    else:
        valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
        text = '\n\n'.join(valid_paragraphs)
        text = re.sub(r'\n\s*\n', '\n\n', text)
    
    # 3. 格式化日期（如果抓到了）
    if pub_date:
        # 尝试解析各种日期格式
        try:
            # 格式: 2026-06-07T12:34:56+0800 或 2026-06-07 12:34:56
            match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', pub_date)
            if match:
                year, month, day = match.groups()
                # 尝试提取时间
                time_match = re.search(r'(\d{1,2}):(\d{1,2}):?(\d{0,2})', pub_date)
                if time_match:
                    hour, minute, second = time_match.groups()
                    second = second if second else '00'
                    dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
                else:
                    dt = datetime(int(year), int(month), int(day))
                pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S +0800')
            else:
                # 无法解析，保持原样
                pass
        except:
            pass
    else:
        pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')
    
    return text, pub_date

def fetch_and_convert():
    print(f"抓取联合报: {INDEX_URL}")
    resp = fetch_with_retry(INDEX_URL)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    links = []
    for a in soup.find_all('a', href=re.compile(r'/news/story/\d+/\d+')):
        url = a['href']
        if not url.startswith('http'):
            url = 'https://udn.com' + url
        title = a.get_text(strip=True)
        if title and len(title) > 5 and url not in [l['url'] for l in links]:
            links.append({'url': url, 'title': title})
        if len(links) >= 20:
            break
    
    seen = set()
    unique_links = []
    for link in links:
        if link['url'] not in seen:
            seen.add(link['url'])
            unique_links.append(link)
    unique_links = unique_links[:15]
    
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
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n<channel>\n'
    xml += '  <title>联合报新闻 RSS（简体/全文）</title>\n'
    xml += '  <link>https://udn.com/</link>\n'
    xml += '  <description>联合报新闻全文抓取、繁转简</description>\n'
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
