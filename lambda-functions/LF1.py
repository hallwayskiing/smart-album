import json
import os
import boto3
import urllib.parse
import urllib.request
import base64
from datetime import datetime

s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')

OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', '').rstrip('/')
OPENSEARCH_USER = os.environ.get('OPENSEARCH_USER', 'admin')
OPENSEARCH_PASS = os.environ.get('OPENSEARCH_PASS', 'AdminPassword2026!')
INDEX_NAME = os.environ.get('INDEX_NAME', 'photos')

def post_to_opensearch(document):
    if not OPENSEARCH_ENDPOINT:
        print("Warning: OPENSEARCH_ENDPOINT is not set.")
        return False
        
    url = f"{OPENSEARCH_ENDPOINT}/{INDEX_NAME}/_doc"
    auth_str = f"{OPENSEARCH_USER}:{OPENSEARCH_PASS}"
    auth_header = "Basic " + base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": auth_header
    }
    
    data = json.dumps(document).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode('utf-8')
            print(f"OpenSearch response [{response.status}]: {res_body}")
            return True
    except Exception as e:
        print(f"Error indexing to OpenSearch: {e}")
        raise e

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event))
    
    records = event.get('Records', [])
    if not records:
        print("No records found in event.")
        return {'statusCode': 400, 'body': 'No records found'}
        
    record = records[0]
    bucket = record['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(record['s3']['object']['key'])
    print(f"Processing object: s3://{bucket}/{key}")
    
    # 1. Retrieve metadata from S3
    custom_labels = []
    try:
        head_res = s3.head_object(Bucket=bucket, Key=key)
        metadata = head_res.get('Metadata', {})
        print("S3 Metadata: ", metadata)
        
        # S3 lowercases metadata keys
        custom_labels_str = metadata.get('customlabels') or metadata.get('x-amz-meta-customlabels')
        if custom_labels_str:
            custom_labels = [c.strip().lower() for c in custom_labels_str.split(',') if c.strip()]
            print("Extracted custom labels: ", custom_labels)
    except Exception as e:
        print(f"Error fetching head_object: {e}")

    # 2. Detect labels using Rekognition
    rek_labels = []
    try:
        rek_res = rekognition.detect_labels(
            Image={'S3Object': {'Bucket': bucket, 'Name': key}},
            MaxLabels=20,
            MinConfidence=70
        )
        rek_labels = [label['Name'].lower().strip() for label in rek_res.get('Labels', [])]
        print("Rekognition labels: ", rek_labels)
    except Exception as e:
        print(f"Error detecting labels with Rekognition: {e}")

    # 3. Combine labels and deduplicate
    all_labels = list(dict.fromkeys(rek_labels + custom_labels))
    print("Combined labels: ", all_labels)
    
    # 4. Construct JSON document as required by Assignment 3 schema
    document = {
        "objectKey": key,
        "bucket": bucket,
        "createdTimestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "labels": all_labels
    }
    print("Indexing document: ", json.dumps(document))
    
    # 5. Store document in OpenSearch
    post_to_opensearch(document)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Photo successfully indexed',
            'document': document
        })
    }
