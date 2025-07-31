from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import uuid
import os
from PIL import Image, ImageDraw, ImageFont
import io
import json
import random
from datetime import datetime
from Agent_builder import AgentBuilder  # 导入AgentBuilder类
from event_loop_tool import run_event_loop  # 导入事件交互脚本
from daily_loop_tool import run_daily_loop

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 确保头像目录存在
if not os.path.exists('avatars'):
    os.makedirs('avatars')

# 一、头像接口 - 生成智能体头像
@app.route('/api/avatar', methods=['GET'])
def generate_avatar():
    agent_id = request.args.get('agent_id')
    if not agent_id:
        return jsonify({"error": "agent_id is required"}), 400

    # 生成简单的头像
    image = Image.new('RGB', (200, 200), color=get_random_color(agent_id))
    draw = ImageDraw.Draw(image)

    # 从agent_id中取前两个字符作为头像初始字母
    initials = agent_id[:2].upper() if agent_id else "?"

    # 确保中文显示正常
    try:
        font = ImageFont.truetype("simhei.ttf", 80)
    except IOError:
        # 如果找不到中文字体，使用默认字体
        font = ImageFont.load_default()

    draw.text((70, 60), initials, fill=(255, 255, 255), font=font)

    # 将图像转为字节流并返回
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    return send_file(img_byte_arr, mimetype='image/png')


def get_random_color(seed):
    """根据seed生成固定的随机颜色"""
    random.seed(seed)
    return (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))


#智能体接口
@app.route('/V1/agents', methods=['POST'])
def get_agent():
    # 获取请求体中的user_input参数
    data = request.json
    user_input = data.get('data', '')

    if not user_input:
        return jsonify({"error": "Missing 'user_input' parameter"}), 400

    try:
        # 创建AgentBuilder实例
        builder = AgentBuilder(api_key='sk-Jgb98JXxJ0nNfB2vcNoQ0ZZg1B5zYbM1TgsGmc1LOrNPMIPV')

        # 通过实例调用方法
        agent_data = builder.build_agent(user_input)

        # 从agent_data中获取formatted_text
        formatted_text = agent_data.get("智能体信息", {})

        # 映射formatted_text字段到API响应字段
        response_data = {
            "user_id": str(formatted_text.get("用户ID", "")),
            "agent_id": str(formatted_text.get("Agent_id", "")),
            "agent_name": str(formatted_text.get("姓名", "")),
            "age": str(formatted_text.get("年龄", "")),
            "career": str(formatted_text.get("职业", "")),
            "country": str(formatted_text.get("国家地区", "")),
            "skill": str(formatted_text.get("个人技能", "")),
            "appearance": str(formatted_text.get("外貌", "")),
            "hobby": str(formatted_text.get("爱好", "")),
            "voice": str(formatted_text.get("声音", "")),
            "relation": str(formatted_text.get("与玩家关系", "")),
            "mbti": str(formatted_text.get("MBTI类型", "")),
            "icon_url": str(formatted_text.get("头像URL", ""))
        }

        return jsonify(response_data), 200

    except Exception as e:
        # 错误处理
        return jsonify({"error": f"Failed to build agent: {str(e)}"}), 500

# 三、对话接口
@app.route('/api/daily', methods=['POST'])
def get_conversation():
    """
    日常对话接口：
    请求体：{"agent_id": "string",  "content": "string", "user_id": "string"}
    返回：{"agent_id": "string", "content": "string"}
    """
    # 解析请求参数
    req_data = request.json
    agent_id = req_data.get("agent_id")
    content = req_data.get("content")

    # 验证必填参数
    if not all([agent_id, content]):
        return jsonify({
            "error": "缺少必填参数：agent_id、content 或 user_id"
        }), 400

    try:
        # 调用事件交互逻辑（直接传入请求参数，文件读取逻辑在main.py中处理）
        daily_result = run_daily_loop(
            user_id=1,
            agent_id=agent_id,
            user_input=content  # 传入用户内容
            # 注意：formatted_text、goals、tree、db等参数由main.py内部处理
        )

        # 构造响应
        return jsonify({
            "agent_id": agent_id,
            "content": daily_result.get("content")
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"事件处理失败：{str(e)}"
        }), 500


# 四、事件接口
@app.route('/api/event', methods=['POST'])
def event():
    """
    事件对话接口：支持 issue_id 为空（使用初始事件）
    请求体：{"agent_id": "string", "issue_id": "string"（可为空）, "content": "string", "user_id": "string"}
    返回：{"agent_id": "string", "issue_id": "string", "content": "string"}
    """
    # 解析请求参数
    req_data = request.json
    agent_id = req_data.get("agent_id")
    issue_id = req_data.get("issue_id")  # 允许为 None 或空字符串
    content = req_data.get("content")

    # 验证必填参数
    if not all([agent_id, content, issue_id]):
        return jsonify({
            "error": "缺少必填参数：agent_id、content 或 user_id"
        }), 400

    try:
        # 调用事件交互逻辑（直接传入请求参数，文件读取逻辑在main.py中处理）
        event_result = run_event_loop(
            user_id=1,
            agent_id=agent_id,
            event_id=issue_id,  # 对应main.py中的event_id参数
            user_input=content  # 传入用户内容
            # 注意：formatted_text、goals、tree、db等参数由main.py内部处理
        )

        # 构造响应
        return jsonify({
            "agent_id": agent_id,
            "issue_id": event_result.get("issue_id"),
            "content": event_result.get("content")
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"事件处理失败：{str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(debug=True)