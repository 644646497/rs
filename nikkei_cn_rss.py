# nikkei_cn_rss.py
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime
import os

def fetch_nikkei_news():
    """
    抓取日经中文网最新文章
    """
    url = "https://cn.nikkei.com/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    articles = []
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8' # 确保编码正确
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 日经中文网的新闻列表通常包含在特定的 class 中
        # 这里的 CSS 选择器是根据 cn.nikkei.com 常见结构编写的，可能需要随网站改版微调
        news_items = soup.select('div.c-column__list article, div.index-news-list article, .news-list li') 
        
        for item in news_items[:10]: # 限制抓取前10条
            title_tag = item.select_one('h3 a, h2 a, .title a')
            desc_tag = item.select_one('p, .summary, .txt')
            
            if title_tag:
                title = title_tag.get_text(strip=True)
                link = title_tag.get('href', '')
                
                # 处理相对链接
                if link.startswith('/'):
                    link = f"https://cn.nikkei.com{link}"
                    
                description = desc_tag.get_text(strip=True) if desc_tag else ""
                
                articles.append({
                    'title': title,
                    'link': link,
                    'description': description
                })
                
    except Exception as e:
        print(f"Error fetching Nikkei CN: {e}")
        
    return articles

def generate_xml(articles, filename):
    """
    生成 RSS XML 文件
    """
    rss = ET.Element('rss', version="2.0")
    channel = ET.SubElement(rss, 'channel')
    
    # RSS 频道基本信息
    ET.SubElement(channel, 'title').text = '日经中文网 - 最新资讯'
    ET.SubElement(channel, 'link').text = 'https://cn.nikkei.com/'
    ET.SubElement(channel, 'description').text = '日经中文网免费文章 RSS 订阅源'
    ET.SubElement(channel, 'lastBuildDate').text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    for art in articles:
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = art['title']
        ET.SubElement(item, 'link').text = art['link']
        ET.SubElement(item, 'description').text = art['description']
        ET.SubElement(item, 'guid', isPermaLink="true").text = art['link']
        ET.SubElement(item, 'pubDate').text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="\t") # Python 3.9+ 支持美化输出
    tree.write(filename, encoding='unicode', xml_declaration=True)
    print(f"Generated {filename} with {len(articles)} items.")

if __name__ == "__main__":
    news_data = fetch_nikkei_news()
    output_file = "nikkei_feed.xml"
    generate_xml(news_data, output_file)
