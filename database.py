# database.py
import pymysql
from pymysql import MySQLError
from typing import Dict, List, Optional, Any
import json

class MySQLDB:
    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306, charset: str = 'utf8mb4'):
        """初始化数据库连接参数"""
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.charset = charset
        self.connection = None

    def __enter__(self):
        """上下文管理器进入时创建连接"""
        try:
            self.connection = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                port=self.port,
                charset=self.charset,
                cursorclass=pymysql.cursors.DictCursor  # 返回字典格式结果
            )
            return self
        except MySQLError as e:
            print(f"数据库连接失败: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出时关闭连接"""
        if self.connection:
            self.connection.close()

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行查询并返回字典格式结果"""
        with self.connection.cursor() as cursor:
            try:
                cursor.execute(query, params or ())
                result = cursor.fetchall()
                return result
            except MySQLError as e:
                print(f"查询执行失败: {e}")
                raise

    def _execute_update(self, query: str, params: tuple = None) -> int:
        """执行插入/更新/删除操作并返回影响行数"""
        with self.connection.cursor() as cursor:
            try:
                cursor.execute(query, params or ())
                self.connection.commit()
                return cursor.rowcount
            except MySQLError as e:
                self.connection.rollback()
                print(f"更新操作失败: {e}")
                raise



    # ------------------------------ 模板表操作 ------------------------------
    def get_template_by_type_key(self, template_type: str, template_key: str, version: str = '1.0') -> Optional[Dict]:
        """根据类型、键名和版本获取模板"""
        query = """
            SELECT template_id, template_type, template_key, content_json, version, is_active, created_at, updated_at
            FROM templates 
            WHERE template_type = %s AND template_key = %s AND version = %s AND is_active = TRUE
        """
        result = self._execute_query(query, (template_type, template_key, version))
        return result[0] if result else None

    def get_active_templates_by_type(self, template_type: str) -> List[Dict]:
        """获取指定类型的所有活跃模板"""
        query = """
            SELECT template_id, template_type, template_key, content_json, version, is_active, created_at, updated_at
            FROM templates 
            WHERE template_type = %s AND is_active = TRUE
        """
        return self._execute_query(query, (template_type,))

    def get_active_mbti_templates(self) -> List[Dict]:
        """获取所有活跃的MBTI模板"""
        query = """
               SELECT template_id, template_type, template_key, content_json, version, is_active, created_at, updated_at
               FROM templates 
               WHERE template_type = 'mbti' AND is_active = TRUE
           """
        return self._execute_query(query)

    def insert_agent_daily_schedule(self, user_id: int, agent_id: int, schedule_json: str) -> Optional[int]:
        """插入智能体日常时间表并返回schedule_id"""
        insert_sql = """
                     INSERT INTO agent_schedules (user_id, agent_id, schedule_json)
                     VALUES (%s, %s, %s) \
                     """
        try:
            self._execute_update(insert_sql, (user_id, agent_id, schedule_json))
            # 获取自增ID
            result = self._execute_query("SELECT LAST_INSERT_ID()")
            return result[0]['LAST_INSERT_ID()'] if result else None
        except MySQLError as e:
            print(f"插入智能体日常时间表失败: {e}")
            return None

    def get_agent_daily_schedules(self, agent_id: int) -> List[Dict]:
        """获取指定智能体的所有日常时间表（按更新时间倒序）"""
        query = """
                SELECT schedule_id, user_id, agent_id, schedule_json, created_at, updated_at
                FROM agent_schedules
                WHERE agent_id = %s
                ORDER BY updated_at DESC \
                """
        return self._execute_query(query, (agent_id,))

    # ------------------------------ 用户表操作 ------------------------------
    def get_user_by_phone(self, phone: str) -> Optional[Dict]:
        """通过手机号获取用户信息"""
        query = """
            SELECT user_id, phone, password_hash, nickname, avatar_url, gender, birthday, signature,
                   region, interests, is_verified, status, last_login_ip, last_login_time,
                   created_at, updated_at
            FROM users 
            WHERE phone = %s
        """
        result = self._execute_query(query, (phone,))
        return result[0] if result else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """通过用户ID获取用户信息"""
        query = """
            SELECT user_id, phone, password_hash, nickname, avatar_url, gender, birthday, signature,
                   region, interests, is_verified, status, last_login_ip, last_login_time,
                   created_at, updated_at
            FROM users 
            WHERE user_id = %s
        """
        result = self._execute_query(query, (user_id,))
        return result[0] if result else None

    # ------------------------------ 智能体表操作 ------------------------------

    def insert_agent(self, user_id: int, agent_name: str, full_json: str) -> Optional[int]:
        """插入智能体并返回自增ID"""
        insert_sql = """
          INSERT INTO agents (user_id, agent_name, full_json)
          VALUES (%s, %s, %s)
          """
        try:
            # 执行插入
            self._execute_update(insert_sql, (user_id, agent_name, full_json))
            # 获取自增ID
            result = self._execute_query("SELECT LAST_INSERT_ID()")
            return result[0]['LAST_INSERT_ID()'] if result else None
        except MySQLError as e:
            print(f"插入智能体失败: {e}")
            return None

    def get_agent(self, agent_id: int) -> List[Dict]:
        """获取智能体"""
        query = """
            SELECT agent_id, user_id, agent_name, full_json, created_at, updated_at
            FROM agents 
            WHERE agent_id = %s  -- 去掉多余的AND
            ORDER BY created_at DESC
        """
        return self._execute_query(query, (agent_id,))

    def get_agents_by_mbti(self, mbti_type: str) -> List[Dict]:
        """通过MBTI类型筛选智能体"""
        query = """
            SELECT agent_id, user_id, template_id, name, age, birthday, worldview, education,
                   family_background, occupation, country_region, mbti_type, psychological_state,
                   ideal, hobbies, voice_desc, skills, knowledge_system, relationship_with_user,
                   status_tags, feature_tags, experience_tags, relationship_tags, avatar_url,
                   is_active, created_at, updated_at
            FROM agents 
            WHERE mbti_type = %s AND is_active = TRUE
        """
        return self._execute_query(query, (mbti_type,))

    # ------------------------------ 智能体生平事件表操作 ------------------------------
    def insert_agent_life_event(self, user_id: int, agent_id: int, event_json: str) -> bool:
        """
        插入智能体生平事件
        返回值：True表示成功，False表示失败
        """
        insert_sql = """
        INSERT INTO agent_life_events (user_id, agent_id, event_json)
        VALUES (%s, %s, %s)
        """
        try:
            # 执行插入，返回影响行数（1表示成功）
            row_count = self._execute_update(insert_sql, (user_id, agent_id, event_json))
            return row_count == 1
        except MySQLError as e:
            print(f"插入智能体生平事件失败: {e}")
            return False

    def get_agent_life_events(self, agent_id: int) -> List[Dict]:
        """获取指定智能体的所有生平事件（按创建时间倒序）"""
        query = """
        SELECT user_id, agent_id, event_json, created_at, updated_at
        FROM agent_life_events
        WHERE agent_id = %s
        ORDER BY created_at DESC
        """
        return self._execute_query(query, (agent_id,))

    # ------------------------------ 智能体目标表操作 ------------------------------
    def insert_agent_goal(self, user_id: int, agent_id: int, goals_json: str) -> Optional[int]:
        """插入智能体目标并返回目标ID"""
        insert_sql = """
        INSERT INTO agent_goals_json (user_id, agent_id, goals_json)
        VALUES (%s, %s, %s)
        """
        try:
            self._execute_update(insert_sql, (user_id, agent_id, goals_json))
            # 获取自增的goal_id
            result = self._execute_query("SELECT LAST_INSERT_ID()")
            return result[0]['LAST_INSERT_ID()'] if result else None
        except MySQLError as e:
            print(f"插入智能体目标失败: {e}")
            return None

    def get_agent_goals(self, agent_id: int) -> List[Dict]:
        """获取指定智能体的所有目标（按创建时间倒序）"""
        query = """
        SELECT goal_id, user_id, agent_id, goals_json, created_at, updated_at
        FROM agent_goals_json
        WHERE agent_id = %s
        ORDER BY created_at DESC
        """
        return self._execute_query(query, (agent_id,))


    # ------------------------------ 智能体事件链表操作 ------------------------------
    def insert_agent_event_chain(self, user_id: int, agent_id: int, chain_json: str) -> Optional[int]:
        """插入智能体事件链并返回chain_id"""
        insert_sql = """
        INSERT INTO agent_event_chains (user_id, agent_id, chain_json)
        VALUES (%s, %s, %s)
        """
        try:
            self._execute_update(insert_sql, (user_id, agent_id, chain_json))
            # 获取自增ID
            result = self._execute_query("SELECT LAST_INSERT_ID()")
            return result[0]['LAST_INSERT_ID()'] if result else None
        except MySQLError as e:
            print(f"插入智能体事件链失败: {e}")
            return None

    def get_agent_event_chains(self, agent_id: int) -> List[Dict]:
        """获取指定智能体的所有事件链（按创建时间倒序）"""
        query = """
        SELECT chain_id, user_id, agent_id, chain_json, created_at, updated_at
        FROM agent_event_chains
        WHERE agent_id = %s
        ORDER BY created_at DESC
        """
        return self._execute_query(query, (agent_id,))
    def get_agent_events_by_stage(self, agent_id: int, stage_name: str) -> List[Dict]:
        """获取智能体特定阶段的事件"""
        query = """
            SELECT agent_id, user_id, stage_name, stage_time_range, event_id, event_type,
                   event_name, event_time, location, characters, cause, process, result,
                   impact, importance, urgency, tags, trigger_conditions, dependencies,
                   is_completed, created_at, updated_at
            FROM agent_event_chain 
            WHERE agent_id = %s AND stage_name = %s 
            ORDER BY importance DESC
        """
        return self._execute_query(query, (agent_id, stage_name))

    def get_uncompleted_events(self, agent_id: int) -> List[Dict]:
        """获取智能体未完成的事件"""
        query = """
            SELECT agent_id, user_id, stage_name, stage_time_range, event_id, event_type,
                   event_name, event_time, location, characters, cause, process, result,
                   impact, importance, urgency, tags, trigger_conditions, dependencies,
                   is_completed, created_at, updated_at
            FROM agent_event_chain 
            WHERE agent_id = %s AND is_completed = FALSE 
            ORDER BY urgency DESC, importance DESC
        """
        return self._execute_query(query, (agent_id,))

    def insert_agent_daily_schedule(self, user_id: int, agent_id: int, schedule_json: str) -> Optional[int]:
        """插入智能体日常时间表并返回schedule_id"""
        insert_sql = """
                     INSERT INTO agent_schedules (user_id, agent_id, schedule_json)
                     VALUES (%s, %s, %s) \
                     """
        try:
            self._execute_update(insert_sql, (user_id, agent_id, schedule_json))
            # 获取自增ID
            result = self._execute_query("SELECT LAST_INSERT_ID()")
            return result[0]['LAST_INSERT_ID()'] if result else None
        except MySQLError as e:
            print(f"插入智能体日常时间表失败: {e}")
            return None

    def get_agent_daily_schedules(self, agent_id: int) -> List[Dict]:
        """获取指定智能体的所有日常时间表（按更新时间倒序）"""
        query = """
                SELECT schedule_id, user_id, agent_id, schedule_json, created_at, updated_at
                FROM agent_schedules
                WHERE agent_id = %s
                ORDER BY updated_at DESC \
                """
        return self._execute_query(query, (agent_id,))

#对话历史记忆表操作
    def insert_dialog_memory(self, user_id: int, agent_id: int, dialog_json: str) -> Optional[int]:
        """插入对话历史记忆并返回memory_id"""
        insert_sql = """
        INSERT INTO agent_dialog_memory (user_id, agent_id, dialog_json)
        VALUES (%s, %s, %s)
        """
        try:
            self._execute_update(insert_sql, (user_id, agent_id, dialog_json))
            result = self._execute_query("SELECT LAST_INSERT_ID()")
            return result[0]['LAST_INSERT_ID()'] if result else None
        except MySQLError as e:
            print(f"插入对话历史记忆失败: {e}")
            return None

    def get_agent_dialog_memories(self, agent_id: int) -> List[Dict]:
        """获取指定智能体的所有对话历史（按时间倒序）"""
        query = """
        SELECT memory_id, user_id, agent_id, dialog_json, created_at, updated_at
        FROM agent_dialog_memory
        WHERE agent_id = %s
        ORDER BY created_at DESC
        """
        return self._execute_query(query, (agent_id,))

    def get_user_agent_dialogs(self, user_id: int, agent_id: int) -> List[Dict]:
        """获取指定用户与智能体的对话历史（按时间正序，即对话发生顺序）"""
        query = """
        SELECT memory_id, dialog_json, created_at
        FROM agent_dialog_memory
        WHERE user_id = %s AND agent_id = %s
        ORDER BY created_at ASC
        """
        return self._execute_query(query, (user_id, agent_id))

    def save_agent_dialog_memory(self, user_id: int, agent_id: int, dialog_data: List[Dict]) -> bool:
        # 检查是否存在历史记录
        check_query = """
          SELECT memory_id 
          FROM agent_dialog_memory 
          WHERE user_id = %s AND agent_id = %s
          LIMIT 1
          """
        update_query = """
          UPDATE agent_dialog_memory 
          SET dialog_json = %s 
          WHERE memory_id = %s
          """
        insert_query = """
          INSERT INTO agent_dialog_memory 
          (user_id, agent_id, dialog_json) 
          VALUES (%s, %s, %s)
          """
        try:
            dialog_json = json.dumps(dialog_data, ensure_ascii=False)
            exists = self._execute_query(check_query, (user_id, agent_id))
            if exists:
                # 更新现有记录
                row_count = self._execute_update(
                    update_query,
                    (dialog_json, exists[0]['memory_id'])
                )
                return row_count > 0
            else:
                # 插入新记录
                row_count = self._execute_update(
                    insert_query,
                    (user_id, agent_id, dialog_json)
                )
                return row_count > 0
        except Exception as e:
            print(f"❌❌ 保存对话记忆失败: {e}")
            return False

# 日常对话记录表操作
    def insert_agent_message(self, user_id: int, agent_id: int, role: str, content: str,
                           issue_id: str, timestamp: str, activity: str, status: str) -> bool:
        """插入单条对话消息"""
        insert_sql = """
        INSERT INTO agent_messages 
        (user_id, agent_id, role, content, issue_id, timestamp, activity, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            self._execute_update(insert_sql, (user_id, agent_id, role, content,
                                            issue_id, timestamp, activity, status))
            return True
        except Exception as e:
            print(f"❌❌ 插入单条消息失败: {e}")
            return False

    def get_agent_dialog_memory(self, user_id: int, agent_id: int) -> List[Dict]:
        query = """
                SELECT role, content, issue_id, timestamp, activity, status
                FROM agent_messages
                WHERE user_id = %s AND agent_id = %s
                ORDER BY timestamp ASC
                """
        try:
            result = self._execute_query(query, (user_id, agent_id))
            if result and result[0].get('dialog_json'):
                return json.loads(result[0]['dialog_json'])
            return []
        except Exception as e:
            print(f"❌❌ 获取对话记忆失败: {e}")
            return []

# 配置数据库连接信息
DB_CONFIG = {
    "host": "101.200.229.113",
    "user": "gongwei",
    "password": "Echo@123456",
    "database": "echo",
    "port": 3306,
    "charset": "utf8mb4"
}


def main():
    # 1. 读取生效的智能体模板（agent_info类型）
    with MySQLDB(**DB_CONFIG) as db:
        # 查询模板表：获取agent_info类型的生成模板
        agent_template = db.get_active_template(
            template_type="agent_info",
            template_key="agent_generation_template"
        )
        if agent_template:
            print("获取到智能体模板：")
            print("模板内容JSON:", agent_template["content_json"])
            print("模板版本:", agent_template["version"])

    # 2. 读取指定智能体详情
    with MySQLDB(**DB_CONFIG) as db:
        agent_id = 1  # 示例智能体ID
        agent = db.get_agent_by_id(agent_id)
        if agent:
            print(f"\n智能体 {agent_id} 详情：")
            print("姓名:", agent["name"])
            print("世界观:", agent["worldview"])
            print("MBTI类型:", agent["mbti_type"])

    # 3. 读取用户的所有智能体
    with MySQLDB(**DB_CONFIG) as db:
        user_id = 100  # 示例用户ID
        user_agents = db.get_agents_by_user(user_id)
        print(f"\n用户 {user_id} 的智能体列表（共{len(user_agents)}个）：")
        for ag in user_agents:
            print(f"- {ag['name']}（ID: {ag['agent_id']}）")

    # 4. 读取智能体的生平事件
    with MySQLDB(**DB_CONFIG) as db:
        agent_id = 1  # 示例智能体ID
        events = db.get_agent_events(agent_id)
        print(f"\n智能体 {agent_id} 的生平事件（共{len(events)}个）：")
        for event in events:
            print(f"{event['year_desc']}（{event['age_at_event']}）：{event['event_description'][:50]}...")
 # 5. 读取所有活跃的MBTI模板
    with MySQLDB(**DB_CONFIG) as db:
        mbti_templates = db.get_active_mbti_templates()
        print(f"\nMBTI 模板列表（共{len(mbti_templates)}个）：")
        for template in mbti_templates:
            print(f"模板键名: {template['template_key']}, 版本: {template['version']}")
            print("内容JSON:", template["content_json"])


if __name__ == "__main__":
    main()
