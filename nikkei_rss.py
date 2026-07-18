import requests
from bs4 import BeautifulSoup
import feedgenerator
import datetime
import re
import json
import os
from typing import List, Dict, Optional

class NikkeiRSSGenerator:
    def __init__(self):
        self.base_url = "https://cn.nikkei.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def fetch_article_list(self, category: str = "trend", page: int = 1) -> List[Dict]:
        """
        获取文章列表
        category: politics, economy, industry, trend, column, opinion
        """
        url = f"{self.base_url}/more/{category}"
        params = {"page": page}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.encoding = 'utf-8'
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []
            
            # 根据实际HTML结构调整选择器
            article_items = soup.select('div.news-list ul li, div.newslist ul li, .item-list li')
            
            for item in article_items:
                link_tag = item.find('a')
                if not link_tag:
                    continue
                    
                title = link_tag.get_text(strip=True)
                href = link_tag.get('href', '')
                
                # 获取日期
                date_tag = item.find('span', class_='date') or item.find('time')
                pub_date = date_tag.get_text(strip=True) if date_tag else ""
                
                # 获取摘要
                summary_tag = item.find('p', class_='summary') or item.find('div', class_='summary')
                summary = summary_tag.get_text(strip=True) if summary_tag else ""
                
                if href and title:
                    if not href.startswith('http'):
                        href = self.base_url + href
                    articles.append({
                        'title': title,
                        'link': href,
                        'pub_date': pub_date,
                        'summary': summary
                    })
            
            return articles
            
        except requests.RequestException as e:
            print(f"获取文章列表失败: {e}")
            return []
    
    def fetch_article_content(self, url: str) -> Optional[str]:
        """获取文章全文内容"""
        try:
            response = self.session.get(url, timeout=30)
            response.encoding = 'utf-8'
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找文章内容
            content_selectors = [
                'div.article-main',
                'div.article-content',
                'div.main-content',
                'div.body-content',
                'div.article-body',
                '.article_detail',
                '.article-text'
            ]
            
            content_div = None
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    break
            
            if not content_div:
                # 尝试获取所有段落
                paragraphs = soup.select('p')
                if paragraphs:
                    content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
                    return content
                return None
            
            # 移除不需要的元素
            for tag in content_div.find_all(['script', 'style', 'iframe', 'ins', 'figure', '.advertisement']):
                tag.decompose()
            
            # 获取文本内容
            content = content_div.get_text(strip=True)
            # 清理多余空白
            content = re.sub(r'\s+', ' ', content).strip()
            
            # 如果内容太少，尝试获取更多
            if len(content) < 100:
                all_paragraphs = content_div.find_all('p')
                if all_paragraphs:
                    content = '\n\n'.join([p.get_text(strip=True) for p in all_paragraphs])
            
            return content if len(content) > 50 else None
            
        except requests.RequestException as e:
            print(f"获取文章内容失败 {url}: {e}")
            return None
    
    def generate_rss(self, category: str = "trend", max_articles: int = 20) -> str:
        """生成RSS feed"""
        feed = feedgenerator.Rss201rev2Feed(
            title=f"日经中文网 - {category}",
            link=self.base_url,
            description=f"日经中文网 {category} 栏目最新文章",
            language="zh-CN",
            feed_url=f"{self.base_url}/rss/{category}"
        )
        
        articles = self.fetch_article_list(category, page=1)
        
        # 如果第一页不够，获取第二页
        if len(articles) < max_articles:
            more_articles = self.fetch_article_list(category, page=2)
            articles.extend(more_articles)
        
        articles = articles[:max_articles]
        
        for article in articles:
            print(f"处理: {article['title']}")
            
            # 获取文章内容
            content = self.fetch_article_content(article['link'])
            
            # 解析日期
            pub_date = None
            if article['pub_date']:
                try:
                    # 尝试解析常见日期格式
                    date_str = article['pub_date']
                    if '/' in date_str:
                        pub_date = datetime.datetime.strptime(date_str, '%Y/%m/%d')
                    elif '-' in date_str:
                        pub_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    pass
            
            if not pub_date:
                pub_date = datetime.datetime.now()
            
            feed.add_item(
                title=article['title'],
                link=article['link'],
                description=content or article['summary'] or "原文请点击链接查看",
                content=content,
                pubdate=pub_date,
                unique_id=article['link'],
                categories=[category]
            )
        
        return feed.writeString('utf-8')
    
    def generate_multi_category_rss(self, categories: List[str] = None) -> str:
        """生成多个分类的RSS"""
        if categories is None:
            categories = ['politics', 'economy', 'industry', 'trend', 'column']
        
        feed = feedgenerator.Rss201rev2Feed(
            title="日经中文网综合",
            link=self.base_url,
            description="日经中文网综合RSS订阅",
            language="zh-CN",
            feed_url=f"{self.base_url}/rss/all"
        )
        
        all_articles = []
        for category in categories:
            articles = self.fetch_article_list(category, page=1)
            for article in articles:
                article['category'] = category
                all_articles.append(article)
        
        # 去重并排序
        seen_links = set()
        unique_articles = []
        for article in all_articles:
            if article['link'] not in seen_links:
                seen_links.add(article['link'])
                unique_articles.append(article)
        
        unique_articles = unique_articles[:50]
        
        for article in unique_articles:
            content = self.fetch_article_content(article['link'])
            
            pub_date = None
            if article['pub_date']:
                try:
                    date_str = article['pub_date']
                    if '/' in date_str:
                        pub_date = datetime.datetime.strptime(date_str, '%Y/%m/%d')
                    elif '-' in date_str:
                        pub_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    pass
            
            if not pub_date:
                pub_date = datetime.datetime.now()
            
            feed.add_item(
                title=f"[{article['category']}] {article['title']}",
                link=article['link'],
                description=content or article['summary'] or "原文请点击链接查看",
                content=content,
                pubdate=pub_date,
                unique_id=article['link'],
                categories=[article['category']]
            )
        
        return feed.writeString('utf-8')

def main():
    generator = NikkeiRSSGenerator()
    
    # 获取环境变量中的分类
    categories = os.getenv('NIKKEI_CATEGORIES', 'trend').split(',')
    
    if len(categories) == 1:
        rss_content = generator.generate_rss(categories[0].strip())
    else:
        rss_content = generator.generate_multi_category_rss([c.strip() for c in categories])
    
    # 保存到文件
    with open('rss.xml', 'w', encoding='utf-8') as f:
        f.write(rss_content)
    
    print("RSS生成成功！")
    return rss_content

if __name__ == "__main__":
    main()