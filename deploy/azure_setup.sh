#!/usr/bin/env bash
#
# Provisions everything this project needs on Azure: a resource group,
# an Azure OpenAI resource + model deployment, an Azure AI Content Safety
# resource, a Log Analytics workspace + Application Insights, and an Azure
# Container Apps environment + the app itself.
#
# THIS SCRIPT WAS WRITTEN BUT NEVER RUN. The environment that wrote it has
# no `az` CLI and no Azure credentials, so none of these commands have been
# executed or verified against a real subscription. Read through it before
# running it -- treat every `az` invocation as a claim about the CLI's
# syntax and behavior, not a tested fact. Report back anything that's
# wrong and it'll get fixed.
#
# Run this with `bash deploy/azure_setup.sh`, from the repo root, after
# `az login`. It pauses and prints an estimated cost before every step that
# creates a billable resource, and waits for you to press Enter -- Ctrl+C
# at any point to stop. Nothing here runs unattended.
#
# ─── Before you run this ─────────────────────────────────────────────────
#
#   1. You need an actual Azure subscription. If you have a .edu email,
#      Azure for Students (azure.microsoft.com/free/students) gives you
#      $100 credit with no credit card required. Otherwise, a new Azure
#      account gets $200 free credit for 30 days (requires a card on file,
#      but nothing is charged unless you exceed the credit and explicitly
#      upgrade). Either covers this whole project comfortably -- everything
#      below is designed to be free-tier or a few dollars at most.
#
#   2. Azure OpenAI specifically requires your subscription to be approved
#      for access (a one-time registration, usually instant to a few
#      hours for standard use cases): https://aka.ms/oai/access
#
#   3. Install the Azure CLI if you don't have it: https://learn.microsoft.com/cli/azure/install-azure-cli
#      Then run `az login` and confirm you're on the right subscription
#      with `az account show`.

set -euo pipefail

# ─── Configuration -- edit these before running ──────────────────────────

RESOURCE_GROUP="rg-rag-assistant"
LOCATION="eastus"                      # Azure OpenAI + Content Safety region availability varies -- check aka.ms/oai/access if eastus doesn't work for you
UNIQUE_SUFFIX="$(date +%s | tail -c 6)" # keeps resource names globally unique without you having to think about it

AOAI_NAME="aoai-rag-${UNIQUE_SUFFIX}"
AOAI_DEPLOYMENT_NAME="gpt-41-mini"
AOAI_MODEL="gpt-4.1-mini"
AOAI_MODEL_VERSION="2025-04-14"        # gpt-4o-mini had 0 quota on an Azure for Students sub; gpt-4.1-mini (GlobalStandard) worked. check `az cognitiveservices account list-models` for what's current in your region

CONTENT_SAFETY_NAME="safety-rag-${UNIQUE_SUFFIX}"

LOG_ANALYTICS_NAME="log-rag-${UNIQUE_SUFFIX}"
APP_INSIGHTS_NAME="appi-rag-${UNIQUE_SUFFIX}"

CONTAINERAPPS_ENV="env-rag-${UNIQUE_SUFFIX}"
CONTAINER_APP_NAME="rag-assistant"

# Container image source. Azure Container Registry (Basic tier) costs
# about $5/month, continuously, which isn't free-tier or trivial for a
# portfolio project you might not touch again for months. Using a free
# registry instead avoids that recurring cost -- pick one:
#   - ghcr.io  (GitHub Container Registry, free for public images)
#   - Docker Hub (free public repos)
# Set IMAGE to wherever you actually pushed the built image; this script
# does not build or push it for you -- see README "Deployment" for the
# `docker build` / `docker push` commands.
IMAGE="ghcr.io/YOUR_GITHUB_USERNAME/rag-assistant:latest"

confirm_cost() {
    echo ""
    echo "─────────────────────────────────────────────────────────"
    echo "  $1"
    echo "  Estimated cost: $2"
    echo "─────────────────────────────────────────────────────────"
    read -r -p "Press Enter to continue, or Ctrl+C to stop here... "
}

# ─── 1. Resource group ────────────────────────────────────────────────────

confirm_cost "Create resource group '${RESOURCE_GROUP}'" \
    "\$0 -- resource groups themselves are free, only what's inside costs anything"

az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

# ─── 2. Azure OpenAI resource + gpt-4o-mini deployment ───────────────────

confirm_cost "Create Azure OpenAI resource '${AOAI_NAME}' + deploy ${AOAI_MODEL}" \
    "\$0 to create the resource itself; usage is pay-per-token. gpt-4o-mini is
    Azure OpenAI's cheapest current chat model (as of when this was written)
    at a fraction of a cent per typical request. A few dozen test calls
    while building this project should be well under \$1 total, covered by
    free credit either way."

az cognitiveservices account create \
    --name "$AOAI_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --kind OpenAI \
    --sku S0 \
    --custom-domain "$AOAI_NAME"

az cognitiveservices account deployment create \
    --name "$AOAI_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --deployment-name "$AOAI_DEPLOYMENT_NAME" \
    --model-name "$AOAI_MODEL" \
    --model-version "$AOAI_MODEL_VERSION" \
    --model-format OpenAI \
    --sku-capacity 10 \
    --sku-name "GlobalStandard"

AOAI_ENDPOINT=$(az cognitiveservices account show \
    --name "$AOAI_NAME" --resource-group "$RESOURCE_GROUP" \
    --query "properties.endpoint" -o tsv)
AOAI_KEY=$(az cognitiveservices account keys list \
    --name "$AOAI_NAME" --resource-group "$RESOURCE_GROUP" \
    --query "key1" -o tsv)

echo "Azure OpenAI endpoint: $AOAI_ENDPOINT"
echo "(key retrieved, not printed -- it's used directly below)"

# ─── 3. Azure AI Content Safety ───────────────────────────────────────────

confirm_cost "Create Content Safety resource '${CONTENT_SAFETY_NAME}'" \
    "\$0 on the F0 (free) tier -- 5,000 text records/month included. This
    project's traffic during development and demoing is nowhere near that.
    If you exceed it, the S0 tier is per-1,000-records pricing; check
    https://azure.microsoft.com/pricing/details/content-safety/ for current rates."

az cognitiveservices account create \
    --name "$CONTENT_SAFETY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --kind ContentSafety \
    --sku F0

CONTENT_SAFETY_ENDPOINT=$(az cognitiveservices account show \
    --name "$CONTENT_SAFETY_NAME" --resource-group "$RESOURCE_GROUP" \
    --query "properties.endpoint" -o tsv)
CONTENT_SAFETY_KEY=$(az cognitiveservices account keys list \
    --name "$CONTENT_SAFETY_NAME" --resource-group "$RESOURCE_GROUP" \
    --query "key1" -o tsv)

echo "Content Safety endpoint: $CONTENT_SAFETY_ENDPOINT"

# ─── 4. Log Analytics + Application Insights ─────────────────────────────

confirm_cost "Create Log Analytics workspace + Application Insights" \
    "\$0 in practice for this project's volume -- first 5 GB/month of
    ingested log data is free, and a demo project running occasionally
    won't come close to that. Beyond 5 GB it's pay-per-GB; check
    https://azure.microsoft.com/pricing/details/monitor/ for current rates."

az monitor log-analytics workspace create \
    --resource-group "$RESOURCE_GROUP" \
    --workspace-name "$LOG_ANALYTICS_NAME" \
    --location "$LOCATION"

LOG_ANALYTICS_ID=$(az monitor log-analytics workspace show \
    --resource-group "$RESOURCE_GROUP" --workspace-name "$LOG_ANALYTICS_NAME" \
    --query "customerId" -o tsv)

az monitor app-insights component create \
    --app "$APP_INSIGHTS_NAME" \
    --location "$LOCATION" \
    --resource-group "$RESOURCE_GROUP" \
    --workspace "$LOG_ANALYTICS_NAME"

APPINSIGHTS_CONNECTION_STRING=$(az monitor app-insights component show \
    --app "$APP_INSIGHTS_NAME" --resource-group "$RESOURCE_GROUP" \
    --query "connectionString" -o tsv)

echo "Application Insights connection string retrieved (not printed)."

# ─── 5. Container Apps environment + the app itself ──────────────────────

confirm_cost "Create Container Apps environment + deploy '${CONTAINER_APP_NAME}'" \
    "\$0 in practice for a low-traffic demo -- Container Apps' Consumption
    plan includes 180,000 vCPU-seconds and 360,000 GiB-seconds free per
    month, plus 2 million free requests. This app idling most of the time
    with occasional test traffic stays inside that. Sustained real traffic
    would cost pay-as-you-go beyond the free grant; check
    https://azure.microsoft.com/pricing/details/container-apps/ for current rates."

az containerapp env create \
    --name "$CONTAINERAPPS_ENV" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --logs-workspace-id "$LOG_ANALYTICS_ID"

az containerapp create \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$CONTAINERAPPS_ENV" \
    --image "$IMAGE" \
    --target-port 8000 \
    --ingress external \
    --min-replicas 0 \
    --max-replicas 2 \
    --cpu 1.0 \
    --memory 2.0Gi \
    --env-vars \
        "AZURE_OPENAI_ENDPOINT=$AOAI_ENDPOINT" \
        "AZURE_OPENAI_API_KEY=$AOAI_KEY" \
        "AZURE_OPENAI_DEPLOYMENT=$AOAI_DEPLOYMENT_NAME" \
        "AZURE_OPENAI_API_VERSION=2024-10-21" \
        "AZURE_CONTENT_SAFETY_ENDPOINT=$CONTENT_SAFETY_ENDPOINT" \
        "AZURE_CONTENT_SAFETY_KEY=$CONTENT_SAFETY_KEY" \
        "APPLICATIONINSIGHTS_CONNECTION_STRING=$APPINSIGHTS_CONNECTION_STRING"

# --min-replicas 0 means the app scales to zero and costs nothing when idle
# (there's a cold-start delay -- including re-downloading nothing, since the
# embedding model is baked into the image -- but the container itself has
# to start) rather than running, and being billed, 24/7.

echo ""
echo "Done. Note two things this script does NOT set up (see README for why):"
echo "  1. Persistent storage -- ChromaDB and the experiments SQLite DB reset"
echo "     on every restart/new revision without an Azure Files volume mount."
echo "  2. A container registry -- IMAGE above must point at wherever you"
echo "     actually pushed the built image (ghcr.io, Docker Hub, or ACR)."
echo ""
echo "App URL:"
az containerapp show \
    --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" \
    --query "properties.configuration.ingress.fqdn" -o tsv
