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
        response.raise_for_status() # 检查HTTP错误
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 针对移动版页面的选择器逻辑
        # 移动版通常使用 article 标签或者特定的 class
        # 这里尝试查找所有的链接，并过滤出文章链接
        links = soup.find_all('a', href=True)
        
        seen_links = set()
        
        for link_tag in links:
            href = link_tag['href']
            # 过滤：必须是文章详情页 (通常包含 /pc/article/ 或类似结构)
            # 并且不能是重复的
            if '/pc/article/' in href or '/article/' in href:
                # 补全URL (如果是相对路径)
                if not href.startswith('http'):
                    full_url = f"https://cn.nikkei.com{href}"
                else:
                    full_url = href
                
                if full_url in seen_links:
                    continue
                seen_links.add(full_url)
                
                # 获取标题 (通常在 a 标签内部，或者父级 div 中)
                title = link_tag.get_text(strip=True)
                
                # 简单清洗，去除空标题或过短的标题
                if len(title) > 5: 
                    articles.append({
                        'title': title,
                        'link': full_url,
                        'description': f"查看最新报道：{title}", # 移动版很难抓取摘要，暂用标题代替
                        'pubDate': datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
                    })
                    
        print(f"[+] 成功抓取到 {len(articles)} 篇文章")

    except Exception as e:
        print(f"[!] 抓取失败: {str(e)}", file=sys.stderr)
        return []

    return articles[:15] # 限制数量，避免生成过大的XML

def generate_rss(articles):
    """
    生成 RSS XML 文件
    """
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    
    ET.SubElement(channel, "title").text = "日经中文网 - 最新资讯"
    ET.SubElement(channel, "link").text = "https://cn.nikkei.com/"
    ET.SubElement(channel, "description").text = "日经中文网免费文章 RSS 订阅源 (自动更新)"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    for item in articles:
        item_elem = ET.SubElement(channel, "item")
        ET.SubElement(item_elem, "title").text = item['title']
        ET.SubElement(item_elem, "link").text = item['link']
        ET.SubElement(item_elem, "description").text = item['description']
        ET.SubElement(item_elem, "guid", isPermaLink="true").text = item['link']
        ET.SubElement(item_elem, "pubDate").text = item['pubDate']
        
    return ET.tostring(rss, encoding='unicode', xml_declaration=True)

if __name__ == "__main__":
    news_list = fetch_nikkei_news()
    
    if news_list:
        xml_content = generate_rss(news_list)
        
        # 输出文件名，需与你的 yml 配置一致
        output_file = "nikkei_feed.xml" 
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(xml_content)
            
        print(f"[OK] RSS 文件已生成: {output_file}")
    else:
        print("[ERROR] 未获取到任何文章，XML 未更新")
