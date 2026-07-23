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
        response.encoding = 'utf-8' # 强制指定编码
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找文章列表容器 (针对移动版结构优化)
        # 通常移动版的文章链接在 .article-list 或类似的 class 中，或者是直接的 a 标签列表
        # 这里我们尝试寻找包含 /article/ 的链接
        links = soup.find_all('a', href=True)
        
        seen_urls = set()
        
        for link in links:
            href = link['href']
            title_tag = link.find('h3') or link.find('h4') or link
            
            # 过滤条件：必须是文章页，且不能重复
            if '/article/' in href and href not in seen_urls:
                # 补全相对路径
                if href.startswith('/'):
                    full_url = f"https://m.cn.nikkei.com{href}"
                else:
                    full_url = href
                
                # 获取标题，清理空白字符
                title = title_tag.get_text(strip=True)
                
                if title and len(title) > 5: # 简单过滤无效标题
                    seen_urls.add(href)
                    articles.append({
                        'title': title,
                        'link': full_url,
                        'description': f"查看最新日经新闻: {title}"
                    })
                    
            # 限制抓取数量，避免过多
            if len(articles) >= 10:
                break

    except Exception as e:
        print(f"[!] 抓取失败: {e}", file=sys.stderr)
        return []

    print(f"[+] 成功抓取到 {len(articles)} 篇文章")
    return articles

def generate_rss(articles, output_file='nikkei_feed.xml'):
    """
    生成 RSS XML 文件
    """
    rss = ET.Element('rss', version="2.0")
    channel = ET.SubElement(rss, 'channel')
    
    # RSS 头部信息
    ET.SubElement(channel, 'title').text = '日经中文网 - 最新资讯'
    ET.SubElement(channel, 'link').text = 'https://cn.nikkei.com/'
    ET.SubElement(channel, 'description').text = '日经中文网免费文章 RSS 订阅源'
    ET.SubElement(channel, 'lastBuildDate').text = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    # 添加文章条目
    for article in articles:
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = article['title']
        ET.SubElement(item, 'link').text = article['link']
        ET.SubElement(item, 'description').text = article['description']
        ET.SubElement(item, 'pubDate').text = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        ET.SubElement(item, 'guid', isPermaLink="true").text = article['link']

    # 写入文件
    tree = ET.ElementTree(rss)
    ET.indent(tree, space="\t") # Python 3.9+ 支持美化输出
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"[*] RSS 文件已生成: {output_file}")

if __name__ == "__main__":
    news_list = fetch_nikkei_news()
    if news_list:
        generate_rss(news_list)
    else:
        print("[!] 未获取到任何文章，请检查网络或网站结构是否变更。")
