# nikkei_cn_rss.py
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime
import os
import sys

def fetch_nikkei_news():
    """
    抓取日经中文网（移动版）最新文章
    """
    # 使用移动版页面，结构简单，无复杂JS渲染，更易抓取
    url = "https://m.cn.nikkei.com/" 
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
    }
    
    articles = []
    
    print(f"[*] 正在请求: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 尝试查找新闻列表项 (基于移动版常见结构)
        # 注意：网站结构可能会变，这里使用了比较通用的选择器策略
        items = soup.find_all('div', class_='news-item') or soup.find_all('article') or soup.find_all('li', class_='item')
        
        if not items:
            # 如果上面的类名找不到，尝试找所有包含链接的列表项作为兜底
            print("[!] 未找到特定类名的新闻块，尝试通用解析...")
            items = soup.find_all('a', href=True)[:20] 

        count = 0
        for item in items:
            try:
                # 提取标题和链接
                a_tag = item.find('a') if item.name != 'a' else item
                
                if not a_tag or not a_tag.get('href'):
                    continue
                    
                title = a_tag.get_text(strip=True)
                link = a_tag['href']
                
                # 补全链接（如果是相对路径）
                if link.startswith('/'):
                    link = f"https://m.cn.nikkei.com{link}"
                elif not link.startswith('http'):
                    continue # 跳过非文章链接

                # 简单过滤，确保是文章页
                if 'story' not in link and 'article' not in link and len(title) < 5:
                    continue

                # 提取摘要或时间（可选）
                desc_tag = item.find('p') or item.find('span', class_='time')
                description = desc_tag.get_text(strip=True) if desc_tag else "日经中文网最新资讯"

                articles.append({
                    'title': title,
                    'link': link,
                    'description': description,
                    'pubDate': datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
                })
                
                count += 1
                if count >= 15: # 限制数量，避免文件过大
                    break
                    
            except Exception as e:
                continue

        print(f"[+] 成功抓取到 {len(articles)} 篇文章")
        
    except Exception as e:
        print(f"[ERROR] 抓取失败: {str(e)}")
        
    return articles

def generate_rss(articles):
    """
    生成 RSS XML 文件
    """
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    
    ET.SubElement(channel, "title").text = "日经中文网 - 最新资讯"
    ET.SubElement(channel, "link").text = "https://cn.nikkei.com/"
    ET.SubElement(channel, "description").text = "日经中文网免费文章 RSS 订阅源"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    for article in articles:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = article['title']
        ET.SubElement(item, "link").text = article['link']
        ET.SubElement(item, "description").text = article['description']
        ET.SubElement(item, "pubDate").text = article['pubDate']
        ET.SubElement(item, "guid", isPermaLink="true").text = article['link']

    tree = ET.ElementTree(root)
    output_file = "nikkei_feed.xml"
    
    # 写入文件
    with open(output_file, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)
        
    print(f"[*] RSS 文件已生成: {output_file}")

if __name__ == "__main__":
    news_list = fetch_nikkei_news()
    if news_list:
        generate_rss(news_list)
    else:
        print("[WARNING] 没有获取到内容，XML 将保持为空或仅包含头部。")
        # 即使没内容也生成一个空壳，防止 GitHub Actions 报错
        generate_rss([])
