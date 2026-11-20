import boto3
import json
import time

apig = boto3.client('apigateway', region_name='us-east-1')
lambda_client = boto3.client('lambda', region_name='us-east-1')

ACCOUNT_ID = "952376465122"
BUCKET_NAME = f"photo-album-storage-{ACCOUNT_ID}"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/ApiGatewayS3ProxyRole"
LF2_ARN = f"arn:aws:lambda:us-east-1:{ACCOUNT_ID}:function:search-photos"

def setup():
    print("Creating REST API...")
    api = apig.create_rest_api(
        name='PhotoSearchAPI',
        description='Photo Search API for CC Assignment 3',
        binaryMediaTypes=['*/*'],
        endpointConfiguration={'types': ['REGIONAL']}
    )
    api_id = api['id']
    print(f"API created with ID: {api_id}")

    # Get root resource id
    resources = apig.get_resources(restApiId=api_id)
    root_id = [r['id'] for r in resources['items'] if r['path'] == '/'][0]

    # Helper function to enable CORS OPTIONS
    def enable_cors(resource_id):
        try:
            apig.put_method(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod='OPTIONS',
                authorizationType='NONE',
                apiKeyRequired=False
            )
            apig.put_integration(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod='OPTIONS',
                type='MOCK',
                requestTemplates={'application/json': '{"statusCode": 200}'}
            )
            apig.put_method_response(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod='OPTIONS',
                statusCode='200',
                responseParameters={
                    'method.response.header.Access-Control-Allow-Headers': False,
                    'method.response.header.Access-Control-Allow-Methods': False,
                    'method.response.header.Access-Control-Allow-Origin': False
                }
            )
            apig.put_integration_response(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod='OPTIONS',
                statusCode='200',
                responseParameters={
                    'method.response.header.Access-Control-Allow-Headers': "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-amz-meta-customLabels'",
                    'method.response.header.Access-Control-Allow-Methods': "'GET,PUT,OPTIONS'",
                    'method.response.header.Access-Control-Allow-Origin': "'*'"
                }
            )
            print(f"Enabled CORS on resource {resource_id}")
        except Exception as e:
            print(f"Error enabling CORS on {resource_id}: {e}")

    # 1. Create /search resource & GET method
    search_res = apig.create_resource(restApiId=api_id, parentId=root_id, pathPart='search')
    search_id = search_res['id']
    
    apig.put_method(
        restApiId=api_id,
        resourceId=search_id,
        httpMethod='GET',
        authorizationType='NONE',
        apiKeyRequired=True,
        requestParameters={'method.request.querystring.q': False}
    )
    
    lambda_uri = f"arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/{LF2_ARN}/invocations"
    apig.put_integration(
        restApiId=api_id,
        resourceId=search_id,
        httpMethod='GET',
        type='AWS_PROXY',
        integrationHttpMethod='POST',
        uri=lambda_uri
    )
    enable_cors(search_id)
    
    # Allow API Gateway to invoke search-photos Lambda
    try:
        lambda_client.add_permission(
            FunctionName='search-photos',
            StatementId=f'apigateway-invoke-{api_id}',
            Action='lambda:InvokeFunction',
            Principal='apigateway.amazonaws.com',
            SourceArn=f"arn:aws:execute-api:us-east-1:{ACCOUNT_ID}:{api_id}/*/*/*"
        )
        print("Granted API Gateway permission to invoke search-photos")
    except Exception as e:
        print(f"Permission might already exist: {e}")

    # Helper for S3 Proxy PUT on {filename}
    def setup_s3_put(parent_path, path_part):
        parent_res = apig.create_resource(restApiId=api_id, parentId=root_id, pathPart=parent_path)
        p_id = parent_res['id']
        enable_cors(p_id)
        
        file_res = apig.create_resource(restApiId=api_id, parentId=p_id, pathPart='{filename}')
        f_id = file_res['id']
        
        apig.put_method(
            restApiId=api_id,
            resourceId=f_id,
            httpMethod='PUT',
            authorizationType='NONE',
            apiKeyRequired=True,
            requestParameters={
                'method.request.path.filename': True,
                'method.request.header.x-amz-meta-customLabels': False,
                'method.request.header.Content-Type': False
            }
        )
        
        s3_uri = f"arn:aws:apigateway:us-east-1:s3:path/{BUCKET_NAME}/{{filename}}"
        apig.put_integration(
            restApiId=api_id,
            resourceId=f_id,
            httpMethod='PUT',
            type='AWS',
            integrationHttpMethod='PUT',
            uri=s3_uri,
            credentials=ROLE_ARN,
            requestParameters={
                'integration.request.path.filename': 'method.request.path.filename',
                'integration.request.header.x-amz-meta-customLabels': 'method.request.header.x-amz-meta-customLabels',
                'integration.request.header.Content-Type': 'method.request.header.Content-Type'
            },
            passthroughBehavior='WHEN_NO_MATCH'
        )
        
        apig.put_method_response(
            restApiId=api_id,
            resourceId=f_id,
            httpMethod='PUT',
            statusCode='200',
            responseParameters={'method.response.header.Access-Control-Allow-Origin': False}
        )
        
        apig.put_integration_response(
            restApiId=api_id,
            resourceId=f_id,
            httpMethod='PUT',
            statusCode='200',
            responseParameters={'method.response.header.Access-Control-Allow-Origin': "'*'"}
        )
        enable_cors(f_id)
        print(f"Configured S3 Proxy PUT for /{parent_path}/{{filename}}")

    setup_s3_put('photos', 'photos')
    setup_s3_put('upload', 'upload')

    # Deploy API
    deployment = apig.create_deployment(restApiId=api_id, stageName='v1')
    print("API deployed to stage 'v1'")

    # Create API Key
    api_key_res = apig.create_api_key(
        name='PhotoSearchKey',
        enabled=True,
        generateDistinctId=True
    )
    api_key_id = api_key_res['id']
    api_key_val = api_key_res['value']
    print(f"API Key created: id={api_key_id}, value={api_key_val}")

    # Create Usage Plan
    usage_plan = apig.create_usage_plan(
        name='PhotoSearchUsagePlan',
        apiStages=[{'apiId': api_id, 'stage': 'v1'}]
    )
    usage_plan_id = usage_plan['id']
    
    apig.create_usage_plan_key(
        usagePlanId=usage_plan_id,
        keyId=api_key_id,
        keyType='API_KEY'
    )
    print("API Key associated with Usage Plan")

    # Generate and export JavaScript SDK
    print("Generating JavaScript SDK...")
    sdk_res = apig.get_sdk(
        restApiId=api_id,
        stageName='v1',
        sdkType='javascript'
    )
    with open('d:/Codes/proj3/frontend/apiGateway-js-sdk.zip', 'wb') as f:
        f.write(sdk_res['body'].read())
    print("SDK successfully saved to d:/Codes/proj3/frontend/apiGateway-js-sdk.zip")

    config = {
        'api_id': api_id,
        'endpoint': f"https://{api_id}.execute-api.us-east-1.amazonaws.com/v1",
        'api_key': api_key_val
    }
    with open('d:/Codes/proj3/api_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    print("Saved api_config.json:", config)

if __name__ == '__main__':
    setup()
