# Smart Album - AI Photo Search Application

A serverless, intelligent photo album web application deployed on AWS that supports natural language search and automated image indexing with AWS Rekognition, Amazon Lex, OpenSearch (Elasticsearch), S3, and API Gateway.

## Live Demo
* **Frontend Web Application:** [http://photo-album-frontend-952376465122.s3-website-us-east-1.amazonaws.com](http://photo-album-frontend-952376465122.s3-website-us-east-1.amazonaws.com)
* **API Gateway Endpoint:** `https://59l6vq12c4.execute-api.us-east-1.amazonaws.com/v1`

---

## Repository Structure

```text
+-- front-end/               # Web client files deployed to S3 static website
|   +-- index.html           # Main HTML UI for upload and search
|   +-- main.js              # Client logic, search handling, API integration
|   +-- apigClient.js        # API Gateway generated JavaScript SDK
|   \-- lib/                 # SDK dependencies (axios, CryptoJS, url-template)
|
+-- lambda-functions/        # AWS Lambda serverless backend functions
|   +-- LF1.py               # index-photos: Rekognition & metadata extraction
|   +-- LF2.py               # search-photos: Lex disambiguation & OpenSearch query
|   +-- LF1/lambda_function.py
|   \-- LF2/lambda_function.py
|
\-- other-scripts/           # Infrastructure as Code & DevOps configurations
    +-- template.yaml        # CloudFormation template for the stack
    +-- buildspec.yml        # CodeBuild spec for Lambda CI/CD
    +-- buildspec-frontend.yml # CodeBuild spec for Frontend S3 deployment
    +-- setup_apigw.py       # API Gateway, S3 Proxy & SDK generation script
    \-- api_config.json      # Deployed API IDs and endpoints reference
```

---

## System Architecture

1. **Photo Upload & Indexing Pipeline (LF1):**
   * Photos are uploaded via `PUT /photos/{filename}` through an **API Gateway S3 Proxy** directly into an Amazon S3 storage bucket (`photo-album-storage-952376465122`).
   * Custom labels provided by the user are passed through the `x-amz-meta-customLabels` header into S3 object metadata.
   * An S3 `ObjectCreated:Put` event triggers Lambda **LF1 (`index-photos`)**.
   * LF1 calls **Amazon Rekognition** (`detect_labels`) to extract visual labels and reads `x-amz-meta-customLabels` via S3 `head_object`.
   * Combined labels are formatted into a JSON document and indexed into **Amazon OpenSearch**.

2. **Natural Language Search Pipeline (LF2):**
   * The web application sends queries to `GET /search?q={query}` with API Key authentication.
   * Lambda **LF2 (`search-photos`)** receives the search query and passes it to an **Amazon Lex V2 bot (`PhotoSearchBot`)**.
   * Lex extracts keywords into intent slots; LF2 also handles lemmatization (singular/plural forms).
   * LF2 queries the OpenSearch cluster for matching photo documents and returns results to the client.

---

## Acceptance Criteria Verified
- [x] End-to-end natural language photo search (e.g. *"show me dogs"*, *"trees and birds"*)
- [x] Multi-keyword and plural queries (e.g. *"cats and dogs"*)
- [x] Custom metadata (`x-amz-meta-customLabels`) indexing and search
- [x] CloudFormation stack template validated and deployable
- [x] CI/CD Buildspecs for Lambda and Frontend deployment
