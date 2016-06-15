from flask import Flask

app = Flask(__name__)

app.config['CELERY_BROKER_URL'] = 'amqp://'
app.config['CELERY_RESULT_BACKEND'] = 'rpc://'

app.debug = True

__all__ = ['app']
