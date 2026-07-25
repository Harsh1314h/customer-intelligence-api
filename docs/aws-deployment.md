# AWS Deployment Guide

This project deploys to AWS with:

- Amazon ECR for the Docker image.
- Amazon S3 for trained model artifacts.
- Amazon ECS Express Mode for the public container service.
- GitHub Actions with AWS OIDC for CI/CD.

Important: AWS App Runner is no longer accepting new customers after April 30, 2026, so this project now uses ECS Express Mode instead.

Default region:

```text
ap-south-1
```

## Current AWS Assets

S3 model artifacts:

```text
s3://customer-intelligence-models-harsh1314h/customer-intelligence/models/
```

AWS account:

```text
188947281989
```

GitHub repository:

```text
Harsh1314h/customer-intelligence-api
```

## GitHub Secrets Needed

Add these in:

```text
GitHub repo > Settings > Secrets and variables > Actions
```

Required secrets:

```text
AWS_ROLE_TO_ASSUME
CI_MODEL_ARTIFACT_URI
ECS_TASK_EXECUTION_ROLE_ARN
ECS_INFRASTRUCTURE_ROLE_ARN
```

Values:

```text
CI_MODEL_ARTIFACT_URI=s3://customer-intelligence-models-harsh1314h/customer-intelligence/models/
```

`AWS_ROLE_TO_ASSUME` is the GitHub Actions deploy role ARN.

`ECS_TASK_EXECUTION_ROLE_ARN` is the ECS task role/execution role ARN.

`ECS_INFRASTRUCTURE_ROLE_ARN` is the ECS infrastructure role ARN.

## 1. Create ECR Repository

Run from local PowerShell after `aws configure`:

```powershell
$env:AWS_REGION="ap-south-1"
aws ecr create-repository --repository-name customer-intelligence-api --region $env:AWS_REGION --image-scanning-configuration scanOnPush=true
```

If the repository already exists, continue.

## 2. Create ECS Task Execution Role

Create the ECS task trust policy:

```powershell
@'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
'@ | Set-Content ecs-task-trust-policy.json
```

Create role:

```powershell
aws iam create-role --role-name CustomerIntelligenceECSTaskExecutionRole --assume-role-policy-document file://ecs-task-trust-policy.json
```

Attach ECS execution policy:

```powershell
aws iam attach-role-policy --role-name CustomerIntelligenceECSTaskExecutionRole --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

Create S3 model-read policy:

```powershell
@'
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
        "arn:aws:s3:::customer-intelligence-models-harsh1314h",
        "arn:aws:s3:::customer-intelligence-models-harsh1314h/customer-intelligence/models/*"
      ]
    }
  ]
}
'@ | Set-Content ecs-model-bucket-policy.json
```

Attach S3 model-read policy:

```powershell
aws iam put-role-policy --role-name CustomerIntelligenceECSTaskExecutionRole --policy-name CustomerIntelligenceModelReadPolicy --policy-document file://ecs-model-bucket-policy.json
```

Get role ARN:

```powershell
aws iam get-role --role-name CustomerIntelligenceECSTaskExecutionRole --query "Role.Arn" --output text
```

Use this as GitHub secret:

```text
ECS_TASK_EXECUTION_ROLE_ARN
```

## 3. Create ECS Infrastructure Role

Create trust policy:

```powershell
@'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
'@ | Set-Content ecs-infrastructure-trust-policy.json
```

Create role:

```powershell
aws iam create-role --role-name CustomerIntelligenceECSInfrastructureRole --assume-role-policy-document file://ecs-infrastructure-trust-policy.json
```

Attach managed infrastructure role policy:

```powershell
aws iam attach-role-policy --role-name CustomerIntelligenceECSInfrastructureRole --policy-arn arn:aws:iam::aws:policy/AmazonECSInfrastructureRolePolicyForManagedInstances
```

Get role ARN:

```powershell
aws iam get-role --role-name CustomerIntelligenceECSInfrastructureRole --query "Role.Arn" --output text
```

Use this as GitHub secret:

```text
ECS_INFRASTRUCTURE_ROLE_ARN
```

## 4. Update GitHub Actions Deploy Role

The GitHub role must be allowed to push to ECR, deploy ECS Express services, and pass the ECS roles.

Create/update policy:

```powershell
@'
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
        "ecs:CreateCluster",
        "ecs:DescribeClusters",
        "ecs:RegisterTaskDefinition",
        "ecs:DeregisterTaskDefinition",
        "ecs:DescribeTaskDefinition",
        "ecs:CreateService",
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:TagResource",
        "ecs:ListServices"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": [
        "arn:aws:iam::188947281989:role/CustomerIntelligenceECSTaskExecutionRole",
        "arn:aws:iam::188947281989:role/CustomerIntelligenceECSInfrastructureRole"
      ]
    }
  ]
}
'@ | Set-Content github-actions-deploy-policy.json
```

Attach policy:

```powershell
aws iam put-role-policy --role-name GitHubActionsCustomerIntelligenceDeployRole --policy-name CustomerIntelligenceDeployPolicy --policy-document file://github-actions-deploy-policy.json
```

## 5. Deploy

Add/confirm GitHub secrets:

```text
AWS_ROLE_TO_ASSUME=arn:aws:iam::188947281989:role/GitHubActionsCustomerIntelligenceDeployRole
CI_MODEL_ARTIFACT_URI=s3://customer-intelligence-models-harsh1314h/customer-intelligence/models/
ECS_TASK_EXECUTION_ROLE_ARN=arn:aws:iam::188947281989:role/CustomerIntelligenceECSTaskExecutionRole
ECS_INFRASTRUCTURE_ROLE_ARN=arn:aws:iam::188947281989:role/CustomerIntelligenceECSInfrastructureRole
```

Push to `main` or rerun GitHub Actions.

The workflow will:

1. Run tests.
2. Build Docker image.
3. Push image to ECR.
4. Deploy or update the ECS Express service.

## 6. Verify

After GitHub Actions succeeds, open the service endpoint shown in the ECS console and test:

```text
/health
/docs
```

Expected `/health` result includes:

```json
"demo_mode": false
```
