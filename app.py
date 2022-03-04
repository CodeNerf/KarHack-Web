from flask import Flask
from werkzeug.middleware.profiler import  ProfilerMiddleware

app = Flask(__name__)
app.config['SECRET_KEY'] = 'thisisasecretkeysodonthackme'
# app.config['PROFILE'] = True
# app.config["REDIS_URL"] = "redis://localhost"
# app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[10])

@app.context_processor
def instance_name():
    return dict(instance_name="Tom")