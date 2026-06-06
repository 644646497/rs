#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from opencc import OpenCC

cc = OpenCC('t2s')

RSS_URL = 'https://technews.tw/tn-rss/'
OUTPUT_FILE = 'technews_feed.xml'

def clean_content(html_content):
    """清理尾巴、标签，并转为简体"""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')

    # 删除广告/赞助/相关阅读区块
    for ad in soup.find_all('div', class_=re.compile(r'ad|coffee|donate|related|also-read|tag-cloud|entry-crumbs|entry-footer')):
        ad.decompose()
    for p in soup.find_all('p', class_=re.compile(r'ad|coffee')):
        p.decompose()

    # 删除关键词段落
    keywords_to_remove = ['喝咖啡', '贊助', '延伸閱讀', '相關文章', '首圖來源', '圖片來源', '（首圖來源', '（圖片來源']
    for kw in keywords_to_remove:
        for elem in soup.find_all(string=re.compile(kw)):
            if elem.parent:
                elem.parent.decompose()

    # 删除 #标签
    for tag_link in soup.find_all('a', href=re.compile(r'tag/')):
        tag_link.decompose()
    for span in soup.find_all('span', class_=re.compile(r'tag|label')):
        span.decompose()

    # 获取纯文本（保留段落结构）
    paragraphs = soup.find_all('p')
    if paragraphs:
        text = '\n\n'.join(p.get_text(strip=True) for p in paragraphs)
    else:
        text = soup.get_text(strip=True)

    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = cc.convert(text)
    return text

def fetch_and_convert():
    print(f"抓取 RSS 索引: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)

    rss_items = []
    for idx, entry in enumerate(feed.entries[:15]):
        article_url = entry.link
        print(f"[{idx+1}] 处理: {entry.title[:50]}...")

        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(article_url, headers=headers, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 尝试多个可能的正文容器
            content_div = (
                soup.find('div', class_='entry-content') or
                soup.find('div', class_='post-content') or
                soup.find('div', class_='article-content') or
                soup.find('article')
            )
            
            if content_div:
                raw_content = str(content_div)
                cleaned = clean_content(raw_content)
                print(f"  ✓ 抓取成功，正文长度: {len(cleaned)} 字符")
            else:
                cleaned = cc.convert(entry.summary)
                print(f"  ⚠ 未找到正文，使用摘要")

            pub_date = entry.get('published', '')
            if not pub_date:
                pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')

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

    print(f"\n✅ 完成！已生成 {len(rss_items)} 篇简中全文 -> {OUTPUT_FILE}")

def escape_xml(text):
    if not text:
        return ''
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

if __name__ == '__main__':
    fetch_and_convert()
