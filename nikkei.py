import requests
import feedparser
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime

RSS_URL = "http://cn.nikkei.com/rss.html"

headers = {
    "User-Agent":
    "Mozilla/5.0"
}


def get_article(url):

    try:
        r = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        r.encoding="utf-8"

        soup = BeautifulSoup(
            r.text,
            "lxml"
        )

        # 日经中文正文区域
        article = soup.select_one(
            ".article_body"
        )

        if not article:
            article = soup.select_one(
                ".content"
            )

        if article:
            for x in article.select(
                "script,style"
            ):
                x.decompose()

            return article.get_text(
                "\n",
                strip=True
            )

    except Exception as e:
        print(e)

    return ""


feed = feedparser.parse(
    RSS_URL
)


fg = FeedGenerator()

fg.title(
    "日经中文网全文RSS"
)

fg.link(
    href="https://cn.nikkei.com/"
)

fg.description(
    "日经中文文章全文"
)

fg.language(
    "zh-CN"
)


for item in feed.entries[:15]:

    text = get_article(
        item.link
    )

    if not text:
        continue

    entry = fg.add_entry()

    entry.title(
        item.title
    )

    entry.link(
        href=item.link
    )

    entry.description(
        text
    )


fg.rss_file(
    "nikkei-full.xml"
)