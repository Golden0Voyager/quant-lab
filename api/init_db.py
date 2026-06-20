"""
数据库初始化脚本
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.app import app
from api.models.database import db


def init_database():
    """初始化数据库"""
    with app.app_context():
        # 创建所有表
        db.create_all()
        print("✅ 数据库表创建成功！")

        # 打印所有表名
        print("\n已创建的表:")
        for table in db.metadata.sorted_tables:
            print(f"  - {table.name}")

if __name__ == '__main__':
    # 配置数据库URI
    if len(sys.argv) > 1:
        database_uri = sys.argv[1]
    else:
        # 默认使用SQLite
        database_uri = 'sqlite:///quant_lab.db'

    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    print(f"📊 初始化数据库: {database_uri}")
    init_database()
