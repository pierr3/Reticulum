from flask import Flask, request, render_template, escape
from config import *
from arango import ArangoClient
from bs4 import BeautifulSoup as bs
import urllib3
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

@app.route('/api/v1/cases/check')
def cases_check():
    return "Not implemented yet."

@app.route('/api/v1/cases/get')
def cases_get():
    if 'celex' in request.args:
        celex = escape(request.args['celex'])
    else:
        raise InvalidUsage('No CELEX number field provided.')

    # First we check if we have that case in database
    if not cases.has(celex):
        return get_new_case(celex)

    result = graph.traverse(
    start_vertex='cases/'+celex,
    direction='inbound',
    strategy='bfs',
    edge_uniqueness='global',
    vertex_uniqueness='global', )   

    return result



if __name__ == '__main__':
    app.run()