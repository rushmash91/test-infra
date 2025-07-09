# ACK Prow Helm Chart

This Helm chart deploys the Prow CI/CD system with ACK workflow extensions for Kubernetes.

## Overview

Prow is a Kubernetes-based CI/CD system used extensively in the Kubernetes ecosystem. This Helm chart includes:

- Core Prow components (deck, hook, sinker, etc.)
- Custom workflow-agent for ACK-specific workflows
- S3 integration for log storage
- RBAC configuration
- GitHub integration

## Prerequisites

- Kubernetes cluster (1.16+)
- Helm 3+
- AWS S3 bucket for log storage
- GitHub App or personal access token for GitHub integration

## Installation

### Add the Helm repository

```bash
# If published to a Helm repository
helm repo add ack-test-infra https://aws-controllers-k8s.github.io/test-infra/charts
helm repo update
```

### Prepare a values.yaml file

Create a custom values.yaml file with your configuration:

```yaml
github:
  organization: "your-github-org"
  bot:
    username: "your-bot-username"
    emailPrefix: "your-email-prefix"
  app:
    id: "your-github-app-id"
    privateKey: "your-github-app-private-key"
  hmacToken: "your-webhook-secret"
  cookieSecret: "your-cookie-secret"

aws:
  region: "us-west-2"
  s3:
    bucket: "your-s3-bucket-name"
    roleArn: "arn:aws:iam::123456789012:role/your-role"
```

### Install the chart

```bash
# Install from local chart
helm install ack-prow ./helm-chart -f your-values.yaml

# Or if published to a Helm repository
helm install ack-prow ack-test-infra/ack-prow -f your-values.yaml
```

## Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `namespaces.prow.create` | Create the Prow namespace | `true` |
| `namespaces.prow.name` | Name of the Prow namespace | `prow` |
| `namespaces.prowJobs.create` | Create the ProwJobs namespace | `true` |
| `namespaces.prowJobs.name` | Name of the ProwJobs namespace | `prow-jobs` |
| `github.organization` | GitHub organization name | `ack-prow-staging` |
| `github.bot.username` | GitHub bot username | `""` |
| `github.bot.emailPrefix` | GitHub bot email prefix | `""` |
| `github.app.id` | GitHub App ID | `""` |
| `github.app.privateKey` | GitHub App private key | `""` |
| `github.hmacToken` | HMAC token for webhook validation | `""` |
| `github.cookieSecret` | Cookie secret for the Deck UI | `""` |
| `aws.region` | AWS region | `us-west-2` |
| `aws.s3.bucket` | S3 bucket name for log storage | `ack-prow-staging-artifacts` |
| `aws.s3.roleArn` | IAM role ARN for S3 access | `""` |
| `components.deck.enabled` | Enable the Deck component | `true` |
| `components.hook.enabled` | Enable the Hook component | `true` |
| `components.sinker.enabled` | Enable the Sinker component | `true` |
| `components.horologium.enabled` | Enable the Horologium component | `true` |
| `components.tide.enabled` | Enable the Tide component | `true` |
| `components.prowControllerManager.enabled` | Enable the Prow Controller Manager | `true` |
| `components.crier.enabled` | Enable the Crier component | `true` |
| `workflowAgent.enabled` | Enable the workflow-agent component | `true` |

See [values.yaml](./values.yaml) for the full list of configurable parameters.

## S3 Configuration

For logs to be correctly stored in S3, make sure:

1. The S3 bucket exists and is configured correctly
2. The IAM role has proper permissions to access the bucket
3. The service account has the IAM role annotation
4. The S3 credentials secret is configured correctly

## GitHub Integration

This chart supports GitHub App authentication:

1. Create a GitHub App with the required permissions
2. Generate a private key for the app
3. Configure the values.yaml file with the app ID and private key
4. Set up webhooks to point to your Hook service

## AWS IAM Role for Service Accounts (IRSA)

To use IRSA for S3 access:

1. Create an IAM role with S3 access policies
2. Configure the trust relationship for your EKS cluster
3. Set the `aws.s3.roleArn` value to the role ARN
4. Leave the `aws.s3.credentials` fields empty

## License

Apache License 2.0