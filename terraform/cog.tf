
resource "azurerm_api_connection" "conn" {
  display_name        = "new_conn_a06e3"
  managed_api_id      = "/subscriptions/dbc98806-131e-499d-b054-fbe202541a2d/providers/Microsoft.Web/locations/eastus/managedApis/azureblob"
  name                = "azureblob"
  parameter_values    = {}
  resource_group_name = "Trish"
  tags                = {}
}

resource "azurerm_logic_app_workflow" "logicapp" {
  enabled                            = true
  location                           = "eastus"
  name                               = "fkmicrosoftlogicapp13"
  parameters = {
    "$connections" = "{\"azureblob\":{\"connectionId\":\"/subscriptions/dbc98806-131e-499d-b054-fbe202541a2d/resourceGroups/Trish/providers/Microsoft.Web/connections/azureblob\",\"connectionName\":\"azureblob\",\"connectionProperties\":{},\"id\":\"/subscriptions/dbc98806-131e-499d-b054-fbe202541a2d/providers/Microsoft.Web/locations/eastus/managedApis/azureblob\"}}"
  }
  resource_group_name = "Trish"
  tags = {
    Name = "Artificial Intelligence FOudnary Services"
  }
  workflow_parameters = {
    "$connections" = "{\"defaultValue\":{},\"type\":\"Object\"}"
  }
  workflow_schema  = "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#"
  workflow_version = "1.0.0.0"
  identity {
    identity_ids = []
    type         = "SystemAssigned"
  }
}
resource "azurerm_logic_app_trigger_custom" "trrgr" {
  body = jsonencode({
    inputs = {
      host = {
        connection = {
          name = "@parameters('$connections')['azureblob']['connectionId']"
        }
      }
      method = "get"
      path   = "/v2/datasets/@{encodeURIComponent(encodeURIComponent('AccountNameFromSettings'))}/triggers/batch/onupdatedfile"
      queries = {
        checkBothCreatedAndModifiedDateTime = false
        folderId                            = "JTJmcGRmc2FuZGltYWdlcw=="
        maxFileCount                        = 10
      }
    }
    metadata = {
      "JTJmcGRmc2FuZGltYWdlcw==" = "/pdfsandimages"
    }
    recurrence = {
      frequency = "Minute"
      interval  = 3
    }
    splitOn = "@triggerBody()"
    type    = "ApiConnection"
  })
  logic_app_id = azurerm_logic_app_workflow.logicapp.id
  name         = "When_a_blob_is_added_or_modified_(properties_only)_(V2)"
}
