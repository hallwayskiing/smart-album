import json
import os
import boto3
import urllib.parse
import urllib.request
import base64
import re

lex = boto3.client('lexv2-runtime', region_name='us-east-1')

OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', '').rstrip('/')
OPENSEARCH_USER = os.environ.get('OPENSEARCH_USER', 'admin')
OPENSEARCH_PASS = os.environ.get('OPENSEARCH_PASS', 'AdminPassword2026!')
INDEX_NAME = os.environ.get('INDEX_NAME', 'photos')
BOT_ID = os.environ.get('LEX_BOT_ID', 'F6POHMQCVR')
BOT_ALIAS_ID = os.environ.get('LEX_BOT_ALIAS_ID', 'TSTALIASID')
LOCALE_ID = os.environ.get('LEX_LOCALE_ID', 'en_US')

STOP_WORDS = {
    'show', 'me', 'photos', 'photo', 'pictures', 'picture', 'with', 
    'in', 'them', 'and', 'or', 'a', 'an', 'the', 'find', 'search', 
    'of', 'please', 'for', 'to', 'some', 'all'
}

def extract_keywords_from_lex(query_text):
    keywords = []
    try:
        response = lex.recognize_text(
            botId=BOT_ID,
            botAliasId=BOT_ALIAS_ID,
            localeId=LOCALE_ID,
            sessionId='user-search-session',
            text=query_text
        )
        print("Lex response: ", json.dumps(response))
        session_state = response.get('sessionState', {})
        intent = session_state.get('intent', {})
        slots = intent.get('slots', {}) or {}
        
        for slot_name, slot_data in slots.items():
            if slot_data and 'value' in slot_data:
                val = slot_data['value'].get('interpretedValue') or slot_data['value'].get('originalValue')
                if val:
                    val = val.lower().strip()
                    if val not in STOP_WORDS and val not in keywords:
                        keywords.append(val)
    except Exception as e:
        print(f"Error querying Lex bot: {e}")
        
    # Heuristic fallback / supplement: token extraction
    tokens = re.findall(r'\b[a-zA-Z0-9_\-]+\b', query_text.lower())
    for token in tokens:
        if token not in STOP_WORDS and token not in keywords:
            keywords.append(token)
            
    # Add singular/plural variants for English keywords (e.g. dogs -> dog, cats -> cat)
    all_kws = list(keywords)
    for kw in keywords:
        if kw.endswith('ies') and len(kw) > 3:
            variant = kw[:-3] + 'y'
            if variant not in all_kws: all_kws.append(variant)
        elif kw.endswith('es') and len(kw) > 3:
            for variant in [kw[:-2], kw[:-1]]:
                if variant not in all_kws: all_kws.append(variant)
        elif kw.endswith('s') and len(kw) > 2:
            variant = kw[:-1]
            if variant not in all_kws: all_kws.append(variant)
            
    print(f"Resolved search keywords for '{query_text}': {all_kws}")
    return all_kws

def query_opensearch(keywords):
    if not OPENSEARCH_ENDPOINT or not keywords:
        return []
        
    url = f"{OPENSEARCH_ENDPOINT}/{INDEX_NAME}/_search"
    auth_str = f"{OPENSEARCH_USER}:{OPENSEARCH_PASS}"
    auth_header = "Basic " + base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": auth_header
    }
    
    should_clauses = []
    for kw in keywords:
        should_clauses.append({"match": {"labels": {"query": kw, "boost": 2.0}}})
        should_clauses.append({"wildcard": {"labels": f"*{kw}*"}})
        # Also check objectKey
        should_clauses.append({"wildcard": {"objectKey": f"*{kw}*"}})
        
    query_body = {
        "size": 50,
        "query": {
            "bool": {
                "should": should_clauses,
                "minimum_should_match": 1
            }
        }
    }
    
    data = json.dumps(query_body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    
    photos = []
    seen_urls = set()
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            hits = res_data.get('hits', {}).get('hits', [])
            print(f"OpenSearch returned {len(hits)} hits")
            
            for hit in hits:
                source = hit.get('_source', {})
                bucket = source.get('bucket')
                key = source.get('objectKey')
                labels = source.get('labels', [])
                
                if bucket and key:
                    url = f"https://{bucket}.s3.amazonaws.com/{key}"
                    if url not in seen_urls:
                        seen_urls.add(url)
                        photos.append({
                            "url": url,
                            "labels": labels
                        })
    except Exception as e:
        print(f"Error querying OpenSearch: {e}")
        
    return photos

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event))
    
    # Handle CORS preflight if routed to Lambda
    http_method = event.get('httpMethod', '')
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET,PUT,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-amz-meta-customLabels'
            },
            'body': ''
        }
        
    params = event.get('queryStringParameters') or {}
    q = params.get('q', '').strip()
    
    cors_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET,PUT,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-amz-meta-customLabels'
    }
    
    if not q:
        print("Empty search query provided.")
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({'results': []})
        }
        
    print(f"Processing search query: '{q}'")
    keywords = extract_keywords_from_lex(q)
    
    if not keywords:
        print("No keywords extracted from query.")
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({'results': []})
        }
        
    results = query_opensearch(keywords)
    print(f"Returning {len(results)} photos for query '{q}'")
    
    return {
        'statusCode': 200,
        'headers': cors_headers,
        'body': json.dumps({'results': results})
    }
