import sqlite3
import os
from langchain_core.tools import tool

# 数据库配置
DB_NAME = "film_archive.sqlite3"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_NAME)


class FilmArchiveDB:
    """
    胶片摄影档案关系型数据库管理类
    """
    
    def __init__(self):
        """初始化数据库连接"""
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_table()
    
    def _connect(self):
        """连接到SQLite数据库"""
        try:
            self.conn = sqlite3.connect(DB_PATH)
            self.cursor = self.conn.cursor()
            print(f"[数据库] 成功连接到 {DB_PATH}")
        except sqlite3.Error as e:
            print(f"[数据库] 连接失败: {e}")
    
    def _create_table(self):
        """创建照片信息表"""
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS photos (
                idx INTEGER PRIMARY KEY AUTOINCREMENT,
                照片路径 TEXT UNIQUE NOT NULL,
                拍摄场景 TEXT,
                拍摄风格 TEXT,
                胶片特征 TEXT
            );
            """
            self.cursor.execute(create_table_sql)
            self.conn.commit()
            print("[数据库] 照片信息表创建成功")
        except sqlite3.Error as e:
            print(f"[数据库] 创建表失败: {e}")
    
    def insert_photo_info(self, photo_path, scene, style, film_features):
        """插入或更新照片信息"""
        try:
            # 检查照片是否已经存在
            existing_photo = self.get_photo_info_by_path(photo_path)
            
            if existing_photo:
                # 照片已存在，执行更新操作
                update_sql = """
                UPDATE photos 
                SET 拍摄场景 = ?, 拍摄风格 = ?, 胶片特征 = ?
                WHERE 照片路径 = ?;
                """
                self.cursor.execute(update_sql, (scene, style, film_features, photo_path))
                self.conn.commit()
                print(f"[数据库] 成功更新照片信息: {photo_path}")
                return True
            else:
                # 照片不存在，执行插入操作
                insert_sql = """
                INSERT INTO photos (照片路径, 拍摄场景, 拍摄风格, 胶片特征)
                VALUES (?, ?, ?, ?);
                """
                self.cursor.execute(insert_sql, (photo_path, scene, style, film_features))
                self.conn.commit()
                print(f"[数据库] 成功插入照片信息: {photo_path}")
                return True
        except sqlite3.Error as e:
            print(f"[数据库] 操作照片信息失败: {e}")
            return False

    def get_photo_info_by_path(self, photo_path):
        """根据照片路径查询照片信息"""
        try:
            select_sql = """
            SELECT 拍摄场景, 拍摄风格, 胶片特征
            FROM photos
            WHERE 照片路径 = ?;
            """
            self.cursor.execute(select_sql, (photo_path,))
            result = self.cursor.fetchone()
            if result:
                return {
                    "拍摄场景": result[0],
                    "拍摄风格": result[1],
                    "胶片特征": result[2]
                }
            else:
                return None
        except sqlite3.Error as e:
            print(f"[数据库] 查询照片信息失败: {e}")
            return None
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            print("[数据库] 连接已关闭")


# 初始化数据库实例
db = FilmArchiveDB()


@tool
def get_photo_metadata(photo_path: str) -> str:
    """
    从关系型数据库中获取照片的元数据信息。当需要获取照片的拍摄场景、拍摄风格或胶片特征等结构化信息时使用此工具。
    
    Args:
        :param photo_path: 照片的完整路径
        
    Returns:
        返回照片的拍摄场景、拍摄风格和胶片特征信息。如果未找到对应照片，返回未找到的提示信息。
    """
    print(f"\n正在查询照片 {photo_path} 的元数据...")
    result = db.get_photo_info_by_path(photo_path)
    
    if result:
        # 格式化返回结果
        formatted_result = []
        formatted_result.append(f"照片路径: {photo_path}")
        formatted_result.append(f"拍摄场景: {result['拍摄场景']}")
        formatted_result.append(f"拍摄风格: {result['拍摄风格']}")
        formatted_result.append(f"胶片特征: {result['胶片特征']}")
        return "\n".join(formatted_result)
    else:
        return f"未找到照片 {photo_path} 的元数据信息"


# 示例用法
if __name__ == "__main__":
    # 初始化数据库
    film_db = FilmArchiveDB()
    
    # 插入示例数据
    film_db.insert_photo_info(
        photo_path="/Users/junhong/PycharmProjects/HelloLangChain/resources/img/Fruit1.jpg",
        scene="水果静物",
        style="写实主义",
        film_features="柯达彩色胶片"
    )
    
    film_db.insert_photo_info(
        photo_path="/Users/junhong/PycharmProjects/HelloLangChain/resources/img/Fruit2.jpg",
        scene="水果静物",
        style="抽象主义",
        film_features="富士彩色胶片"
    )
    
    # 查询示例数据
    result = film_db.get_photo_info_by_path(
        "/Users/junhong/PycharmProjects/HelloLangChain/resources/img/Fruit1.jpg"
    )
    print(result)
    
    # 关闭连接
    film_db.close()