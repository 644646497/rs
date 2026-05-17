import requests
import feedparser
import trafilatura
from datetime import datetime
import time

# ✅ 修复点1：使用日经中文网官方 RSS 地址，替代失效的第三方接口
RSS_URL = "https://china.nikkei.com/index.php/rssindex/latest/rss.xml"
OUTPUT_FILE = "feed.xml"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
}

def fetch_fulltext(url):
    try:
        # 增加超时设置，防止卡死
        downloaded = trafilatura.fetch_url(url, user_agent=HEADERS['User-Agent'], timeout=15)
        if downloaded:
            # no_fallback=True 可以尝试提取即使没有明显文章标签的内容
            result = trafilatura.extract(downloaded, include_formatting=True, no_fallback=True)
            if result:
                return result
    except Exception as e:
        print(f"  ❌ 全文提取失败: {e}")
    return None

def main():
    print(f"🚀 开始抓取日经中文网...")
    print(f"🔗 数据源: {RSS_URL}")
    
    try:
        resp = requests.get(RSS_URL, headers=HEADERS, timeout=20)
        print(f"📡 HTTP状态码: {resp.status_code}")
        
        if resp.status_code != 200:
            print("❌ 无法连接RSS源，请检查网络或URL是否有效。")
            return
            
        feed = feedparser.parse(resp.content)
        
        # ✅ 修复点2：处理 feed.entries 可能不存在的情况
        if not feed.entries:
            print("❌ 解析失败：未找到文章列表。可能是RSS格式变更。")
            return

        print(f"📰 找到 {len(feed.entries)} 篇文章")
        
    except Exception as e:
        print(f"❌ 抓取RSS失败: {e}")
        return
    
    rss_items = []
    
    # 只抓取最新的 5 篇，避免运行时间过长（日经中文网文章较多）
    max_articles = 5 
    for i, entry in enumerate(feed.entries[:max_articles]):
        title = entry.get('title', '无标题')
        link = entry.get('link')
        
        # ✅ 修复点3：增加链接有效性检查
        if not link:
            continue
            
        print(f"\n[{i+1}/{max_articles}] 正在处理: {title[:30]}...")
        
        # 尝试抓取全文
        content = fetch_fulltext(link)
        
        # 如果全文抓取失败，回退到 RSS 自带的摘要
        if not content:
            print("  ⚠️ 全文抓取失败，使用摘要代替")
            content = entry.get('summary', entry.get('description', '无内容'))
        
        # 处理发布时间
        pubdate = datetime.now()
        if entry.get('published_parsed'):
            pubdate = datetime(*entry['published_parsed'][:6])
        elif entry.get('updated_parsed'):
            pubdate = datetime(*entry['updated_parsed'][:6])
        
        rss_items.append({
            'title': title,
            'link': link,
            'description': content,
            'pubdate': pubdate
        })
        
        # 礼貌抓取，防止被封IP
        time.sleep(1.5)
    
    # 生成 XML
    if not rss_items:
        print("❌ 没有抓取到任何有效内容，程序退出。")
        return

    print(f"\n🛠️ 正在生成 XML 文件...")
    rss_output = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>日经中文网 - 全文修复版</title>
<link>https://china.nikkei.com</link>
<description>由Python脚本自动抓取的日经中文网全文RSS</description>
<lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>
'''
    
    for item in rss_items:
        # ✅ 修复点4：对 description 进行 CDATA 包裹，防止 XML 格式报错
        desc_content = f"""
        <h3>{item['title']}</h3>
        <p><small>原文链接: <a href="{item['link']}">{item['link']}</a></small></p>
        <hr/>
        {item['description']}
        """
        
        rss_output += f'''
<item>
    <title><![CDATA[{item['title']}]]></title>
    <link>{item['link']}</link>
    <guid isPermaLink="true">{item['link']}</guid>
    <pubDate>{item['pubdate'].strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate>
    <description><![CDATA[{desc_content}]]></description>
</item>'''
    
    rss_output += '\n</channel>\n</rss>'
    
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(rss_output)
        print(f"\n✅ 成功！已生成 {OUTPUT_FILE}，包含 {len(rss_items)} 篇文章。")
    except Exception as e:
        print(f"\n❌ 文件写入失败: {e}")

if __name__ == "__main__":
    main()
