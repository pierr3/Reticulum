from flask import Flask, request, render_template, escape
from config import *
from arango import ArangoClient
from lxml import etree
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
http = urllib3.PoolManager()

# Get a new case
def get_new_case(celex, level=2):
    r = http.request('GET', CELLAR_CELEX_BASE_URL + celex + '?language=ENG',  
                    headers={ 'Accept': 'application/xml;notice=object' })
    if r.status is not 200:
        return "" # Need to handle exception here in the future
    
    root = etree.fromstring(r.data)
    

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
        get_new_case(celex)

    c = cases.get(celex)

    result = graph.traverse(
        start_vertex = celex,
        direction='outbound',
        strategy='breadthfirst'
    )

    return result



if __name__ == '__main__':
    app.run()