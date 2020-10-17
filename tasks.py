import time
from config import *
from arango import ArangoClient
from bs4 import BeautifulSoup as bs
import urllib3, re
from redis import Redis
from rq import Queue

client = ArangoClient(hosts='http://localhost:8529')
db = client.db(DB_NAME, username=ARRANGO_USER, password=ARRANGO_PASSWORD)
cases = db.collection('cases')
relationships = db.collection('cases_connections')

http = urllib3.PoolManager()
q = Queue(connection=Redis())

def celex_to_case(celex):
    if 'CJ' in celex:
        number = 'C-'
    if 'TJ' in celex:
        number = 'T-'
    if 'FJ' in celex:
        number = 'F-'
    number = number + celex[7:].lstrip('0') + '/' + celex[3:5] 
    return number

def get_new_case(celex, max_level=2, current_level=0):
    r = http.request('GET', CELLAR_CELEX_BASE_URL + celex + '?language=ENG',  
                    headers={ 'Accept': 'application/xml;notice=branch', 'Accept-Language': 'eng' })
    if r.status != 200:
        return "" # Need to handle exception here in the future
    
    bs_content = bs(r.data, "lxml")
    
    present_case = {'_key': celex, 'number': celex_to_case(celex)}

    work = bs_content.find('work')
    if work != None:
        # Already inserted cases should have an ECLI
        ecli = work.find('ecli', recursive=False)
        if ecli != None:
            present_case['ecli'] = ecli.getText()
        else:
            present_case['ecli'] = 'No ECLI found'

        date = work.find('date', recursive=False)
        if date != None:
            present_case['date'] = date.find('value').getText()
            present_case['year'] = int(date.find('year').getText())

    expression = bs_content.find('expression', recursive=False)
    if expression != None:
        case_name = expression.find('parties', recursive=False)
        if case_name is None:
            case_name = expression.find('expression_title_short')
            if case_name != None:
                present_case['name'] = case_name.getText()
            else:
                present_case['name'] = 'Could not find name'
        else:
            present_case['name'] = case_name.getText()

    # We now add the new case or update it
    if cases.has(celex):
        cases.update(present_case)
    else:
        # The case is brand new and has not been indexed yet, we will flag it as indexed once we get all the relationships available
        present_case['indexed'] = False
        cases.insert(present_case)

    present_case = cases.get(celex)

    # We reached the max level, we stop here
    if current_level > max_level or present_case['indexed']:
        return

    # We now move to linked cases

    cited_cases = []

    all_cases = bs_content.find_all('work_cites_work')
    for case in all_cases:
        # We check if the citation is another judgement of the court
        if re.search(r'(6[0-9]{4})(CJ|TJ|FJ)([0-9]{4})',  case.getText()):
            linked_case = {'_key': '', 'ecli': ''}
            for ids in case.find_all('identifier'):
                if 'celex' in ids.find_next('type').getText():
                    linked_case['_key'] = ids.getText()
                if 'ecli' in ids.find_next('type').getText():
                    linked_case['ecli'] = ids.getText()
            cited_cases.append(linked_case)
    
    # We fetch all the linked cases
    for cc in cited_cases:
        # Add the case so we can build the links then update the downstream metadata
        if not cases.has(cc['_key']):
            cc['indexed'] = False
            cc['number'] = celex_to_case(cc['_key'])
            cases.insert(cc)
            # Add the task to the queue
            q.enqueue(get_new_case, cc['_key'], max_level, current_level+1)

        # We add the link between this current cases and all cited cases
        relationships.insert({'_from': 'cases/'+celex, '_to': 'cases/'+cc['_key']})

    # All relationships inserted, we can now mark it as indexed
    present_case['indexed'] = True
    cases.update(present_case)