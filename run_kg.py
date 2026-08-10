"""
知识图谱系统 — 独立启动脚本
============================================================
将知识图谱 Blueprint 和页面路由注册到现有 web_app，
完全不动 web_app.py 代码。

用法:
  python run_kg.py          # 启动 web_app (:5001) + 知识图谱
  python run_kg.py --port 5002  # 指定端口
============================================================
"""

import sys
import os
import argparse
from pathlib import Path

# 确保项目根目录在 path 中
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# 注册知识图谱 Blueprint 到现有 app
from web_app import app, socketio
from blueprints.kg_api import kg_bp, register_kg_routes

# 1. 注册 API Blueprint (所有路由以 /api/kg/ 为前缀)
app.register_blueprint(kg_bp)
print("✅ 知识图谱 API Blueprint 已注册 → /api/kg/*")

# 2. 注册页面路由 (/kg/explorer, /kg/search)
register_kg_routes(app)
print("✅ 知识图谱页面已注册 → /kg/explorer, /kg/search")

# 3. 可选：在主页导航中添加知识图谱入口
# （不动 templates/index.html，通过 app.before_request 注入提示）

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="CPA知识图谱系统启动")
    parser.add_argument("--port", type=int, default=5001, help="服务端口（默认5001）")
    parser.add_argument("--debug", action="store_true", default=True, help="调试模式")
    args = parser.parse_args()

    print("=" * 60)
    print("   🧠 CPA 知识图谱 + 问答系统")
    print(f"   知识图谱 API:  http://localhost:{args.port}/api/kg/")
    print(f"   图谱浏览器:     http://localhost:{args.port}/kg/explorer")
    print(f"   CPA 问答:       http://localhost:{args.port}/")
    print(f"   管理后台:       http://localhost:{args.port}/admin")
    print("=" * 60)

    socketio.run(app, host='0.0.0.0', port=args.port, debug=args.debug, allow_unsafe_werkzeug=True)
