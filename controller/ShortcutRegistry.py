
import json,logging,os
from config import USER_SHORTCUT_PATH

class ShortcutRegistry:
    '''
    快捷键注册中心，单例模式，长周期
    功能:
    - 加载和保存用户自定义的快捷键配置
    - 提供默认快捷键配置
    - 支持添加、删除、修改快捷键
    - 支持查询快捷键绑定的操作
    '''
    _instance = None  # 存储单例引用

    def __new__(cls, *args, **kwargs):
        """使用 __new__ 确保只创建一个实例"""
        if not cls._instance:
            cls._instance = super(ShortcutRegistry, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance


    def __init__(self, config_path=USER_SHORTCUT_PATH):
        """确保初始化逻辑只运行一次"""
        if self._initialized:
            return
        logging.info("-------------------快捷键注册----------------------")
        self.config_path = str(config_path)
        logging.info(f"{self.config_path}")
        # 默认配置表：ID -> {名称, 默认键}
        self.defaults = {
            "add_masturbation_record": {"name": "添加撸管记录", "key": "M"},
            "add_quick_work": {"name": "快速添加番号", "key": "W"},
            "add_makelove_record": {"name": "添加做爱记录", "key": "L"},
            "add_sexual_rousal_record": {"name": "添加晨勃记录", "key": "A"},
            "open_help": {"name": "打开文档", "key": "H"},
            "search": {"name": "搜索", "key": "Ctrl+F"},
            "capture": {"name": "部分截图", "key": "C"},
            "allcapture": {"name": "全软件截图", "key": "Shift+C"},

        }
        self.user_shortcuts = self.load_config()
        self.actions_map={}
        self._initialized = True

    def load_config(self):
        """加载本地 JSON；不存在或无效则返回空 dict 并打日志"""
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            logging.warning(
                "加载快捷键配置失败，将使用空配置: %s (%s)",
                self.config_path,
                e,
            )
            return {}
        if not isinstance(data, dict):
            logging.warning(
                "快捷键配置根节点须为 JSON 对象，实际为 %s，将使用空配置: %s",
                type(data).__name__,
                self.config_path,
            )
            return {}
        return data

    def save_config(self):
        """保存当前用户设置到本地"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.user_shortcuts, f, indent=4, ensure_ascii=False)

    def get_shortcut(self, action_id):
        """获取快捷键：优先用户自定义，其次默认值"""
        return self.user_shortcuts.get(action_id, self.defaults[action_id]["key"])

    def update_shortcut(self, action_id, new_key_str):
        """更新并保存"""
        self.user_shortcuts[action_id] = new_key_str
        self.save_config()

    def reset_to_default(self, action_id):
        """恢复单个默认值"""
        if action_id in self.user_shortcuts:
            del self.user_shortcuts[action_id]
            self.save_config()


