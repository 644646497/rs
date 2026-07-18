#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from opencc import OpenCC
import time

cc = OpenCC('t2s')

# 日经中文网
BASE_URL = 'https://cn.nikkei.com'
OUTPUT_FILE = 'nikkei_feed.xml'

def fetch_with_retry(url, max_retries=3):
    """带重试的请求"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://cn.nikkei.com/',
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

def extract_articles_from_page(url):
    """从页面提取文章列表"""
    try:
        resp = fetch_with_retry(url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        articles = []
        
        # 查找所有文章链接
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            title = a.get_text(strip=True)
            
            # 过滤日经文章链接
            if href.startswith('/article/') or href.startswith('/news/') or href.startswith('/columnviewpoint/'):
                # 过滤无效标题
                if not title or len(title) < 10:
                    continue
                if any(k in title for k in ['首页', '新闻', '专栏', '搜索', '登录', '注册', '更多', 'RSS']):
                    continue
                
                # 构建完整URL
                if href.startswith('/'):
                    full_url = BASE_URL + href
                else:
                    full_url = href
                
                articles.append({
                    'title': title,
                    'url': full_url
                })
        
        return articles
    except Exception as e:
        print(f"  ❌ 抓取列表失败: {e}")
        return []

def extract_full_text(html):
    """提取正文"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 移除干扰元素
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'iframe']):
        tag.decompose()
    
    # 日经文章主体
    article = None
    for selector in ['article', '.content', '.article-content', '.post-content', '#main']:
        article = soup.select_one(selector)
        if article:
            break
    
    if not article:
        article = soup.body
    
    # 提取段落
    paragraphs = article.find_all('p') if article else []
    if not paragraphs:
        return soup.get_text(strip=True)
    
    # 过滤太短的段落
    valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
    
    text = '\n\n'.join(valid_paragraphs)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text

def fetch_and_convert():
    print(f"抓取日经中文网...")
    
    # 抓取多个栏目
    urls = [
        'https://cn.nikkei.com/',
        'https://cn.nikkei.com/china/',
        'https://cn.nikkei.com/politicsaeconomy/',
        'https://cn.nikkei.com/industry/',
        'https://cn.nikkei.com/columnviewpoint/',
    ]
    
    all_articles = []
    seen_urls = set()
    
    for url in urls:
        print(f"  抓取栏目: {url}")
        articles = extract_articles_from_page(url)
        
        for article in articles:
            if article['url'] not in seen_urls:
                seen_urls.add(article['url'])
                all_articles.append(article)
        
        if len(all_articles) >= 30:
            break
        
        time.sleep(1)
    
    print(f"找到 {len(all_articles)} 篇文章")
    
    rss_items = []
    for idx, article in enumerate(all_articles[:30]):
        article_url = article['url']
        title = article['title']
        
        print(f"[{idx+1}] 处理: {title[:50]}...")
        
        try:
            resp = fetch_with_retry(article_url)
            raw_text = extract_full_text(resp.text)
            cleaned = cc.convert(raw_text)
            
            if len(cleaned) < 100:
                print(f"  ⚠ 正文过短({len(cleaned)}字)，使用摘要")
                cleaned = cc.convert(f"原文链接：{article_url}")
            else:
                print(f"  ✓ 正文长度: {len(cleaned)} 字符")
            
            pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        except Exception as e:
            print(f"  ❌ 出错: {e}")
            cleaned = cc.convert(f"原文链接：{article_url}")
            pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        rss_items.append({
            'title': cc.convert(title),
            'link': article_url,
            'description': cleaned,
            'pubDate': pub_date,
            'guid': article_url,
        })
    
    # 生成 XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<rs