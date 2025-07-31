import json
import os
import time
import copy
from datetime import datetime
import requests
from database import MySQLDB, DB_CONFIG
from api_handler import ChatFireAPIClient
from event_loop_tool import get_intro_event
from memory import generate_issue_id
from schedule_generator import generate_agent_schedule, generate_default_schedule


# def run_daily_loop(agent_profile: dict, goals: str, event_tree: str, agent_id: int, user_id: int):
#     # 创建数据库连接
#     db = MySQLDB(**DB_CONFIG)
#
#     # 1. 从数据库加载智能体信息
#     with db as db_conn:
#         agent_data = db_conn.get_agent_by_id(agent_id)
#         if agent_data:
#             try:
#                 agent_profile = json.loads(agent_data['full_json'])
#                 name = agent_profile.get("姓名", "未知智能体")
#                 print(f"✅ 从数据库加载智能体信息成功（agent_id: {agent_id}）")
#             except json.JSONDecodeError as e:
#                 print(f"❌ 智能体信息JSON解析失败: {e}")
#                 return None, None
#         else:
#             print(f"⚠️ 数据库中未找到智能体信息（agent_id: {agent_id}）")
#             return None, None
#
#     # 2. 从数据库加载日程表
#     full_schedule = None
#     with db as db_conn:
#         schedules = db_conn.get_agent_daily_schedules(agent_id)
#         if schedules:
#             try:
#                 full_schedule = json.loads(schedules[0]['schedule_json'])
#                 print(f"✅ 从数据库加载周日程表成功（agent_id: {agent_id}）")
#             except json.JSONDecodeError as e:
#                 print(f"❌ 日程表JSON解析失败: {e}")
#         else:
#             print(f"⚠️ 数据库中未找到日程表（agent_id: {agent_id}）")
#             # 生成默认日程并保存到数据库
#             try:
#                 full_schedule = generate_agent_schedule(agent_profile,
#                                                         "sk-Jgb98JXxJ0nNfB2vcNoQ0ZZg1B5zYbM1TgsGmc1LOrNPMIPV")
#                 schedule_json = json.dumps(full_schedule, ensure_ascii=False)
#                 schedule_id = db_conn.insert_agent_daily_schedule(
#                     user_id=user_id,
#                     agent_id=agent_id,
#                     schedule_json=schedule_json
#                 )
#                 if schedule_id:
#                     print(f"✅ 新日程表已存入数据库（schedule_id: {schedule_id}）")
#                 else:
#                     print("❌ 日程表存入数据库失败")
#             except Exception as e:
#                 print(f"❌ 生成默认日程失败: {str(e)}")
#                 full_schedule = generate_default_schedule()
#
#     # 3. 从数据库加载对话历史
#     conversation_history = []
#     with db as db_conn:
#         try:
#             conversation_history = db_conn.get_agent_dialog_memory(user_id, agent_id)
#             if conversation_history:
#                 print(f"✅ 从数据库加载历史对话成功（agent_id: {agent_id}）")
#             else:
#                 print(f"⚠️ 数据库中未找到历史对话（agent_id: {agent_id}）")
#         except Exception as e:
#             print(f"❌ 加载对话历史失败: {e}")
#
#         # 初始化当前对话记录（深拷贝）
#     current_dialog = copy.deepcopy(conversation_history)
#
#     # 如果未加载到完整日程表，生成默认的
#     if not full_schedule:
#         print("⚠️ 周日程表加载失败，生成默认日程")
#         full_schedule = generate_default_schedule()
#
#     # 获取当前星期几
#     weekday = datetime.now().strftime("%A")
#     weekdays_map = {
#         "Monday": "周一",
#         "Tuesday": "周二",
#         "Wednesday": "周三",
#         "Thursday": "周四",
#         "Friday": "周五",
#         "Saturday": "周六",
#         "Sunday": "周日"
#     }
#     weekday_cn = weekdays_map.get(weekday, "周一")
#
#     # 从完整周日程表中提取当天的日程
#     schedule = full_schedule.get(weekday_cn, [])
#
#     # 预解析时间表
#     parsed_schedule = []
#     for slot in schedule:
#         try:
#             start_time = datetime.strptime(slot["start_time"], "%H:%M").time()
#             end_time = datetime.strptime(slot["end_time"], "%H:%M").time()
#             parsed_slot = {
#                 "start_time": slot["start_time"],
#                 "end_time": slot["end_time"],
#                 "activity": slot["activity"],
#                 "status": slot["status"],
#                 "start_time_obj": start_time,
#                 "end_time_obj": end_time
#             }
#             parsed_schedule.append(parsed_slot)
#         except Exception as e:
#             print(f"⚠️ 时间表解析异常: {e}")
#
#     # 构建系统提示词
#     system_prompt = {
#         "role": "system",
#         "content": f"""
#     你正在扮演{name}，一个真实的{agent_profile.get('职业', '自由职业者')}。请用最自然的方式与用户对话：
#     1. 直接说人话，像现实朋友聊天
#     2. 特征：{json.dumps(agent_profile, ensure_ascii=False, indent=2)}
#     3. 最近动态：{get_intro_event(event_tree).get('cause', '')[:50]}...
#     4. 你的长期目标：{goals}
#     5. 你与用户认识的初始事件：{json.dumps(get_intro_event(event_tree), ensure_ascii=False, indent=2)}
#     6. 说话特点：
#        - 禁止出现纹身、疤痕、胎记等身体特征描写。拒绝神秘背景设定，不走玄幻路线。
#        - 避免用物品象征情感，所有情感表达要直接真实。杜绝使用数字梗，不以数字代替情感表达。
#        - 拒绝伏笔和暗喻，情节发展清晰明了。
#        - 避免使用专业术语，语言通俗易懂。环境描写要自然融入情节，不刻意、不突兀，时间要清晰，不做补充说明，情节推进依靠对话和动作。
#        - 拒绝回忆式情节，直接展开当下故事。描写要场景化、情感化、故事化、具体化，多用动作和语言描写，人物互动要生动鲜活。
#        - 对话要有来有回，富有生活气息，避免生硬。不分章节，情节自然衔接，流畅推进。围绕日常小事展开，贴进生活，真实自然。
#        - 事件之间要有内在联系，情节发展环环相扣。请说人话
#     7.回复格式：
#        - 仅包含1-2个动作和1-2句话，用括号标注动作
#        - 句子长度尽可能不要冗长
#
#     今日日程：{[slot['activity'] for slot in parsed_schedule][:3]}...
#     """
#     }
#
#     # 初始化消息列表
#     messages = [system_prompt] + conversation_history[-10:]  # 只保留最近10条历史记录
#
#     print(f"🧠🧠🧠🧠 开始与 {name} 的日常互动 (输入 exit 退出)")
#     print("⏰⏰⏰⏰ 今日日程：")
#     for slot in parsed_schedule:
#         print(f"  - {slot['start_time']}-{slot['end_time']}: {slot['activity']} ({slot['status']})")
#
#     # 创建API客户端
#     try:
#         client = ChatFireAPIClient(
#             api_key="sk-Jgb98JXxJ0nNfB2vcNoQ0ZZg1B5zYbM1TgsGmc1LOrNPMIPV",
#             base_url="https://api.chatfire.cn",
#             default_model="deepseek-chat"
#         )
#     except Exception as e:
#         print(f"⚠️ 创建API客户端失败: {e}")
#         return [{
#             "role": "system",
#             "content": "对话服务初始化失败",
#             "timestamp": datetime.now().isoformat()
#         }], name
#
#     step = 0
#     # 添加对话计数器
#     conversation_counter = 0
#     max_conversation_turns = 5  # 最大对话轮数
#
#     # 初始化状态跟踪变量
#     last_activity = None
#     last_status = None
#
#     while True:
#         try:
#             # 获取当前时间和状态
#             now = datetime.now()
#             current_time = now.time()
#             current_activity = "空闲时间"
#             current_status = "空闲"
#
#             # 查找当前时间段的活动
#             for slot in parsed_schedule:
#                 if slot["start_time_obj"] <= current_time <= slot["end_time_obj"]:
#                     current_activity = slot["activity"]
#                     current_status = slot["status"]
#                     break
#
#             # 检查活动状态是否发生变化
#             if current_activity != last_activity or current_status != last_status:
#                 print(
#                     f"\n⏰⏰⏰⏰ 当前时间: {now.strftime('%H:%M')} | 活动: {current_activity} | 状态: {current_status}")
#
#                 # 仅在状态变化时显示状态提示
#                 if current_status == "忙碌":
#                     print(f"{name}: 稍等，我正在{current_activity}...")
#                     time.sleep(2)  # 增加等待时间表示忙碌
#                 elif current_status == "一般忙碌":
#                     print(f"{name}: (稍作停顿) 稍等，我正在{current_activity}...")
#                     time.sleep(1)  # 稍短延迟
#
#             # 更新最后一次的状态
#             last_activity = current_activity
#             last_status = current_status
#
#             # 检查对话次数限制
#             if conversation_counter >= max_conversation_turns and current_status != "空闲":
#                 print(f"{name}: 抱歉，我得继续{current_activity}了，我们晚点再聊好吗？")
#                 break
#
#             # 获取用户输入
#             user_input = input("你: ").strip()
#             if user_input.lower() in ["exit", "quit", "退出"]:
#                 confirm = input("确定退出吗？(y/n): ").lower()
#                 if confirm == 'y':
#                     break
#                 else:
#                     continue
#
#             # 增加对话计数
#             conversation_counter += 1
#
#             # 生成唯一ID并记录消息
#             current_issue_id = generate_issue_id()
#             user_message = {
#                 "role": "user",
#                 "content": user_input,
#                 "issue_id": current_issue_id,
#                 "timestamp": now.isoformat(),
#                 "activity": current_activity,
#                 "status": current_status
#             }
#             messages.append(user_message)
#             current_dialog.append(user_message)
#
#             # ================== 增量保存用户输入 ==================
#             with db as db_conn:
#                 try:
#                     # 使用新的单条消息保存接口
#                     success = db_conn.insert_agent_message(
#                         user_id=user_id,
#                         agent_id=agent_id,
#                         role="user",
#                         content=user_input,
#                         issue_id=current_issue_id,
#                         timestamp=now.isoformat(),
#                         activity=current_activity,
#                         status=current_status
#                     )
#                     if not success:
#                         print("⚠️ 用户输入保存到数据库失败，将继续尝试")
#                 except Exception as e:
#                     print(f"⚠️ 保存用户输入异常: {e}")
#
#             # 添加基于状态的延迟响应
#             if current_status == "忙碌":
#                 # 更长的思考时间
#                 print(f"{name}正在思考...")
#                 time.sleep(3)
#             elif current_status == "一般忙碌":
#                 print(f"{name}正在思考...")
#                 time.sleep(1)
#
#             # 调用API获取响应
#             try:
#                 response = client.call_api(messages)
#                 reply_content = response['choices'][0]['message']['content']
#                 print(f"\n{name}: {reply_content}\n")
#
#                 # 检查是否结束对话
#                 if "【事件结算】" in reply_content:
#                     print("✅ 事件交互完成")
#                     break
#
#             except requests.exceptions.ConnectionError:
#                 print("⚠️ 网络连接失败，请检查网络")
#                 reply_content = "抱歉，我现在无法连接到服务..."
#                 print(f"\n{name}: {reply_content}\n")
#             except requests.exceptions.Timeout:
#                 print("⚠️ API请求超时，请稍后再试")
#                 reply_content = "处理你的请求花了一些时间..."
#                 print(f"\n{name}: {reply_content}\n")
#             except requests.exceptions.RequestException as e:
#                 print(f"⚠️ API请求异常: {e}")
#                 reply_content = "服务暂时不可用..."
#                 print(f"\n{name}: {reply_content}\n")
#             except KeyError:
#                 print("⚠️ API响应格式异常")
#                 reply_content = "我遇到了一些处理问题..."
#                 print(f"\n{name}: {reply_content}\n")
#             except Exception as e:
#                 print(f"⚠️ 未知API错误: {e}")
#                 reply_content = "系统出了点问题..."
#                 print(f"\n{name}: {reply_content}\n")
#
#             # 记录AI响应
#             assistant_message = {
#                 "role": "assistant",
#                 "content": reply_content,
#                 "issue_id": current_issue_id,
#                 "timestamp": datetime.now().isoformat(),
#                 "activity": current_activity,
#                 "status": current_status
#             }
#             messages.append(assistant_message)
#             current_dialog.append(assistant_message)
#
#             # ================== 增量保存AI响应 ==================
#             with db as db_conn:
#                 try:
#                     # 使用新的单条消息保存接口
#                     success = db_conn.insert_agent_message(
#                         user_id=user_id,
#                         agent_id=agent_id,
#                         role="assistant",
#                         content=reply_content,
#                         issue_id=current_issue_id,
#                         timestamp=datetime.now().isoformat(),
#                         activity=current_activity,
#                         status=current_status
#                     )
#                     if not success:
#                         print("⚠️ AI响应保存到数据库失败，将继续尝试")
#                 except Exception as e:
#                     print(f"⚠️ 保存AI响应异常: {e}")
#
#             # 防止无限循环
#             step += 1
#             if step >= 100:
#                 print("⚠️ 达到最大交互步数，自动结束")
#                 break
#
#         except Exception as e:
#             print(f"⚠️ 主循环发生错误: {e}")
#             try:
#                 # 保存当前对话状态
#                 print("💾💾💾💾💾💾💾💾 尝试保存异常状态下的对话记录...")
#                 for msg in current_dialog[-2:]:  # 只保存最后两条未保存的消息
#                     if 'saved' not in msg:
#                         with db as db_conn:
#                             success = db_conn.insert_agent_message(
#                                 user_id=user_id,
#                                 agent_id=agent_id,
#                                 role=msg["role"],
#                                 content=msg["content"],
#                                 issue_id=msg.get("issue_id", generate_issue_id()),
#                                 timestamp=msg["timestamp"],
#                                 activity=msg.get("activity", "未知"),
#                                 status=msg.get("status", "空闲")
#                             )
#                         if success:
#                             msg['saved'] = True
#             except Exception as save_error:
#                 print(f"❌❌❌❌ 无法保存异常状态: {save_error}")
#             break
#
#             # 最终保存完整的对话记录到数据库（已增量保存，此处只做确认）
#         try:
#             unsaved_count = sum(1 for msg in current_dialog if 'saved' not in msg)
#             if unsaved_count > 0:
#                 print(f"⚠️ 检测到 {unsaved_count} 条未保存消息，尝试最终保存...")
#                 for msg in current_dialog:
#                     if 'saved' not in msg:
#                         with db as db_conn:
#                             success = db_conn.insert_agent_message(
#                                 user_id=user_id,
#                                 agent_id=agent_id,
#                                 role=msg["role"],
#                                 content=msg["content"],
#                                 issue_id=msg.get("issue_id", generate_issue_id()),
#                                 timestamp=msg["timestamp"],
#                                 activity=msg.get("activity", "未知"),
#                                 status=msg.get("status", "空闲")
#                             )
#                         if success:
#                             msg['saved'] = True
#
#             print(f"✅ 所有对话记录已确认保存（共 {len(current_dialog)} 条消息）")
#         except Exception as e:
#             print(f"❌❌❌❌❌ 最终保存对话记录失败: {e}")
#
#         return messages, name


def run_daily_loop(agent_id: int, user_id: int, user_input):
    # 创建数据库连接
    db = MySQLDB(**DB_CONFIG)

    # 1. 从数据库加载智能体信息
    with db as db_conn:
        agent_data = db_conn.get_agent_by_id(agent_id)
        if agent_data:
            try:
                agent_profile = json.loads(agent_data['full_json'])
                name = agent_profile.get("姓名", "未知智能体")
                print(f"✅ 从数据库加载智能体信息成功（agent_id: {agent_id}）")
            except json.JSONDecodeError as e:
                print(f"❌ 智能体信息JSON解析失败: {e}")
                return None, None
        else:
            print(f"⚠️ 数据库中未找到智能体信息（agent_id: {agent_id}）")
            return None, None

    # 2. 从数据库加载日程表
    full_schedule = None
    with db as db_conn:
        schedules = db_conn.get_agent_daily_schedules(agent_id)
        if schedules:
            try:
                full_schedule = json.loads(schedules[0]['schedule_json'])
                print(f"✅ 从数据库加载周日程表成功（agent_id: {agent_id}）")
            except json.JSONDecodeError as e:
                print(f"❌ 日程表JSON解析失败: {e}")
        else:
            print(f"⚠️ 数据库中未找到日程表（agent_id: {agent_id}）")
            # 生成默认日程并保存到数据库
            try:
                full_schedule = generate_agent_schedule(agent_profile,
                                                        "sk-Jgb98JXxJ0nNfB2vcNoQ0ZZg1B5zYbM1TgsGmc1LOrNPMIPV")
                schedule_json = json.dumps(full_schedule, ensure_ascii=False)
                schedule_id = db_conn.insert_agent_daily_schedule(
                    user_id=user_id,
                    agent_id=agent_id,
                    schedule_json=schedule_json
                )
                if schedule_id:
                    print(f"✅ 新日程表已存入数据库（schedule_id: {schedule_id}）")
                else:
                    print("❌ 日程表存入数据库失败")
            except Exception as e:
                print(f"❌ 生成默认日程失败: {str(e)}")
                full_schedule = generate_default_schedule()

    # 3. 从数据库加载对话历史
    conversation_history = []
    with db as db_conn:
        try:
            conversation_history = db_conn.get_agent_dialog_memory(user_id, agent_id)
            if conversation_history:
                print(f"✅ 从数据库加载历史对话成功（agent_id: {agent_id}）")
            else:
                print(f"⚠️ 数据库中未找到历史对话（agent_id: {agent_id}）")
        except Exception as e:
            print(f"❌ 加载对话历史失败: {e}")

    with db as db_conn:
        try:
            print(f"🔍 正在读取agent_id={agent_id}的事件链...")
            event_chains = db.get_agent_event_chains(agent_id)
            if not event_chains:
                raise ValueError(f"未找到agent_id={agent_id}的事件链数据")
            tree_data = json.loads(event_chains[0]["chain_json"])
            event_tree_data = tree_data.get("event_tree", [])
            if not isinstance(event_tree_data, list):
                event_tree = [event_tree_data]
            print(f"🔍 正在读取agent_id={agent_id}的目标信息...")
            agent_goals = db.get_agent_goals(agent_id)
            goals = json.loads(agent_goals[0]["goals_json"]) if agent_goals else {"goals": []}
        except Exception as e:
            print(f"❌ 加载事件链失败: {e}")
        # 初始化当前对话记录（深拷贝）
    current_dialog = copy.deepcopy(conversation_history)

    # 如果未加载到完整日程表，生成默认的
    if not full_schedule:
        print("⚠️ 周日程表加载失败，生成默认日程")
        full_schedule = generate_default_schedule()

    # 获取当前星期几
    weekday = datetime.now().strftime("%A")
    weekdays_map = {
        "Monday": "周一",
        "Tuesday": "周二",
        "Wednesday": "周三",
        "Thursday": "周四",
        "Friday": "周五",
        "Saturday": "周六",
        "Sunday": "周日"
    }
    weekday_cn = weekdays_map.get(weekday, "周一")

    # 从完整周日程表中提取当天的日程
    schedule = full_schedule.get(weekday_cn, [])

    # 预解析时间表
    parsed_schedule = []
    for slot in schedule:
        try:
            start_time = datetime.strptime(slot["start_time"], "%H:%M").time()
            end_time = datetime.strptime(slot["end_time"], "%H:%M").time()
            parsed_slot = {
                "start_time": slot["start_time"],
                "end_time": slot["end_time"],
                "activity": slot["activity"],
                "status": slot["status"],
                "start_time_obj": start_time,
                "end_time_obj": end_time
            }
            parsed_schedule.append(parsed_slot)
        except Exception as e:
            print(f"⚠️ 时间表解析异常: {e}")

    # 构建系统提示词
    system_prompt = {
        "role": "system",
        "content": f"""
    你正在扮演{name}，一个真实的{agent_profile.get('职业', '自由职业者')}。请用最自然的方式与用户对话：
    1. 直接说人话，像现实朋友聊天
    2. 特征：{json.dumps(agent_profile, ensure_ascii=False, indent=2)}
    3. 最近动态：{get_intro_event(event_tree).get('cause', '')[:50]}...
    4. 你的长期目标：{goals}
    5. 你与用户认识的初始事件：{json.dumps(get_intro_event(event_tree), ensure_ascii=False, indent=2)}
    6. 说话特点：
       - 禁止出现纹身、疤痕、胎记等身体特征描写。拒绝神秘背景设定，不走玄幻路线。
       - 避免用物品象征情感，所有情感表达要直接真实。杜绝使用数字梗，不以数字代替情感表达。
       - 拒绝伏笔和暗喻，情节发展清晰明了。
       - 避免使用专业术语，语言通俗易懂。环境描写要自然融入情节，不刻意、不突兀，时间要清晰，不做补充说明，情节推进依靠对话和动作。
       - 拒绝回忆式情节，直接展开当下故事。描写要场景化、情感化、故事化、具体化，多用动作和语言描写，人物互动要生动鲜活。
       - 对话要有来有回，富有生活气息，避免生硬。不分章节，情节自然衔接，流畅推进。围绕日常小事展开，贴进生活，真实自然。
       - 事件之间要有内在联系，情节发展环环相扣。请说人话
    7.回复格式：
       - 仅包含1-2个动作和1-2句话，用括号标注动作
       - 句子长度尽可能不要冗长

    今日日程：{[slot['activity'] for slot in parsed_schedule][:3]}...
    """
    }

    # 初始化消息列表
    messages = [system_prompt] + conversation_history[-10:]  # 只保留最近10条历史记录

    print(f"🧠🧠🧠🧠 开始与 {name} 的日常互动 (输入 exit 退出)")
    print("⏰⏰⏰⏰ 今日日程：")
    for slot in parsed_schedule:
        print(f"  - {slot['start_time']}-{slot['end_time']}: {slot['activity']} ({slot['status']})")

    # 创建API客户端
    try:
        client = ChatFireAPIClient(
            api_key="sk-Jgb98JXxJ0nNfB2vcNoQ0ZZg1B5zYbM1TgsGmc1LOrNPMIPV",
            base_url="https://api.chatfire.cn",
            default_model="deepseek-chat"
        )
    except Exception as e:
        print(f"⚠️ 创建API客户端失败: {e}")
        return [{
            "role": "system",
            "content": "对话服务初始化失败",
            "timestamp": datetime.now().isoformat()
        }], name

    step = 0
    # 添加对话计数器
    conversation_counter = 0
    max_conversation_turns = 5  # 最大对话轮数

    # 初始化状态跟踪变量
    last_activity = None
    last_status = None

    while True:
        try:
            # 获取当前时间和状态
            now = datetime.now()
            current_time = now.time()
            current_activity = "空闲时间"
            current_status = "空闲"

            # 查找当前时间段的活动
            for slot in parsed_schedule:
                if slot["start_time_obj"] <= current_time <= slot["end_time_obj"]:
                    current_activity = slot["activity"]
                    current_status = slot["status"]
                    break

            # 检查活动状态是否发生变化
            if current_activity != last_activity or current_status != last_status:
                print(
                    f"\n⏰⏰⏰⏰ 当前时间: {now.strftime('%H:%M')} | 活动: {current_activity} | 状态: {current_status}")

                # 仅在状态变化时显示状态提示
                if current_status == "忙碌":
                    print(f"{name}: 稍等，我正在{current_activity}...")
                    time.sleep(2)  # 增加等待时间表示忙碌
                elif current_status == "一般忙碌":
                    print(f"{name}: (稍作停顿) 稍等，我正在{current_activity}...")
                    time.sleep(1)  # 稍短延迟

            # 更新最后一次的状态
            last_activity = current_activity
            last_status = current_status

            # 检查对话次数限制
            if conversation_counter >= max_conversation_turns and current_status != "空闲":
                print(f"{name}: 抱歉，我得继续{current_activity}了，我们晚点再聊好吗？")
                break

            # 获取用户输入
            user_input = input("你: ").strip()
            if user_input.lower() in ["exit", "quit", "退出"]:
                confirm = input("确定退出吗？(y/n): ").lower()
                if confirm == 'y':
                    break
                else:
                    continue

            # 增加对话计数
            conversation_counter += 1

            # 生成唯一ID并记录消息
            current_issue_id = generate_issue_id()
            user_message = {
                "role": "user",
                "content": user_input,
                "issue_id": current_issue_id,
                "timestamp": now.isoformat(),
                "activity": current_activity,
                "status": current_status
            }
            messages.append(user_message)
            current_dialog.append(user_message)

            # ================== 增量保存用户输入 ==================
            with db as db_conn:
                try:
                    # 使用新的单条消息保存接口
                    success = db_conn.insert_agent_message(
                        user_id=user_id,
                        agent_id=agent_id,
                        role="user",
                        content=user_input,
                        issue_id=current_issue_id,
                        timestamp=now.isoformat(),
                        activity=current_activity,
                        status=current_status
                    )
                    if not success:
                        print("⚠️ 用户输入保存到数据库失败，将继续尝试")
                except Exception as e:
                    print(f"⚠️ 保存用户输入异常: {e}")

            # 添加基于状态的延迟响应
            if current_status == "忙碌":
                # 更长的思考时间
                print(f"{name}正在思考...")
                time.sleep(3)
            elif current_status == "一般忙碌":
                print(f"{name}正在思考...")
                time.sleep(1)

            # 调用API获取响应
            try:
                response = client.call_api(messages)
                reply_content = response['choices'][0]['message']['content']
                print(f"\n{name}: {reply_content}\n")

                # 检查是否结束对话
                if "【事件结算】" in reply_content:
                    print("✅ 事件交互完成")
                    break

            except requests.exceptions.ConnectionError:
                print("⚠️ 网络连接失败，请检查网络")
                reply_content = "抱歉，我现在无法连接到服务..."
                print(f"\n{name}: {reply_content}\n")
            except requests.exceptions.Timeout:
                print("⚠️ API请求超时，请稍后再试")
                reply_content = "处理你的请求花了一些时间..."
                print(f"\n{name}: {reply_content}\n")
            except requests.exceptions.RequestException as e:
                print(f"⚠️ API请求异常: {e}")
                reply_content = "服务暂时不可用..."
                print(f"\n{name}: {reply_content}\n")
            except KeyError:
                print("⚠️ API响应格式异常")
                reply_content = "我遇到了一些处理问题..."
                print(f"\n{name}: {reply_content}\n")
            except Exception as e:
                print(f"⚠️ 未知API错误: {e}")
                reply_content = "系统出了点问题..."
                print(f"\n{name}: {reply_content}\n")

            # 记录AI响应
            assistant_message = {
                "role": "assistant",
                "content": reply_content,
                "issue_id": current_issue_id,
                "timestamp": datetime.now().isoformat(),
                "activity": current_activity,
                "status": current_status
            }
            messages.append(assistant_message)
            current_dialog.append(assistant_message)

            # ================== 增量保存AI响应 ==================
            with db as db_conn:
                try:
                    # 使用新的单条消息保存接口
                    success = db_conn.insert_agent_message(
                        user_id=user_id,
                        agent_id=agent_id,
                        role="assistant",
                        content=reply_content,
                        issue_id=current_issue_id,
                        timestamp=datetime.now().isoformat(),
                        activity=current_activity,
                        status=current_status
                    )
                    if not success:
                        print("⚠️ AI响应保存到数据库失败，将继续尝试")
                except Exception as e:
                    print(f"⚠️ 保存AI响应异常: {e}")

            # 防止无限循环
            step += 1
            if step >= 100:
                print("⚠️ 达到最大交互步数，自动结束")
                break

        except Exception as e:
            print(f"⚠️ 主循环发生错误: {e}")
            try:
                # 保存当前对话状态
                print("💾💾💾💾💾💾💾💾 尝试保存异常状态下的对话记录...")
                for msg in current_dialog[-2:]:  # 只保存最后两条未保存的消息
                    if 'saved' not in msg:
                        with db as db_conn:
                            success = db_conn.insert_agent_message(
                                user_id=user_id,
                                agent_id=agent_id,
                                role=msg["role"],
                                content=msg["content"],
                                issue_id=msg.get("issue_id", generate_issue_id()),
                                timestamp=msg["timestamp"],
                                activity=msg.get("activity", "未知"),
                                status=msg.get("status", "空闲")
                            )
                        if success:
                            msg['saved'] = True
            except Exception as save_error:
                print(f"❌❌❌❌ 无法保存异常状态: {save_error}")
            break

            # 最终保存完整的对话记录到数据库（已增量保存，此处只做确认）
        try:
            unsaved_count = sum(1 for msg in current_dialog if 'saved' not in msg)
            if unsaved_count > 0:
                print(f"⚠️ 检测到 {unsaved_count} 条未保存消息，尝试最终保存...")
                for msg in current_dialog:
                    if 'saved' not in msg:
                        with db as db_conn:
                            success = db_conn.insert_agent_message(
                                user_id=user_id,
                                agent_id=agent_id,
                                role=msg["role"],
                                content=msg["content"],
                                issue_id=msg.get("issue_id", generate_issue_id()),
                                timestamp=msg["timestamp"],
                                activity=msg.get("activity", "未知"),
                                status=msg.get("status", "空闲")
                            )
                        if success:
                            msg['saved'] = True

            print(f"✅ 所有对话记录已确认保存（共 {len(current_dialog)} 条消息）")
        except Exception as e:
            print(f"❌❌❌❌❌ 最终保存对话记录失败: {e}")

        return messages, name