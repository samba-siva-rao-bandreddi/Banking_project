# AWS S3 Setup Guide for Banking CDC Pipeline

> **Goal**: Create an S3 bucket and configure credentials to store Parquet files from Kafka.

---

## Step 1: Create an AWS Account (Skip if you have one)

1. Go to [aws.amazon.com](https://aws.amazon.com)
2. Click **"Create an AWS Account"**
3. Follow the registration process
4. Add a payment method (required, but we'll use free tier)

---

## Step 2: Create an S3 Bucket

### 2.1 Navigate to S3
1. Log in to **AWS Console**: [console.aws.amazon.com](https://console.aws.amazon.com)
2. Search for **"S3"** in the top search bar
3. Click **"S3"** to open the S3 dashboard

### 2.2 Create Bucket
1. Click **"Create bucket"** (orange button)

2. **Bucket name**: `banking-data-lake`
   > ⚠️ Bucket names must be globally unique. If taken, try `banking-data-lake-yourname`

3. **AWS Region**: Select `us-east-1` (or your preferred region)
   > 💡 Remember this region - you'll need it for .env

4. **Object Ownership**: Keep default (ACLs disabled)

5. **Block Public Access**: Keep all boxes **checked** ✅
   > This keeps your data private

6. **Bucket Versioning**: Disable (optional)

7. **Default encryption**: Enable with **SSE-S3** (free)

8. Click **"Create bucket"**

### 2.3 Verify Bucket Created
You should see your bucket in the S3 dashboard list.

---

## Step 3: Create IAM User for Programmatic Access

### 3.1 Navigate to IAM
1. Search for **"IAM"** in AWS Console
2. Click **"IAM"** (Identity and Access Management)

### 3.2 Create User
1. Click **"Users"** in the left sidebar
2. Click **"Create user"**

3. **User name**: `banking-pipeline-user`

4. Click **"Next"**

### 3.3 Set Permissions
1. Select **"Attach policies directly"**

2. Search for **"AmazonS3FullAccess"**

3. Check the box next to **"AmazonS3FullAccess"** ✅

4. Click **"Next"**

5. Click **"Create user"**

---

## Step 4: Create Access Keys

### 4.1 Open User Details
1. Click on the user **"banking-pipeline-user"**
2. Click the **"Security credentials"** tab

### 4.2 Create Access Key
1. Scroll to **"Access keys"** section
2. Click **"Create access key"**

3. Select **"Application running outside AWS"**
4. Click **"Next"**

5. (Optional) Add description: `Banking CDC Pipeline`
6. Click **"Create access key"**

### 4.3 Save Your Credentials ⚠️ IMPORTANT
You will see:
```
Access key ID:     AKIAXXXXXXXXXXXXXXXX
Secret access key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**⚠️ SAVE THESE NOW! You cannot see the secret key again after closing this page.**

Options:
- Click **"Download .csv file"** to save
- Or copy both values immediately

---

## Step 5: Configure Your Project

### 5.1 Update .env File

Open `banking_project/.env` and update:

```env
# AWS S3 Configuration
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION=us-east-1
S3_BUCKET_NAME=banking-data-lake
```

Replace with your actual values:
| Variable | Where to find it |
|----------|------------------|
| `AWS_ACCESS_KEY_ID` | From Step 4.3 |
| `AWS_SECRET_ACCESS_KEY` | From Step 4.3 |
| `AWS_REGION` | Region you selected in Step 2.2 (e.g., `us-east-1`) |
| `S3_BUCKET_NAME` | Bucket name from Step 2.2 |

---

## Step 6: Test the Connection

### Option A: Test with Python Script
Create a test file `test_s3.py`:

```python
import boto3
import os
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    's3',
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

bucket = os.getenv("S3_BUCKET_NAME")

# List buckets
response = s3.list_buckets()
print("✅ Connected to AWS S3!")
print("Your buckets:", [b['Name'] for b in response['Buckets']])

# Test upload
s3.put_object(Bucket=bucket, Key="test/hello.txt", Body="Hello from Banking Pipeline!")
print(f"✅ Test file uploaded to s3://{bucket}/test/hello.txt")
```

Run:
```bash
python test_s3.py
```

### Option B: Test with AWS CLI
```bash
aws s3 ls s3://banking-data-lake/
```

---

## Step 7: Verify in AWS Console

1. Go to **S3** in AWS Console
2. Click on your bucket **"banking-data-lake"**
3. You should see the `test/` folder with `hello.txt`

---

## Troubleshooting

### Error: "Access Denied"
- Check if Access Key ID and Secret are correct
- Verify the IAM user has `AmazonS3FullAccess` policy

### Error: "NoSuchBucket"
- Verify bucket name in .env matches exactly
- Check the bucket exists in AWS Console

### Error: "InvalidAccessKeyId"
- Access Key ID is wrong
- The access key may have been deleted

### Error: "SignatureDoesNotMatch"
- Secret Access Key is wrong (check for extra spaces)

---

## Security Best Practices

1. **Never commit .env to Git**
   ```bash
   # Add to .gitignore
   .env
   ```

2. **Use least privilege** - For production, create a policy that only allows access to your specific bucket

3. **Rotate keys regularly** - Delete old access keys and create new ones periodically

4. **Enable MFA** - Add multi-factor authentication to your AWS account

---

## Quick Reference

| Item | Value |
|------|-------|
| AWS Console | [console.aws.amazon.com](https://console.aws.amazon.com) |
| S3 Dashboard | [s3.console.aws.amazon.com](https://s3.console.aws.amazon.com) |
| IAM Dashboard | [console.aws.amazon.com/iam](https://console.aws.amazon.com/iam) |
| Free Tier | 5GB storage, 20,000 GET, 2,000 PUT requests/month |

---

## Summary Checklist

- [ ] Created AWS account
- [ ] Created S3 bucket `banking-data-lake`
- [ ] Created IAM user `banking-pipeline-user`
- [ ] Attached `AmazonS3FullAccess` policy
- [ ] Created and saved Access Keys
- [ ] Updated `.env` with credentials
- [ ] Tested connection successfully
