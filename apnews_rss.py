#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import time

try:
    from googletrans import Translator
    translator = Translator()
    CAN_TRANSLATE = True
except ImportError:
    CAN_TRANSLATE = False
    print("警告: googletrans 未安装，将保持英文原文")

# AP News 首页
INDEX_URL = 'https://apnews.com'
OUTPUT_FILE = 'apnews_feed.xml'

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

def translate_to_simplified(text):
    if not CAN_TRANSLATE or not text or len(text) < 50:
        return text
    try:
        translated = translator.translate(text, dest='zh-cn')
        return translated.text
    except Exception as e:
        print(f"翻译出错: {e}")
        return text

def extract_article(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
        tag.decompose()
    
    article = (soup.find('article') or 
               soup.find('div', class_=re.compile(r'Article|RichTextStoryBody|RichTextArticleBody')) or
               soup.find('main'))
    
    if not article:
        article = soup.body
    
    paragraphs = article.find_all('p')
    if not paragraphs:
        return soup.get_text(strip=True)
    
    valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40]
    text = '\n\n'.join(valid_paragraphs)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text

def fetch_and_convert():
    print(f"抓取 AP News 首页: {INDEX_URL}")
    resp = fetch_with_retry(INDEX_URL)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # 提取所有新闻链接
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        # AP News 的文章链接格式
        if href.startswith('/article/') or '/article/' in href:
            if not href.startswith('http'):
                url = 'https://apnews.com' + href
            else:
                url = href
            title = a.get_text(strip=True)
            if title and len(title) > 20 and url not in [l['url'] for l in links]:
                links.append({'url': url, 'title': title})
            if len(links) >= 20:
                break
    
    # 去重
    seen = set()
    unique_links = []
    for link in links:
        if link['url'] not in seen:
            seen.add(link['url'])
            unique_links.append(link)
    unique_links = unique_links[:15]
    
    print(f"找到 {len(unique_links)} 篇新闻")
    
    rss_items = []
    for idx, link in enumerate(unique_links):
        print(f"[{idx+1}] 处理: {link['title'][:60]}...")
        
        try:
            article_resp = fetch_with_retry(link['url'])
            raw_text = extract_article(article_resp.text)
            
            if len(raw_text) < 200:
                print(f"  ⚠ 正文过短({len(raw_text)}字)")
            else:
                print(f"  ✓ 正文长度: {len(raw_text)} 字符")
            
            # 翻译
            if CAN_TRANSLATE:
                print(f"  🔄 翻译中...")
                translated_title = translate_to_simplified(link['title'])
                translated_text = translate_to_simplified(raw_text)
                print(f"  ✓ 翻译完成")
            else:
                translated_title = link['title']
                translated_text = raw_text
            
            pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        except Exception as e:
            print(f"  ❌ 出错: {e}")
            translated_title = link['title']
            translated_text = ""
            pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        rss_items.append({
            'title': translated_title,
            'link': link['url'],
            'description': translated_text,
            'pubDate': pub_date,
            'guid': link['url'],
        })
    
    # 生成 XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n<channel>\n'
    xml += '  <title>AP News 全文 RSS（简体中文版）</title>\n'
    xml += '  <link>https://apnews.com/</link>\n'
    xml += '  <description>AP News 首页抓取 + 英译简</description>\n'
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
