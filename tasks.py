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
        
    present_case = {'_key': celex, 'ecli': case_ecli, 'name': case_name}

    # We now add the new case or update it
    if cases.has(celex):
        cases.update(present_case)
    else:
        # The case is brand new and has not been indexed yet, we will flag it as indexed once we get all the relationships available
        present_case['indexed'] = False
        cases.insert(present_case)

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
            cases.insert(cc)
            # Add the task to the queue
            q.enqueue(get_new_case, celex, max_level, current_level+1)

        # We add the link between this current cases and all cited cases
        relationships.insert({'_from': 'cases/'+celex, '_to': 'cases/'+cc['_key']})

    # All relationships inserted, we can now mark it as indexed
    present_case['indexed'] = True
    cases.update(present_case)