import logging
from app import app
import views

gunicorn_logger = logging.getLogger('gunicorn.critical')
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(logging.CRITICAL)
if __name__ == '__main__':
    app.run()