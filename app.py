from flask import Flask, request, render_template
from config import *
from arango import ArangoClient
app = Flask(__name__)

# Basic definitions
class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

# DB Setup
client = ArangoClient(hosts='http://localhost:8529')
db = client.db(DB_NAME, username=ARRANGO_USER, password=ARRANGO_PASSWORD)

@app.route('/')
def hello():
    return render_template('index.html')

@app.route('/api/v1/cases/check')
def cases_check():
    if 'celex' in request.args:
        celex = int(request.args['id'])
    else:
        raise InvalidUsage('No CELEX number field provided.')

@app.route('/api/v1/cases/get')
def cases_get():
    if 'celex' in request.args:
        celex = int(request.args['id'])
    else:
        raise InvalidUsage('No CELEX number field provided.')



if __name__ == '__main__':
    app.run()