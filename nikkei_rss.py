#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from opencc import OpenCC
import time

cc = OpenCC('t2s')

INDEX_URL = 'https://cn.nikkei.com/politicsaeconomy/'
OUTPUT_FILE = 'nikkei_feed.xml'

def fetch_with_retry(url, max_retries=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,ja;q=0.8',
    }
    for i in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            return resp
        except Exception as e:
            if i == max_retries - 1:
                raise
            time.sleep(2)

def extract_article_and_date(html):
    """提取正文和发布日期，返回 (text, date_str)"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. 提取发布时间 - 日经中文网格式
    pub_date = None
    # 日经常见日期格式: 2026/07/20 或 2026年7月20日
    date_patterns = [
        r'(\d{4})/(\d{1,2})/(\d{1,2})',
        r'(\d{4})年(\d{1,2})月(\d{1,2})日',
    ]
    
    # 查找日期元素
    for tag in soup.find_all(['div', 'span', 'p', 'time']):
        text = tag.get_text(strip=True)
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                pub_date = text
                break
        if pub_date:
            break
    
    # 如果没找到，尝试meta标签
    if not pub_date:
        meta_tag = soup.find('meta', {'name': re.compile(r'date|pubdate|publish', re.I)})
        if meta_tag:
            pub_date = meta_tag.get('content')
    
    # 2. 提取正文内容
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'form', 'noscript']):
        tag.decompose()
    
    # 日经中文网文章内容通常在 article 或特定 class 中
    article = soup.find('article') or soup.find('div', class_=re.compile(r'article|content|text|body', re.I))
    if not article:
        article = soup.body
    
    # 提取段落，过滤掉广告和短句
    paragraphs = article.find_all('p') if article else []
    if not paragraphs:
        # 尝试找 div 中的文本
        text = soup.get_text(strip=True)
        # 清理多余空白
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'。', '。\n', text)
        text = re.sub(r'！', '！\n', text)
        text = re.sub(r'？', '？\n', text)
    else:
        valid_paragraphs = []
        for p in paragraphs:
            p_text = p.get_text(strip=True)
            # 过滤掉导航、版权等短句
            if len(p_text) > 15 and not re.match(r'^[\d\s]+$', p_text):
                # 过滤掉常见的页脚文字
                if not any(keyword in p_text for keyword in ['版权所有', 'Copyright', '关于我们', '联系我们', '广告服务']):
                    valid_paragraphs.append(p_text)
        
        # 如果过滤后没有内容，使用所有段落
        if not valid_paragraphs:
            valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 10]
        
        text = '\n\n'.join(valid_paragraphs)
        text = re.sub(r'\n\s*\n', '\n\n', text)
    
    # 3. 格式化日期
    if pub_date:
        try:
            match = re.search(r'(\d{4})[/年](\d{1,2})[/月](\d{1,2})', pub_date)
            if match:
                year, month, day = match.groups()
                dt = datetime(int(year), int(month), int(day))
                pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S +0800')
            else:
                # 尝试解析 ISO 格式
                try:
                    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S +0800')
                except:
                    pass
        except:
            pass
    else:
        pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')
    
    # 清理文本中的广告和多余内容
    text = re.sub(r'【[^】]*】', '', text)  # 移除【】内的标签
    text = re.sub(r'[◆◇●○■□▲△★☆]+', '', text)  # 移除装饰符号
    
    return text, pub_date

def fetch_and_convert():
    print(f"抓取日经中文网: {INDEX_URL}")
    resp = fetch_with_retry(INDEX_URL)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    links = []
    # 日经中文网的链接模式
    for a in soup.find_all('a', href=True):
        href = a['href']
        # 匹配文章链接: /politicsaeconomy/数字.html 或其他分类
        if re.search(r'/(politicsaeconomy|economy|business|technology|finance)/[^/]+\.html', href):
            url = a['href']
            if not url.startswith('http'):
                url = 'https://cn.nikkei.com' + url if url.startswith('/') else 'https://cn.nikkei.com/' + url
            title = a.get_text(strip=True)
            # 过滤导航链接
            if title and len(title) > 8 and not re.match(r'^[\d\s]+$', title):
                # 避免重复
                if not any(link['url'] == url for link in links):
                    links.append({'url': url, 'title': title})
        if len(links) >= 25:
            break
    
    # 去重并限制数量
    seen = set()
 