import argparse
import os
import json
import uuid
import re
import requests
import time
from datetime import datetime
from Agent_builder import AgentBuilder
from Event_builder import EventTreeGenerator
from api_handler import ChatFireAPIClient
from daily_loop_tool import run_daily_loop
from event_loop_tool import run_event_loop
from memory import save_conversation_history
from database import MySQLDB

API_KEY = "sk-Jgb98JXxJ0nNfB2vcNoQ0ZZg1B5zYbM1TgsGmc1LOrNPMIPV"


def run_full_pipeline(user_input: str, user_id: int):
    builder = AgentBuilder(api_key=API_KEY, user_id=user_id)
    agent_data = builder.build_agent(user_input)
    if not agent_data:
        print("❌ 智能体构建失败。")
        return None

    formatted_dict = agent_data["智能体信息"]
    agent_goals = agent_data["目标"]
    agent_id = agent_data["agent_id"]
    name = agent_data["agent_name"]
    generator = EventTreeGenerator(agent_name=name, api_key=API_KEY, agent_id=agent_id, user_id=user_id)
    full_event_tree = generator.generate_and_save()

    print("✅初始化完成，智能体角色与事件链构建完毕。")
    return formatted_dict, agent_goals, full_event_tree, agent_id, name
def evaluate_state_change(messages, agent_profile, goals, event_tree):
    client = ChatFireAPIClient(api_key=API_KEY, default_model="gpt-4o")

    # 按 issue_id 分组对话
    conversations = {}
    for msg in messages:
        if "issue_id" in msg:
            issue_id = msg["issue_id"]
            if issue_id not in conversations:
                conversations[issue_id] = []
            conversations[issue_id].append(msg)

    # 构建提示词
    prompt = f"""
请根据以下内容评估事件结束后智能体的状态变化，并按issue_id分组评估：

【智能体设定】
{json.dumps(agent_profile, ensure_ascii=False, indent=2)}

【目标信息】
{json.dumps(goals, ensure_ascii=False, indent=2)}

【事件链】
{json.dumps(event_tree, ensure_ascii=False, indent=2)}

【对话分组】："""

    for issue_id, msgs in conversations.items():
        prompt += f"\nIssue ID: {issue_id}\n"
        for msg in msgs:
            role = msg["role"]
            content = msg["content"]
            prompt += f"{role}: {content}\n"

    prompt += """
输出格式如下：
{
  "心理状态变化": {
    "心情": "+/-整数",
    "心理健康度": "+/-整数",
    "求知欲": "+/-整数",
    "社交能量": "+/-整数"
  },
  "知识储备变化": {
    "增加": ["新知识1", "新知识2"]
  },
  "事件树状态": {
    "事件ID": "事件编号",
    "状态": "完成/失败/跳过"
  }
}

请严格按照以下JSON格式输出，不要包含任何额外文本：
{
  "心理状态变化": {...},
  "知识储备变化": {...},
  "事件树状态": {...}
}
重要：不要使用Markdown代码块，直接输出纯JSON！
"""

    # 创建默认评估结果
    def create_default_evaluation() -> dict:
        return {
            "心理状态变化": {
                "心情": 0,
                "心理健康度": 0,
                "求知欲": 0,
                "社交能量": 0
            },
            "知识储备变化": {
                "增加": []
            },
            "事件树状态": {
                "事件ID": "",
                "状态": "未完成"
            }
        }

    max_retries = 2
    for attempt in range(max_retries):
        try:
            # 调用API
            response = client.call_api([{"role": "user", "content": prompt}], max_tokens=1500)

            if not response or 'choices' not in response or not response['choices']:
                print(f"⚠️ API响应无效 (尝试#{attempt + 1})")
                continue

            content = response["choices"][0]["message"]["content"]
            print(f"📊 状态评估响应 (尝试#{attempt + 1}):\n{content}\n")

            # 尝试提取JSON内容
            try:
                # 尝试直接解析整个内容
                if content.strip().startswith('{'):
                    return json.loads(content)

                # 尝试提取JSON对象
                start_index = content.find('{')
                end_index = content.rfind('}')
                if start_index != -1 and end_index != -1 and end_index > start_index:
                    json_str = content[start_index:end_index + 1]
                    return json.loads(json_str)

                # 尝试解析代码块
                if '```json' in content:
                    start = content.find('```json') + 7
                    end = content.find('```', start)
                    if end == -1:
                        json_str = content[start:]
                    else:
                        json_str = content[start:end]
                    return json.loads(json_str.strip())

                if '```' in content:
                    start = content.find('```') + 3
                    end = content.find('```', start)
                    if end == -1:
                        json_str = content[start:]
                    else:
                        json_str = content[start:end]
                    return json.loads(json_str.strip())

            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败 (尝试#{attempt + 1}): {e}")
                continue

        except requests.exceptions.Timeout:
            print(f"⚠️ API请求超时 (尝试#{attempt + 1})")
            time.sleep(1)
        except requests.exceptions.RequestException as e:
            print(f"⚠️ API请求失败 (尝试#{attempt + 1}): {str(e)}")
            time.sleep(1)
        except Exception as e:
            print(f"⚠️ 未知错误 (尝试#{attempt + 1}): {str(e)}")
            time.sleep(1)

    # 所有重试失败后的处理
    print("❌❌ 所有状态评估尝试失败，使用默认评估")
    return create_default_evaluation()


def state_update(agent_id: int, state_result: dict, formatted_text: str, goals: str, event_tree: str):
    # 创建数据库连接
    DB_CONFIG = {
        "host": "101.200.229.113",
        "user": "gongwei",
        "password": "Echo@123456",
        "database": "echo",
        "port": 3306,
        "charset": "utf8mb4"
    }
    db = MySQLDB(**DB_CONFIG)

    # 更新数据库
    try:
        # 更新智能体信息
        with db as db_conn:
            update_sql = """
                UPDATE agents 
                SET full_json = %s 
                WHERE agent_id = %s
            """
            params = (json.dumps(formatted_text), agent_id)
            db_conn._execute_update(update_sql, params)
            print("✅ 智能体信息已更新到数据库")

        # 更新目标
        with db as db_conn:
            # 获取最新的goal_id
            goals_list = db_conn.get_agent_goals(agent_id)
            if goals_list:
                latest_goal_id = goals_list[0]["goal_id"]
                update_sql = """
                    UPDATE agent_goals_json 
                    SET goals_json = %s 
                    WHERE goal_id = %s
                """
                params = (json.dumps(goals), latest_goal_id)
                db_conn._execute_update(update_sql, params)
                print("✅ 目标已更新到数据库")

        # 更新事件链
        with db as db_conn:
            # 获取最新的chain_id
            chains_list = db_conn.get_agent_event_chains(agent_id)
            if chains_list:
                latest_chain_id = chains_list[0]["chain_id"]
                update_sql = """
                    UPDATE agent_event_chains 
                    SET chain_json = %s 
                    WHERE chain_id = %s
                """
                params = (json.dumps(event_tree), latest_chain_id)
                db_conn._execute_update(update_sql, params)
                print("✅ 事件链已更新到数据库")

    except Exception as e:
        print(f"❌ 数据库更新失败: {e}")

    return {
        "formatted": formatted_text,
        "goals": goals,
        "full_event_tree": event_tree
    }

def select_next_event(full_event_tree, state_result) -> dict:
    """
    根据事件树和状态评估结果选择下一个事件
    """
    # 检查输入是否为列表类型
    if not isinstance(full_event_tree, list):
        print(f"⚠️ 事件树格式错误，期望list但得到{type(full_event_tree)}")
        return None

    # 获取事件树中第一个状态不是"完成"的事件
    for stage in full_event_tree:
        for event in stage.get("事件列表", []):
            if event.get("状态", "未开始") != "完成":
                return event

    print("⚠️ 所有事件已完成，没有下一个事件")
    return None

def get_intro_event(event_tree: list) -> dict:
    # 检查是否是分层结构（包含阶段）
    if isinstance(event_tree[0], dict) and "事件列表" in event_tree[0]:
        # 分层结构：遍历阶段找事件
        for stage in event_tree:
            events = stage.get("事件列表", [])
            for event in events:
                if isinstance(event, dict) and event.get("event_id") == "E001":
                    return event
    else:
        # 平铺结构：直接遍历事件列表
        for event in event_tree:
            if isinstance(event, dict) and event.get("event_id") == "E001":
                return event


def main():
    parser = argparse.ArgumentParser(description="AI 虚拟智能体主程序")
    parser.add_argument('--init', action='store_true', help='初始化主角与事件链')
    parser.add_argument('--event', action='store_true', help='进入事件互动')
    parser.add_argument('--event_id', type=str, help='事件ID')
    parser.add_argument('--daily', action='store_true', help='进入日常互动')
    parser.add_argument('--user_id', type=int, default=1, help='用户ID')
    parser.add_argument('--agent_id', type=int,default=37, help='智能体ID（用于日常互动）')


    args = parser.parse_args()

    DB_CONFIG = {
        "host": "101.200.229.113",
        "user": "gongwei",
        "password": "Echo@123456",
        "database": "echo",
        "port": 3306,
        "charset": "utf8mb4"
    }

    if args.init:
        print("🧠🧠🧠🧠🧠🧠🧠🧠请输入角色设定：")
        user_input = input(">>> ") #修改为从前端接收
        user_id = args.user_id #修改为从前端接收
        formatted_text, goals, tree, agent_id, name = run_full_pipeline(user_input, user_id)

    if args.daily:
        if not args.agent_id:
            print("❌ 请提供智能体ID（使用 --agent_id 参数）")
            return

        print(f"🚀 启动日常互动（agent_id: {args.agent_id}, user_id: {args.user_id}）")

        # 创建数据库连接
        db = MySQLDB(**DB_CONFIG)

        # 获取智能体信息
        with db as db_conn:
            agent_info = db_conn.get_agent_by_id(args.agent_id)
            if agent_info:
                try:
                    formatted_dict = json.loads(agent_info['full_json'])
                    print(f"✅ 从数据库加载智能体信息成功（agent_id: {args.agent_id}）")
                except json.JSONDecodeError as e:
                    print(f"❌ 智能体信息JSON解析失败: {e}")
                    return
            else:
                print(f"⚠️ 数据库中未找到智能体信息（agent_id: {args.agent_id}）")
                return

        # 获取目标
        goals = ""
        with db as db_conn:
            goals_data = db_conn.get_agent_goals(args.agent_id)
            if goals_data:
                try:
                    goals = json.loads(goals_data[0]['goals_json'])
                    print(f"✅ 从数据库加载目标成功（agent_id: {args.agent_id}）")
                except json.JSONDecodeError as e:
                    print(f"❌ 目标JSON解析失败: {e}")
            else:
                print(f"⚠️ 数据库中未找到目标（agent_id: {args.agent_id}）")

        # 获取事件树
        event_tree = []
        with db as db_conn:
            events_data = db_conn.get_agent_event_chains(args.agent_id)
            if events_data:
                try:
                    event_tree = json.loads(events_data[0]['chain_json'])
                    print(f"✅ 从数据库加载事件链成功（agent_id: {args.agent_id}）")
                except json.JSONDecodeError as e:
                    print(f"❌ 事件链JSON解析失败: {e}")
            else:
                print(f"⚠️ 数据库中未找到事件链（agent_id: {args.agent_id}）")

        # 运行日常互动
        messages, name = run_daily_loop(formatted_dict, goals, event_tree, args.agent_id, args.user_id)

        # 状态评估
        if messages:
            print("📊 开始状态评估...")
            state_result = evaluate_state_change(messages, formatted_dict, goals, event_tree)

            # 状态更新
            print("🔄 更新智能体状态...")
            state_update(args.agent_id, state_result, formatted_dict, goals, event_tree)

            # 推进到下一事件
            print("⏭️ 推进到下一事件...")
            next_event = select_next_event(event_tree)
            if next_event:
                print(f"🎭 执行事件: {next_event.get('event_name', '未命名事件')}")
                temp_tree = [{
                    "阶段": "临时阶段",
                    "时间范围": "当前",
                    "事件列表": [next_event]
                }]
                event_messages, _ = run_event_loop(formatted_dict, goals, temp_tree)
                if event_messages:
                    event_state_result = evaluate_state_change(event_messages, formatted_dict, goals, event_tree)
                    state_update(args.agent_id, event_state_result, formatted_dict, goals, event_tree)
            else:
                print("🏁 所有事件已完成")

    elif args.event:
                messages = run_event_loop(
                    user_id, agent_id, args.event_id, user_input
                )
                print(f"📊 评估智能体状态变化...")
                state_result = evaluate_state_change(messages, formatted_text, goals, tree)
                state_update(agent_id, state_result, formatted_text, goals, tree)
    else:
        print("⚠️ 缺少必要参数：--init | --daily | --event | --reset")


if __name__ == "__main__":
    main()
