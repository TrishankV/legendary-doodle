
# Creating a serverless function app 
 # FUCK MICROSOFT 
# resource "azurerm_service_plan" "function_app_plan" {
#     name = "conversion-pipeline"
#     resource_group_name = var.rgname
#     location = "canadacentral"
#     os_type = "Linux"
#     sku_name = "Y1"
# }

# # creating a linux function app

# resource "azurerm_linux_function_app" "piplinux" {
#     name = "function-app-243232341"
#     resource_group_name = var.rgname
#     location = "canadacentral"
#     tags = var.tags["aitag"]
#     service_plan_id = azurerm_service_plan.function_app_plan.id

#     storage_account_name = azurerm_storage_account.epubstorage.name
#     storage_account_access_key = azurerm_storage_account.epubstorage.primary_access_key

#     site_config {
#     application_stack {
#         python_version = "3.11"
#     }
#     }
#     app_settings = {
#         "DOC_AI_ENDPOINT" = azurerm_cognitive_account.res-0.endpoint
#         "DOC_AI_KEY" = azurerm_cognitive_account.res-0.primary_access_key
#         "AzureWebJobsStorage" = azurerm_storage_account.epubstorage.primary_connection_string
#         "FUNCTIONS_WORKER_RUNTIME" = "python"
#     }
# }

# Microsoft sint allowing app service on free tier so using logic apps instead 


resource "azurerm_logic_app_workflow" "logicapp" { 
    name = "fkmicrosoftlogicapp13"
    location = var.loc
    resource_group_name = var.rgname
    tags = var.tags["aitag"]

    parameters = {
        "$connections" = jsonencode({
            azureblob = {
                connectionId = azurerm_api_connection.conn.id
                connectionName = azurerm_api_connection.conn.name
                id = azurerm_api_connection.conn.id
                name = azurerm_api_connection.conn.managed_api_id
            }
        })
    }

}

resource "azurerm_api_connection" "conn" { 
    name = "con-azurerblob-prod"
    resource_group_name = var.rgname
    # location = var.loc
    display_name = "Blob storage Connection"

    managed_api_id = "/subscriptions/${data.azurerm_subscription.current.subscription_id}/providers/Microsoft.Web/locations/${var.loc}/managedApis/azureblob"
    parameter_values = {
        accountName = azurerm_storage_account.epubstorage.name
        accountKey = azurerm_storage_account.epubstorage.primary_access_key
    }
}