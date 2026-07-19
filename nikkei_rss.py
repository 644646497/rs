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
    
    # 如果 RSSHub 不行，尝试直接用日经网站
    for i in range(max_retries):
        try:
            resp = session.get(url, headers=headers, timeout=30, allow_redirects=True)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            return resp
        except requests.exceptions.ConnectionError:
            print(f"  连接失败 (尝试 {i+1}/{max_retries})，可能是网络限制")
            if i == max_retries - 1:
                raise
            time.sleep(5)
        except Exception as e:
            print(f"  请求失败 (尝试 {i+1}/{max_retries}): {e}")
            if i == max_retries - 1:
                raise
            time.sleep(3)
    
    return None

def extract_article(html):
    """提取文章内容"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 删除无关标签
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'form', 'noscript', 'svg']):
        tag.decompose()
    
    # 获取所有文本，保留段落结构
    text = soup.get_text(separator='\n', strip=True)
    
    # 按行分割，过滤短行和无关内容
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        # 保留长度大于20的行，排除导航、版权等
        if len(line) > 20 and not any(keyword in line for keyword in 
            ['版权所有', 'Copyright', '关于我们', '联系我们', '广告', '招聘', '订阅', '登录', '注册', '热搜']):
            lines.append(line)
    
    # 如果行数太少，放宽条件
    if len(lines) < 5:
        lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 10]
    
    # 合并
    content = '\n\n'.join(lines[:30])  # 限制最多30段
    
    # 清理
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = re.sub(r'【[^】]{0,30}】', '', content)
    content = re.sub(r'[◆◇●○■□▲△★☆]', '', content)
    
    return content

def fetch_and_convert():
    print(f"抓取日经中文网: {INDEX_URL}")
    print("⚠️ 注意：日经中文网可能有反爬限制，如抓取失败属正常")
    
    try:
        resp = fetch_with_retry(INDEX_URL)
    except Exception as e:
        print(f"❌ 无法访问日经中文网: {e}")
        print("\n💡 建议方案：")
        print("1. 换成其他新闻源，如 BBC 中文网")
        print("2. 使用代理或 VPN")
        print("3. 改用 RSSHub 的国内镜像")
        generate_empty_rss(f"无法访问: {e}")
        return
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # 提取文章链接
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        title = a.get_text(strip=True)
        
        # 匹配日经文章链接
        if (re.search(r'/(politicsaeconomy|economy|business|technology|finance|world|china)/[^/]+\.html', href) and
            title and len(title) > 10 and not re.match(r'^[\d\s]+$', title)):
            
            url = href if href.startswith('http') else 'https://cn.nikkei.com' + (href if href.startswith('/') else '/' + href)
            
            # 去重
            if not any(link['url'] == url for link in links):
                links.append({'url': url, 'title': title})
        
        if len(links) >= 25:
            break
    
    # 去重
    seen = set()
    unique_links = []
    for link in links:
        if link['url'] not in seen:
            seen.add(link['url'])
            unique_links.append(link)
    
    unique_links = unique_links[:15]
    
    if not unique_links:
        print("❌ 未找到文章链接，网站结构可能已变化")
        generate_empty_rss("未找到文章")
        return
    
    print(f"找到 {len(unique_links)} 篇文章")
    
    rss_items = []
    for idx, link in enumerate(unique_links):
        print(f"[{idx+1}] {link['title'][:40]}...")
        
        try:
            time.sleep(1.5)  # 延迟，避免被屏蔽
            
            article_resp = fetch_with_retry(link['url'])
            raw_text = extract_article(article_resp.text)
            
            # 繁转简
            cleaned = cc.convert(raw_text)
            
            if len(cleaned) < 50:
                print(f"  ⚠ 正文过短 ({len(cleaned)}字)，可能被屏蔽")
                # 直接从页面获取所有可见文本
                soup2 = BeautifulSoup(article_resp.text, 'html.parser')
                for tag in soup2(['script', 'style', 'nav', 'header', 'footer']):
                    tag.decompose()
                all_text = soup2.get_text(separator='\n', strip=True)
                lines2 = [line.strip() for line in all_text.split('\n') if len(line.strip()) > 30]
                cleaned = cc.convert('\n\n'.join(lines2[:20]))
                
                if len(cleaned) > 50:
                    print(f"  ✓ 备用方法获取 {len(cleaned)} 字符")
                else:
                    print(f"  ❌ 仍然过短，可能被反爬")
            else:
                print(f"  ✓ 正文长度: {len(cleaned)} 字符")
            
            # 生成日期
            pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            cleaned = f"无法获取文章内容"
            pub_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        rss_items.append({
            'title': cc.convert(link['title']),
            'link': link['url'],
            'description': cleaned,
            'pubDate': pub_date,
            'guid': link['url'],
        })
    
    # 生成 RSS
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<rss version="2.0">\n'
    xml += '<channel>\n'
    xml += '  <title>日经中文网 RSS（简体）</title>\n'
    xml += '  <link>https://cn.nikkei.com/</link>\n'
    xml += '  <description>日经中文网新闻（如无法访问请换源）</description>\n'
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