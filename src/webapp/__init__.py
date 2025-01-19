from flask import Flask

def create_app():
    app = Flask(__name__)
    
    # 配置设置
    app.config.from_mapping(
        SECRET_KEY='your_secret_key',
        # 其他配置项
    )

    # 注册蓝图
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app