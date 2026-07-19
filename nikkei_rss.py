#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from opencc import OpenCC
import time
import feedparser

cc = OpenCC('t2s')

# RSSHub 日经中文网路由
INDEX_URL = 'https://rsshub.app/nikkei/cn/latest'
OUTPUT_FILE = 'nikkei_feed.xml'

def fetch_with_retry(url, max_retries=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    for i in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            return resp
        except Exception as e:
            print(f"  请求失败 (尝试 {i+1}/{max_retries}): {e}")
            if i == max_retries - 1:
                raise
            time.sleep(3)

def extract_article_content(html_url):
    """抓取文章全文（备用方案：直接从RSS描述中提取）"""
    try:
        # 尝试获取文章页面，提取正文
        resp = fetch_with_retry(html_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 删除无关标签
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'form']):
            tag.decompose()
        
        # 尝试多种选择器
        selectors = [
            'article',
            '.article-body',
            '.article-content',
            '.content-body',
            '.entry-content',
            '.post-content',
            '.main-text',
            '#article-body',
            '#content',
        ]
        
        content = None
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                break
        
        if content:
            paragraphs = content.find_all('p')
            if paragraphs:
                text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
            else:
                text = content.get_text(strip=True)
        else:
            # 备用：获取所有文本
            text = soup.get_text(separator='\n', strip=True)
            # 过滤短行
            lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 30]
            text = '\n\n'.join(lines[:20])
        
        # 清理
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r'【[^】]{0,30}】', '', text)
        text = re.sub(r'[◆◇●○■□▲△★☆]', '', text)
        text = text.strip()
        
        return text
    except Exception as e:
        print(f"  提取全文失败: {e}")
        return ""

def fetch_and_convert():
    print(f"通过 RSSHub 获取日经中文网: {INDEX_URL}")
    
    try:
        resp = fetch_with_retry(INDEX_URL)
    except Exception as e:
        print(f"❌ 无法获取 RSS: {e}")
        print("可能原因: 1) RSSHub 服务不可用 2) 网络限制")
        print("尝试备用 RSSHub 实例...")
        
        # 尝试备用 RSSHub 实例
        backup_urls = [
            'https://rsshub.uneasy.win/nikkei/cn/latest',
            'https://rsshub.feeded.xyz/nikkei/cn/latest',
            'https://rsshub.rssforever.com/nikkei/cn/latest',
        ]
        
        for backup in backup_urls:
            try:
                print(f"  尝试: {backup}")
                resp = fetch_with_retry(backup)
                if resp:
                    print(f"  ✅ 使用备用实例成功")
                    break
            except:
                continue
        else:
            print("❌ 所有 RSSHub 实例均不可用")
            # 生成空 RSS
            generate_empty_rss("RSSHub 服务不可用，请稍后重试")
            return
    
    # 解析 RSS
    feed = feedparser.parse(resp.text)
    
    if not feed.entries:
        print("❌ RSS 中没有文章")
        generate_empty_rss("未获取到文章")
        return
    
    print(f"找到 {len(feed.entries)} 篇文章")
    
    rss_items = []
    for idx, entry in enumerate(feed.entries[:15]):
        title = entry.get('title', '无标题')
        link = entry.get('link', '')
        pub_date = entry.get('published', '')
        description = entry.get('description', '')
        summary = entry.get('summary', '')
        
        print(f"[{idx+1}] {title[:40]}...")
        
        # 优先使用 description 或 summary
        content = description or summary
        
        # 如果内容太短或包含HTML，尝试抓取全文
        if len(content) < 100 or '<' in content:
            print(f"  尝试抓取全文...")
            full_text = extract_article_content(link)
            if full_text and len(full_text) > len(content):
                content = full_text
                print(f"  ✅ 获取全文: {len(content)} 字符")
            else:
                # 清理 HTML 标签
                content = re.sub(r'<[^>]+>', '', content)
                content = re.sub(r'\s+', ' ', content).strip()
                print(f"  ⚠ 使用摘要: {len(content)} 字符")
        else:
            print(f"  ✓ 正文长度: {len(content)} 字符")
        
        # 繁转简
        content = cc.convert(content)
        title = cc.convert(title)
        
        # 格式化日期
        try:
            if pub_date:
                dt = datetime.fromtimestamp(time.mktime(entry.get('published_parsed', time.gmtime())))
                pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S +0800')
            else:
                pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')
        except:
            pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')
        
        rss_items.append({
            'title': title,
            'link': link,
            'description': content,
            'pubDate': pub_date,
            'guid': link,
        })
    
    # 生成 RSS
    generate_rss_xml(rss_items)

def generate_rss_xml(items):
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
    xml += '<channel>\n'
    xml += '  <title>日经中文网 RSS（RSSHub）</title>\n'
    xml += '  <link>https://cn.nikkei.com/</link>\n'
    xml += '  <description>通过 RSSHub 获取日经中文网新闻</description>\n'
    xml += f'  <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")}</lastBuildDate>\n'
    
    for item in items:
        xml += '  <item>\n'
        xml += f'    <title>{escape_xml(item["title"])}</title>\n'
        xml += f'    <link>{escape_xml(item["link"])}</link>\n'
        xml += f'    <guid>{escape_xml(item["guid"])}</guid>\n'
        xml += f'    <pubDate>{item["pubDate"]}</pubDate>\n'
        xml += f'    <description><![CDATA[{item["description"]}]]></description>\n'
        xml += '  </item>\n'
    
    xml += '</channel>\n</rss>'
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(xml)
    
    print(f"\n✅ 完成！已生成 {len(items)} 篇 -> {OUTPUT_FILE}")

def generate_empty_rss(reason):
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<rss version="2.0">\n'
    xml += '<channel>\n'
    xml += '  <title>日经中文网 RSS</title>\n'
    xml += '  <link>https://cn.nikkei.com/</link>\n'
    xml += f'  <description>抓取失败: {reason}</description>\n'
    xml += f'  <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")}</lastBuildDate>\n'
    xml += '</channel>\n</rss>'
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(xml)
    
    print(f"⚠️ 生成空 RSS: {reason}")

def escape_xml(text):
    if not text:
        return ''
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

if __name__ == '__main__':
    fetch_and_convert()