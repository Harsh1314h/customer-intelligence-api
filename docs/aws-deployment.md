# AWS Deployment Guide

This project deploys to AWS with:

- Amazon ECR for the Docker image.
- Amazon S3 for trained model artifacts.
- AWS App Runner for the public HTTPS API.
- GitHub Actions with AWS OIDC for CI/CD.

The default region used by the workflow is `ap-south-1`.

## 0. Where To Run These Commands

There are three different places involved:

- **Local PowerShell on your laptop:** project commands like `git`, `docker`, `python`, and `pytest`.
- **AWS CloudShell in your AWS account:** AWS commands like `aws s3`, `aws iam`, `aws ecr`, and `aws apprunner`.
- **GitHub website:** repository secrets for GitHub Actions.

If your local PowerShell says `aws` is not recognized, that is fine. Open AWS in your browser, sign in, and click the CloudShell icon in the top navigation bar. CloudShell already has the AWS CLI installed and authenticated for your account.

You only need to install AWS CLI locally if you want to run AWS commands from your own PowerShell.

## 1. Choose Names

Use these values unless you want custom names:

```powershell
$env:AWS_REGION="ap-south-1"
$env:APP_NAME="customer-intelligence-api"
$env:MODEL_BUCKET="customer-intelligence-models-YOUR_UNIQUE_SUFFIX"
```

S3 bucket names must be globally unique. Replace `YOUR_UNIQUE_SUFFIX` with something like your GitHub username.

## 2. Upload Model Artifacts To S3

Run this from the project root after training:

```powershell
aws s3 mb "s3://$env:MODEL_BUCKET" --region "$env:AWS_REGION"
aws s3 cp models/ "s3://$env:MODEL_BUCKET/customer-intelligence/models/" --recursive
```

Your model artifact URI will be:

```text
s3://YOUR_BUCKET/customer-intelligence/models/
```

## 3. Create The ECR Repository

The GitHub workflow can create this automatically, but creating it once upfront is also fine:

```powershell
aws ecr create-repository `
  --repository-name customer-intelligence-api `
  --region "$env:AWS_REGION" `
  --image-scanning-configuration scanOnPush=true
```

## 4. Create App Runner ECR Access Role

App Runner needs this role to pull private images from ECR.

Create `apprunner-trust-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "build.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Run:

```powershell
aws iam create-role `
  --role-name AppRunnerECRAccessRole `
  --assume-role-policy-document file://apprunner-trust-policy.json

aws iam attach-role-policy `
  --role-name AppRunnerECRAccessRole `
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

aws iam get-role --role-name AppRunnerECRAccessRole --query "Role.Arn" --output text
```

Save the returned ARN. It becomes the GitHub secret `APP_RUNNER_ACCESS_ROLE_ARN`.

## 5. Create App Runner Instance Role

The running API needs this role to read model files from S3.

Create `apprunner-instance-trust-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "tasks.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Create the role:

```powershell
aws iam create-role `
  --role-name CustomerIntelligenceAppRunnerInstanceRole `
  --assume-role-policy-document file://apprunner-instance-trust-policy.json
```

Create `model-bucket-policy.json`, replacing `YOUR_BUCKET`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR_BUCKET",
        "arn:aws:s3:::YOUR_BUCKET/customer-intelligence/models/*"
      ]
    }
  ]
}
```

Attach it:

```powershell
aws iam put-role-policy `
  --role-name CustomerIntelligenceAppRunnerInstanceRole `
  --policy-name CustomerIntelligenceModelReadPolicy `
  --policy-document file://model-bucket-policy.json

aws iam get-role --role-name CustomerIntelligenceAppRunnerInstanceRole --query "Role.Arn" --output text
```

Save the returned ARN for the App Runner service creation step.

## 6. Create GitHub Actions Deploy Role

This role lets GitHub Actions push to ECR and update App Runner without storing AWS access keys.

In AWS IAM, create an OIDC identity provider for GitHub if your AWS account does not already have one:

- Provider URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`

Create `github-actions-trust-policy.json`, replacing `AWS_ACCOUNT_ID` and `Harsh1314h/customer-intelligence-api` if needed:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:Harsh1314h/customer-intelligence-api:*"
        }
      }
    }
  ]
}
```

Create the role:

```powershell
aws iam create-role `
  --role-name GitHubActionsCustomerIntelligenceDeployRole `
  --assume-role-policy-document file://github-actions-trust-policy.json
```

Create `github-actions-deploy-policy.json`, replacing `AWS_ACCOUNT_ID`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:CreateRepository",
        "ecr:DescribeRepositories",
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "apprunner:UpdateService",
        "apprunner:DescribeService",
        "iam:PassRole"
      ],
      "Resource": "*"
    }
  ]
}
```

Attach it:

```powershell
aws iam put-role-policy `
  --role-name GitHubActionsCustomerIntelligenceDeployRole `
  --policy-name CustomerIntelligenceDeployPolicy `
  --policy-document file://github-actions-deploy-policy.json

aws iam get-role --role-name GitHubActionsCustomerIntelligenceDeployRole --query "Role.Arn" --output text
```

Save the returned ARN. It becomes the GitHub secret `AWS_ROLE_TO_ASSUME`.

## 7. Create The First App Runner Service

The GitHub workflow updates App Runner after the service exists. For the first deployment, add only the `AWS_ROLE_TO_ASSUME` GitHub secret and push to `main`; the workflow will build and push the first image to ECR, then skip the App Runner update because `APP_RUNNER_SERVICE_ARN` does not exist yet.

After that first image exists in ECR, create the App Runner service manually.

In the AWS console:

1. Open App Runner.
2. Create service.
3. Source: Container registry.
4. Provider: Amazon ECR.
5. Choose `customer-intelligence-api`.
6. Port: `8080`.
7. Environment variables:
   - `CI_MODEL_ARTIFACT_URI=s3://YOUR_BUCKET/customer-intelligence/models/`
   - `CI_ALLOW_DEMO_MODELS=false`
8. Access role: `AppRunnerECRAccessRole`.
9. Instance role: `CustomerIntelligenceAppRunnerInstanceRole`.

After creation, copy the App Runner service ARN. It becomes the GitHub secret `APP_RUNNER_SERVICE_ARN`.

## 8. Add GitHub Secrets

Go to GitHub repo settings:

`Settings > Secrets and variables > Actions > New repository secret`

Add:

- `AWS_ROLE_TO_ASSUME`
- `APP_RUNNER_SERVICE_ARN`
- `APP_RUNNER_ACCESS_ROLE_ARN`
- `CI_MODEL_ARTIFACT_URI`

Example `CI_MODEL_ARTIFACT_URI`:

```text
s3://YOUR_BUCKET/customer-intelligence/models/
```

## 9. Deploy

Push to `main`:

```powershell
git add .
git commit -m "Deploy customer intelligence API on AWS"
git push origin main
```

GitHub Actions will:

1. Run tests.
2. Build the Docker image.
3. Push it to ECR.
4. Update App Runner.

After App Runner finishes deploying, open the service URL and test:

```text
/health
/docs
```
