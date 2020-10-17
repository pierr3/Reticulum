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
http = urllib3.PoolManager()

# Get a new case
def get_new_case(celex, max_level=2, current_level=0):
    r = http.request('GET', CELLAR_CELEX_BASE_URL + celex + '?language=ENG',  
                    headers={ 'Accept': 'application/xml;notice=branch', 'Accept-Language': 'eng' })
    if r.status != 200:
        return "" # Need to handle exception here in the future
    
    bs_content = bs(r.data, "lxml")
    case_name = bs_content.find('parties')
    if case_name is None:
        case_name = bs_content.find('title').getText()
    else:
        case_name = case_name.getText()

    case_ecli = ''
    work = bs_content.find('work')
    if work != None:
        if 'ECLI:EU' in work.getText():
            for ids in work.find_all('identifier'):
                if 'ecli' in ids.find_next('type').getText():
                    case_ecli = ids.getText()
                    break


    # We now add the new case
    cases.insert({'_key': celex, 'ecli': case_ecli, 'name': case_name})

    # We reached the max level, we stop here
    if current_level > max_level:
        return

    # We now move to linked cases

    cited_cases = []

    all_cases = bs_content.find_all('work_cites_work')
    for case in all_cases:
        if 'ECLI:EU' in case.getText():
            linked_case = {'_key': '', 'ecli': ''}
            for ids in case.find_all('identifier'):
                if 'celex' in ids.find_next('type').getText():
                    linked_case['_key'] = ids.getText()
                #if 'ecli' in ids.find_next('type').getText():
                #    linked_case['ecli'] = ids.getText()
            cited_cases.append(linked_case)
    
    # We fetch all the linked cases
    for cc in cited_cases:
        if not cases.has(cc['_key']):
            get_new_case(cc['_key'], max_level, current_level+1)
        # We add the link between this current cases and all cited cases
        relationships.insert({'_from': 'cases/'+celex, '_to': 'cases/'+cc['_key']})
    
    return str(cited_cases)

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

    result = graph.traverse(start_vertex = 'cases/'+celex, direction='any', strategy='depthfirst', min_depth=0, max_depth=10)

    return result



if __name__ == '__main__':
    app.run()