import boto3
import os
from dotenv import load_dotenv

load_dotenv()

s3=boto3.client(
    's3',
    region_name=os.getenv('AWS_REGION'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

bucket=os.getenv('S3_BUCKET_NAME')


response=s3.list_buckets()

print("Connected to AWS S3")
print("Your buckets:", [b['Name'] for b in response['Buckets']])


#test upload
s3.put_object(Bucket=bucket,Key="test/hello.txt",Body="Hello from Banking Pipeline!")
print(f"✅ Test file uploaded to s3://{bucket}/test/hello.txt")