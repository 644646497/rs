#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from opencc import OpenCC
import time
import json

cc = OpenCC('t2s')

INDEX_URL = 'https://cn.nikkei.com/politicsaeconomy/'
OUTPUT_FILE = 'nikkei_feed.xml'

def fetch_with_retry(url, max_retries=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,ja;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }
    session = requests.Session()
    for i in range(max_retries):
        try:
            resp = session.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            # 日经中文网可能是UTF-8或GBK
            if 'charset' in resp.headers.get('content-type', '').lower():
                resp.encoding = resp.apparent_encoding or 'utf-8'
            else:
                resp.encoding = 'utf-8'
            return resp
        except Exception as e:
            print(f"  请求失败 (尝试 {i+1}/{max_retries}): {e}")
            if i == max_retries - 1:
                raise
            time.sleep(3)

def extract_article_and_date(html, url):
    """提取正文和发布日期，返回 (text, date_str)"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. 提取发布时间
    pub_date = None
    
    # 方法1: 查找包含日期的元素
    date_selectors = [
        'time',
        '.date',
        '.time',
        '.pub-date',
        '.article-date',
        '.post-date',
        '.entry-date',
        '.publish-date',
        '[class*="date"]',
        '[class*="time"]',
        '[class*="publish"]',
    ]
    
    for selector in date_selectors:
        elements = soup.select(selector)
        for elem in elements:
            text = elem.get_text(strip=True)
            # 匹配日期模式
            match = re.search(r'(\d{4})[/年](\d{1,2})[/月](\d{1,2})', text)
            if match:
                pub_date = text
                break
            # 也匹配 datetime 属性
            if elem.get('datetime'):
                pub_date = elem.get('datetime')
                break
        if pub_date:
            break
    
    # 方法2: 查找 meta 标签
    if not pub_date:
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            if meta.get('property') in ['article:published_time', 'og:pubdate']:
                pub_date = meta.get('content')
                break
            if meta.get('name') in ['pubdate', 'publish-date', 'date']:
                pub_date = meta.get('content')
                break
    
    # 方法3: 用正则在整个页面查找
    if not pub_date:
        match = re.search(r'(\d{4})[/年](\d{1,2})[/月](\d{1,2})', html)
        if match:
            pub_date = match.group(0)
    
    # 2. 提取正文内容
    # 删除不需要的标签
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'form', 'noscript', 'svg', 'img']):
        tag.decompose()
    
    # 尝试多种选择器找到文章内容
    content_selectors = [
        'article',
        '.article-body',
        '.article-content',
        '.content-body',
        '.entry-content',
        '.post-content',
        '.story-content',
        '.main-text',
        '.article-text',
        '#article-body',
        '#content',
        '.detail-body',
        '.text-body',
    ]
    
    article_content = None
    for selector in content_selectors:
        article_content = soup.select_one(selector)
        if article_content:
            break
    
    if not article_content:
        # 如果找不到特定容器，使用 body
        article_content = soup.body
    
    # 提取段落
    paragraphs = article_content.find_all('p') if article_content else []
    
    if paragraphs:
        valid_paragraphs = []
        for p in paragraphs:
            p_text = p.get_text(strip=True)
            # 过滤条件
            if (len(p_text) > 20 and 
                not re.match(r'^[\d\s]+$', p_text) and
                not any(keyword in p_text for keyword in ['版权所有', 'Copyright', '关于我们', '联系我们', '广告', '招聘', '订阅'])):
                valid_paragraphs.append(p_text)
        
        # 如果过滤后没内容，放宽条件
        if not valid_paragraphs:
            valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 10]
        
        text = '\n\n'.join(valid_paragraphs)
    else:
        # 如果没有段落，获取所有文本
        text = article_content.get_text(strip=True) if article_content else ''
    
    # 清理文本
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'【[^】]{0,30}】', '', text)  # 移除短标签
    text = re.sub(r'[◆◇●○■□▲△★☆]', '', text)
    
    # 如果正文太短，尝试直接获取所有可见文本
    if len(text) < 100:
        # 获取所有可见文本
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)
        # 按行分割，过滤短行
        lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 20]
        text = '\n\n'.join(lines[:30])  # 限制行数
    
    # 3. 格式化日期
    if pub_date:
        try:
            # 尝试多种日期格式
            match = re.search(r'(\d{4})[/年](\d{1,2})[/月](\d{1,2})', pub_date)
            if match:
                year, month, day = match.groups()
                # 尝试提取时间
                time_match = re.search(r'(\d{1,2}):(\d{1,2})', pub_date)
                if time_match:
                    hour, minute = time_match.groups()
                    dt = datetime(int(year), int(month), int(day), int(hour), int(minute))
                else:
                    dt = datetime(int(year), int(month), int(day))
                pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S +0800')
            else:
                # 尝试解析ISO格式
                try:
                    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S +0800')
                except:
                    pass
        except Exception as e:
            print(f"  日期解析失败: {e}")
            pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')
    else:
        pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')
    
    return text, pub_date

def fetch_and_convert():
    print(f"抓取日经中文网: {INDEX_URL}")
    
    try:
        resp = fetch_with_retry(INDEX_URL)
    except Exception as e:
        print(f"❌ 无法访问日经中文网: {e}")
        print("可能原因: 1) 网络限制 2) 反爬机制 3) 网站改版")
        return
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    links = []
    # 匹配所有文章链接
    for a in soup.find_all('a', href=True):
        href = a['href']
        # 匹配文章链接模式
        if re.search(r'/(politicsaeconomy|economy|business|technology|finance|world|china)/[^/]+\.html', href):
            url = href if href.startswith('http') else 'https://cn.nikkei.com' + href
            title = a.get_text(strip=True)
            # 过滤标题
            if title and len(title) > 10 and not re.match(r'^[\d\s]+$', title):
                # 检查是否已有该链接
                if not any(link['url'] == url for link in links):
                    links.append({'url': url, 'title': title})
        
        if len(links) >= 30:
            break
    
    # 去重
    unique_links = []
    seen_urls = set()
    for link in links:
        if link['url'] not in seen_urls:
            seen_urls.add(link['url'])
            unique_links.append(link)
    
    unique_links = unique_links[:15]
    
    if not unique_links:
        print("❌ 未找到任何文章链接，网站结构可能已变化")
        return
    
    print(f"找到 {len(unique_links)} 篇文章")
    
    rss_items = []
    for idx, link in enumerate(unique_links):
        print(f"[{idx+1}/{len(unique_links)}] {link['title'][:40]}...")
        
        try:
            time.sleep(1)  # 避免请求过快
            article_resp = fetch_with_retry(link['url'])
            raw_text, pub_date = extract_article_and_date(article_resp.text, link['url'])
            
            # 繁转简
            cleaned = cc.convert(raw_text)
            
            # 清理多余空白
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
            cleaned = cleaned.strip()
            
            if len(cleaned) < 30:
                print(f"  ⚠ 正文过短 ({len(cleaned)}字)，可能被反爬")
                # 尝试获取所有文本
                soup2 = BeautifulSoup(article_resp.text, 'html.parser')
                for tag in soup2(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    tag.decompose()
                all_text = soup2.get_text(separator='\n', strip=True)
                # 取前2000字符
                cleaned = cc.convert(all_text[:2000])
                if len(cleaned) > 30:
                    print(f"  ✓ 备用方法获取 {len(cleaned)} 字符")
            else:
                print(f"  ✓ 正文长度: {len(cleaned)} 字符")
            
            print(f"  📅 {pub_date}")
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            cleaned = f"无法获取文章内容: {e}"
            pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        rss_items.append({
            'title': cc.convert(link['title']),
            'link': link['url'],
            'description': cleaned,
            'pubDate': pub_date,
            'guid': link['url'],
        })
    
    # 生成 XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
    xml += '<channel>\n'
    xml += '  <title>日经中文网 RSS</title>\n'
    xml += '  <link>https://cn.nikkei.com/</link>\n'
    xml += '  <description>日经中文网新闻全文（繁转简）</description>\n'
    xml += f'  <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")}</lastBuildDate>\n'
    
    for item in rss_items:
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
    
    print(f"\n✅ 完成！已生成 {len(rss_items)} 篇 -> {OUTPUT_FILE}")

def escape_xml(text):
    if not text:
        return ''
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

if __name__ == '__main__':
    fetch_and_convert()