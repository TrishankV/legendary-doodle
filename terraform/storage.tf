resource "azurerm_storage_account" "epubstorage" {
    name = "forepub12"
    location = "eastus"
    resource_group_name = "Trish"
    account_tier = "Standard"
    account_replication_type = "LRS"
    account_kind = "StorageV2"
    # tags = var.tags["storagetag"]
    
  network_rules {
    default_action = "Allow"
    bypass         = ["AzureServices"]
  }


}

resource "azurerm_storage_container" "containers" { 
    for_each = var.storage_container_Names 
    name = each.value
    storage_account_id = azurerm_storage_account.epubstorage.id 
    container_access_type = "private"
    # tags = var.tags["storagetag"]

}

