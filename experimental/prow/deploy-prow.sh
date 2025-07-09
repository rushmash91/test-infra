#!/bin/bash

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
HELM_CHART_DIR="${SCRIPT_DIR}/helm-chart"
VALUES_FILE="${SCRIPT_DIR}/values.yaml"
RELEASE_NAME="ack-prow"
NAMESPACE="prow"

# Display help message
function show_help() {
  echo "Usage: $0 [OPTIONS]"
  echo ""
  echo "Deploy Prow CI/CD system using Helm"
  echo ""
  echo "Options:"
  echo "  -h, --help                 Display this help message"
  echo "  -n, --namespace NAME       Namespace to deploy Prow (default: prow)"
  echo "  -r, --release-name NAME    Helm release name (default: ack-prow)"
  echo "  -v, --values FILE          Values file (default: ./values.yaml)"
  echo "  -d, --dry-run              Perform a dry-run deployment"
  echo "  -u, --upgrade              Upgrade an existing deployment"
  echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -h|--help)
      show_help
      exit 0
      ;;
    -n|--namespace)
      NAMESPACE="$2"
      shift
      shift
      ;;
    -r|--release-name)
      RELEASE_NAME="$2"
      shift
      shift
      ;;
    -v|--values)
      VALUES_FILE="$2"
      shift
      shift
      ;;
    -d|--dry-run)
      DRY_RUN="--dry-run"
      shift
      ;;
    -u|--upgrade)
      UPGRADE="true"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
done

# Check if values file exists
if [ ! -f "${VALUES_FILE}" ]; then
  echo "Values file not found: ${VALUES_FILE}"
  echo "Creating a sample values.yaml file..."
  cat > "${VALUES_FILE}" << EOF
# Sample values.yaml file for ACK Prow Helm chart
# Edit this file with your specific configuration values

github:
  organization: "ack-prow-staging"
  bot:
    username: ""
    emailPrefix: ""
  app:
    id: ""
    privateKey: ""
  hmacToken: ""
  cookieSecret: ""

aws:
  region: "us-west-2"
  s3:
    bucket: "ack-prow-staging-artifacts"
    roleArn: "arn:aws:iam::086987147623:role/workflow-agent-role"
EOF
  echo "Created sample values.yaml file at ${VALUES_FILE}"
  echo "Please edit the file with your specific configuration before proceeding."
  exit 1
fi

# Deploy or upgrade the Helm chart
if [ "${UPGRADE}" == "true" ]; then
  echo "Upgrading Prow Helm chart..."
  helm upgrade ${RELEASE_NAME} ${HELM_CHART_DIR} \
    --namespace ${NAMESPACE} \
    --create-namespace \
    --values ${VALUES_FILE} \
    ${DRY_RUN}
else
  echo "Installing Prow Helm chart..."
  helm install ${RELEASE_NAME} ${HELM_CHART_DIR} \
    --namespace ${NAMESPACE} \
    --create-namespace \
    --values ${VALUES_FILE} \
    ${DRY_RUN}
fi

echo "Done!"