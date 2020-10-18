from flask import Flask, request, render_template, escape
from config import *
from arango import ArangoClient
from bs4 import BeautifulSoup as bs
import urllib3
from redis import Redis
from rq import Queue
from tasks import get_new_case, q, celex_to_case
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
cases = db.collection('cases')
graph = db.graph('casesGraph')
relationships = db.collection('cases_connections')

# Get a new case
@app.route('/')
def hello():
    return render_template('index.html')

@app.route('/api/v1/cases/request')
def cases_check():
    if 'celex' in request.args:
        celex = escape(request.args['celex'])
    else:
        raise InvalidUsage('No CELEX number field provided.')
    if not cases.has(celex):
        q.enqueue(get_new_case, celex)
        return "{'status': 0, 'message': 'Case has been added to the pending list, it could take a couple hours for it to be indexed!'}"
    else:
        if cases.get(celex)['indexed']:
            return "{'status': 2, 'message': 'Case is available!'}"
        else: 
            q.enqueue(get_new_case, celex)
            return "{'status': 1, 'message': 'Case is being processed, it could take a couple hours for it to be indexed!'}"

@app.route('/api/v1/cases/get')
def cases_get():
    if 'celex' in request.args and 'direction' in request.args:
        celex = escape(request.args['celex'])
        direction = int(request.args['direction'])
    else:
        raise InvalidUsage('No CELEX number and direction field provided.')

    # First we check if we have that case in database
    if not cases.has(celex):
        return "Case is not in database"

    result = graph.traverse(
    start_vertex='cases/'+celex,
    direction= 'outbound' if direction else 'inbound', min_depth=1, max_depth=2)   

    return result



if __name__ == '__main__':
    app.run()