"""手动测试：验证数据库初始化与 sqlite3 连接可用。"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import DATABASE, PRIVATE_DATABASE
from core.database.init import init_private_db, init_database
from core.database.connection import get_connection

# 初始化私有库
init_private_db()

# 初始化数据库（接口兼容，实际已统一为 sqlite3）
if not init_database(DATABASE, PRIVATE_DATABASE):
    print("init_database 失败")
    sys.exit(-1)

# 验证 sqlite3 连接可用
with get_connection(DATABASE, readonly=True) as conn:
    cur = conn.cursor()
    cur.execute("SELECT 1")
    assert cur.fetchone() == (1,), "public 数据库连接异常"
print("数据库连接测试通过")
