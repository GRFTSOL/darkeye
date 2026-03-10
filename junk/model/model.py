from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class Work:
    """作品模型类

    """
    # 必填字段
    serial_number: str

    # 可选字段
    work_id: Optional[int] = None
    director: Optional[str] = None
    story: Optional[str] = None
    release_date: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    cn_title: Optional[str] = None
    jp_title: Optional[str] = None
    cn_story: Optional[str] = None
    jp_story: Optional[str] = None
    actress_ids: List[int] = field(default_factory=list)
    actor_ids: List[int] = field(default_factory=list)
    tag_ids: List[int] = field(default_factory=list)
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    is_deleted: int = 0

    # 聚合字段 (通过番号前缀或其他逻辑计算得出)
    maker_id: Optional[int] = None
    maker_name: Optional[str] = None

    def __post_init__(self):
        """初始化后处理"""
        # 如果没有提供创建和更新时间，使用当前时间
        if not self.create_time:
            self.create_time = datetime.now()
        if not self.update_time:
            self.update_time = datetime.now()

    @property
    def is_active(self) -> bool:
        """是否未被删除"""
        return self.is_deleted == 0

    def delete(self):
        """标记为删除"""
        self.is_deleted = 1
        self.update_time = datetime.now()

    def update(self, **kwargs):
        """更新属性

        Args:
            **kwargs: 要更新的属性及其值
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.update_time = datetime.now()

    def to_dict(self) -> dict:
        """转换为字典形式"""
        return {
            "work_id": self.work_id,
            "serial_number": self.serial_number,
            "director": self.director,
            "story": self.story,
            "release_date": self.release_date,
            "image_url": self.image_url,
            "video_url": self.video_url,
            "cn_title": self.cn_title,
            "jp_title": self.jp_title,
            "cn_story": self.cn_story,
            "jp_story": self.jp_story,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
            "is_deleted": self.is_deleted,
            "actress_ids": self.actress_ids,
            "actor_ids": self.actor_ids,
            "tag_ids": self.tag_ids,
            "maker_id": self.maker_id,
            "maker_name": self.maker_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Work":
        """从字典创建实例

        Args:
            data: 字典数据

        Returns:
            Work: 作品实例
        """
        # 处理时间字段
        if "create_time" in data and data["create_time"]:
            data["create_time"] = datetime.fromisoformat(data["create_time"])
        if "update_time" in data and data["update_time"]:
            data["update_time"] = datetime.fromisoformat(data["update_time"])

        return cls(**data)

    def __str__(self) -> str:
        """字符串表示"""
        return f"Work({self.serial_number}: {self.cn_title or self.jp_title})"




@dataclass
class Actress:
    """女优模型，对应表 actress"""

    actress_id: Optional[int] = None
    birthday: Optional[str] = None
    height: Optional[int] = None
    bust: Optional[int] = None
    waist: Optional[int] = None
    hip: Optional[int] = None
    cup: Optional[str] = None
    debut_date: Optional[str] = None
    need_update: int = 1
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    image_urlA: Optional[str] = None
    image_urlB: Optional[str] = None


    # 聚合字段 (来源于 actress_name 表中 name_type=1 的记录)
    cn_name: Optional[str] = None
    jp_name: Optional[str] = None
    en_name: Optional[str] = None
    kana_name: Optional[str] = None

    def __post_init__(self):
        if not self.create_time:
            self.create_time = datetime.now()
        if not self.update_time:
            self.update_time = datetime.now()

    def to_dict(self) -> dict:
        return {
            "actress_id": self.actress_id,
            "birthday": self.birthday,
            "height": self.height,
            "bust": self.bust,
            "waist": self.waist,
            "hip": self.hip,
            "cup": self.cup,
            "debut_date": self.debut_date,
            "need_update": self.need_update,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
            "image_urlA": self.image_urlA,
            "image_urlB": self.image_urlB,
            "cn_name": self.cn_name,
            "jp_name": self.jp_name,
            "en_name":self.en_name,
            "kana_name":self.kana_name
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Actress":
        if "create_time" in data and data["create_time"]:
            data["create_time"] = datetime.fromisoformat(data["create_time"])
        if "update_time" in data and data["update_time"]:
            data["update_time"] = datetime.fromisoformat(data["update_time"])
        return cls(**data)


@dataclass
class ActressName:
    """女优姓名模型，对应表 actress_name,用于处理复杂的别名"""

    actress_name_id: Optional[int] = None
    actress_id: Optional[int] = None
    name_type: int = 1  # 1=主名, 0=非主名
    cn: Optional[str] = None
    jp: Optional[str] = None
    en: Optional[str] = None
    kana: Optional[str] = None
    redirect_actress_name_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "actress_name_id": self.actress_name_id,
            "actress_id": self.actress_id,
            "name_type": self.name_type,
            "cn": self.cn,
            "jp": self.jp,
            "en": self.en,
            "kana": self.kana,
            "redirect_actress_name_id": self.redirect_actress_name_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActressName":
        return cls(**data)


@dataclass
class WorkActressRelation:
    """作品-女优关系模型，对应表 work_actress_relation。

    表示某部作品中某位女优的出演信息，除关联 work_id/actress_id 外，
    可携带角色（job）、年龄段（age）、人设（married）、状态（state）等属性。
    """

    work_id: Optional[int] = None
    actress_id: Optional[int] = None
    work_actress_relation_id: Optional[int] = None
    job: Optional[str] = None   # 角色/职业，如职员、上司
    age: Optional[str] = None   # 年龄段，如年轻
    married: Optional[str] = None  # 人设，如人妻、女友
    state: Optional[str] = None   # 状态，如主动

    def to_dict(self) -> dict:
        return {
            "work_actress_relation_id": self.work_actress_relation_id,
            "work_id": self.work_id,
            "actress_id": self.actress_id,
            "job": self.job,
            "age": self.age,
            "married": self.married,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkActressRelation":
        return cls(**data)


@dataclass
class Actor:
    """男优模型，对应表 actor"""

    actor_id: Optional[int] = None
    birthday: Optional[str] = None
    height: Optional[int] = None
    handsome: Optional[int] = None
    fat: Optional[int] = None
    need_update: int = 1
    create_time: Optional[datetime] = None

    def __post_init__(self):
        if not self.create_time:
            self.create_time = datetime.now()

    def to_dict(self) -> dict:
        return {
            "actor_id": self.actor_id,
            "birthday": self.birthday,
            "height": self.height,
            "handsome": self.handsome,
            "fat": self.fat,
            "need_update": self.need_update,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Actor":
        if "create_time" in data and data["create_time"]:
            data["create_time"] = datetime.fromisoformat(data["create_time"])
        return cls(**data)


@dataclass
class Tag:
    """标签模型，对应表 tag"""

    tag_name: str
    tag_id: Optional[int] = None
    tag_type_id: Optional[int] = None
    color: str = "#cccccc"
    redirect_tag_id: Optional[int] = None
    detail: Optional[str] = None
    group_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "tag_id": self.tag_id,
            "tag_name": self.tag_name,
            "tag_type_id": self.tag_type_id,
            "color": self.color,
            "redirect_tag_id": self.redirect_tag_id,
            "detail": self.detail,
            "group_id": self.group_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Tag":
        return cls(**data)
