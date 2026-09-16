#!/usr/bin/env bash
#
# Deletes the entire resource group created by azure_setup.sh -- every
# resource inside it (Azure OpenAI, Content Safety, Container Apps
# environment, Log Analytics, Application Insights) goes with it. This is
# the single most useful cost-control step for a portfolio project: delete
# the resource group when you're not actively demoing it, recreate it
# (rerun azure_setup.sh) when you need it again.
#
# THIS SCRIPT WAS WRITTEN BUT NEVER RUN, same caveat as azure_setup.sh.
#
# Usage: bash deploy/azure_teardown.sh rg-rag-assistant

set -euo pipefail

RESOURCE_GROUP="${1:?Usage: azure_teardown.sh <resource-group-name>}"

echo "This will permanently delete resource group '$RESOURCE_GROUP' and"
echo "EVERYTHING in it. This cannot be undone."
read -r -p "Type the resource group name to confirm: " confirm_name

if [[ "$confirm_name" != "$RESOURCE_GROUP" ]]; then
    echo "Name didn't match. Aborting."
    exit 1
fi

az group delete --name "$RESOURCE_GROUP" --yes --no-wait

echo "Deletion started (--no-wait). Check progress with:"
echo "  az group show --name $RESOURCE_GROUP"
echo "(it will 404 once fully deleted, which can take a few minutes)"
