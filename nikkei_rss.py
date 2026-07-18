#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from opencc import OpenCC
import time

cc = OpenCC('t2s')

BASE_URL = 'https://cn.nikkei.com'
OUTPUT_FILE = 'nikkei_feed.xml'

def fetch_with_retry(url, max_retries=3):
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
    return None

def extract_articles_from_page(url):
    """从页面提取文章列表"""
    try:
        resp = fetch_with_retry(url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        articles = []
        
        # 调试：保存页面内容看看
        # print(f"页面长度: {len(resp.text)}")
        
        # 方法1: 查找所有 a 标签，过滤文章链接
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            title = a.get_text(strip=True)
            
            # 日经中文网文章链接格式
            if href and ('/article/' in href or '/news/' in href or '/columnviewpoint/' in href):
                # 过滤无效标题
                if not title or len(title) < 10:
                    continue
                if any(k in title for k in ['首页', '新闻', '专栏', '搜索', '登录', '注册', '更多', 'RSS', '评论', '专题']):
                    continue
                
                # 去重
                if href.startswith('/'):
                    full_url = BASE_URL + href
                else:
                    full_url = href
                
                # 检查是否已存在
                exists = False
                for a in articles:
                    if a['url'] == full_url:
                        exists = True
                        break
                if not exists:
                    articles.append({
                        'title': title,
                        'url': full_url
                    })
                    print(f"    找到: {title[:40]}...")
        
        # 如果没有找到，尝试方法2: 查找 div.article-list 或类似容器
        if len(articles) == 0:
            print("  尝试备用解析方式...")
            for div in soup.find_all('div'):
                # 查找包含文章链接的div
                links = div.find_all('a')
                for a in links:
                    href = a.get('href', '')
                    title = a.get_text(strip=True)
                    if href and ('/article/' in href or '/news/' in href) and len(title) > 10:
                        if href.startswith('/'):
                            full_url = BASE_URL + href
                        else:
                            full_url = href
                        articles.append({
                            'title': title,
                            'url': full_url
                        })
                        print(f"    找到(备用): {title[:40]}...")
        
        return articles
    except Exception as e:
        print(f"  ❌ 抓取列表失败: {e}")
        return []

def extract_full_text(html):
    """提取正文"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 移除干扰元素
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'iframe', 'noscript']):
        tag.decompose()
    
    # 尝试多个选择器
    article = None
    selectors = [
        'article',
        '.article-body',
        '.article-content',
        '.content',
        '.post-content',
        '#article-body',
        '#content',
        '.entry-content',
        '.main-content'
    ]
    
    for selector in selectors:
        article = soup.select_one(selector)
        if article:
            print(f"    使用选择器: {selector}")
            break
    
    if not article:
        # 尝试找所有段落
        paragraphs = soup.find_all('p')
        if paragraphs and len(paragraphs) > 3:
            # 构建一个包含所有段落的容器
            article = soup.new_tag('div')
            for p in paragraphs:
                if len(p.get_text(strip=True)) > 30:
                    article.append(p)
        else:
            article = soup.body
    
    # 提取段落
    paragraphs = article.find_all('p') if article else []
    if not paragraphs:
        # 如果没找到段落，获取所有文本
        text = soup.get_text(strip=True)
        # 清理多余空白
        text = re.sub(r'\s+', ' ', text)
        return text[:5000]  # 限制长度
    
    # 过滤太短的段落
    valid_paragraphs = []
    for p in paragraphs:
        text = p.get_text(strip=True)
        if len(text) > 30:
            valid_paragraphs.append(text)
    
    if not valid_paragraphs:
        return soup.get_text(strip=True)[:5000]
    
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
        
        print(f"  当前共找到 {len(all_articles)} 篇文章")
        
        if len(all_articles) >= 30:
            break
        
        time.sleep(1)
    
    print(f"\n总共找到 {len(all_articles)} 篇文章")
    
    if not all_articles:
        print("❌ 没有找到任何文章！")
        # 生成一个空的但有效的RSS
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<rss version="2.0">\n'
        xml += '<channel>\n'
        xml += '  <title>日经中文网 全文 RSS（简体）</title>\n'
        xml += '  <link>https://cn.nikkei.com/</link>\n'
        xml += '  <description>暂无文章</description>\n'
        xml += f'  <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")}</lastBuildDate>\n'
        xml += '</channel>\n'
        xml += '</rss>'
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(xml)
        return
    
    rss_items = []
    for idx, article in enumerate(all_articles[:30]):
        article_url = article['url']
        title = article['title']
        
        print(f"[{idx+1}] 处理: {title[:50]}...")
        
        try:
            resp = fetch_with_retry(article_url)
            if resp:
                raw_text = extract_full_text(resp.text)
                cleaned = cc.convert(raw_text)
                
                if len(cleaned) < 100:
                    print(f"  ⚠ 正文过短({len(cleaned)}字)")
                else:
                    print(f"  ✓ 正文长度: {len(cleaned)} 字符")
            else:
                cleaned = cc.convert(f"原文链接：{article_url}")
                print(f"  ❌ 请求失败")
            
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
        
        time.sleep(0.5)  # 避免请求过快
    
    # 生成 XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<rss version="2.0">\n'
    xml += '<channel>\n'
    xml += '  <title>日经中文网 全文 RSS（简体）</title>\n'
    xml += '  <link>https://cn.nikkei.com/</link>\n'
    xml += '  <description>全文抓取、繁转简</description>\n'
    xml += f'  <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")}</lastBuildDate>\n'
    
    for item in rss_items:
        xml += '  <item>\n'
        xml += f'    <title>{escape_xml(item["title"])}</title>\n'
        xml += f'    <link>{item["link"]}</link>\n'
        xml += f'    <guid>{item["guid"]}</guid>\n'
        xml += f'    <pubDate>{item["pubDate"]}</pubDate>\n'
        xml += f'    <description><![CDATA[{item["description"]}]]></description>\n'
        xml += '  </item>\n'
    
    xml += '</channel>\n'
    xml += '</rss>'
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(xml)
    
    print(f"\n✅ 完成！已生成 {len(rss_items)} 篇 -> {OUTPUT_FILE}")

def escape_xml(text):
    if not text:
        return ''
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

if __name__ == '__main__':
    fetch_and_convert()