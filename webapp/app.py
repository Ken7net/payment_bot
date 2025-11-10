from flask import Flask
from decouple import config


def create_app():
    app = Flask(__name__)
    app.secret_key = config("FLASK_SECRET_KEY")

    from .views import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app


app = create_app()
