from dataclasses import dataclass, field


@dataclass
class CrawledWorkData:
    '''专门的爬取数据类，用于存储从网站爬取的作品数据，是聚合后的作品数据'''
    serial_number: str
    director: str
    release_date: str
    runtime: int

    cn_title: str
    jp_title: str
    cn_story: str
    jp_story: str

    maker: str
    series: str
    label: str

    # 关联数据（纯数据，非数据库ID）
    tag_list: list[str]        # ["TagA", "TagB"]
    actress_list: list[str]   # ["ActressA"]
    actor_list: list[str]      # ["ActorB"]
    cover_url_list: list[str] #["https://example.com/cover.jpg"]
    