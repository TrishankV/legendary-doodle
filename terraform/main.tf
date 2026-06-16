data "azurerm_subscription" "current" {}



terraform { 
    required_version = ">1.3.0" 
    required_providers { 
        azurerm = {
            source = "hashicorp/azurerm" 
            version = "4.66.0"

        }
    }
}

provider "azurerm" {
    features{}
}


resource "azurerm_cognitive_account" "res-0" {
  # custom_question_answering_search_service_key = "" # Masked sensitive attribute
  custom_subdomain_name                        = "pdftoepub2"
  dynamic_throttling_enabled                   = false
  fqdns                                        = []
  kind                                         = "FormRecognizer"
  local_auth_enabled                           = true
  location                                     = "eastus"
  name                                         = "PdftoEpub2"
  outbound_network_access_restricted           = false
  # primary_access_key                           = "" # Masked sensitive attribute
  project_management_enabled                   = false
  public_network_access_enabled                = true
  resource_group_name                          = "Trish"
  # secondary_access_key                         = "" # Masked sensitive attribute
  sku_name                                     = "F0"
  tags                                         = var.tags["aitag"]
  network_acls {
    # bypass         = ""
    default_action = "Allow"
    ip_rules       = []
  }
}

resource "azurerm_search_service" "res-1" {
    name               = "joogle" 
    location           = "eastus"
    resource_group_name = "Trish"
    sku          = "free"   
    tags     = var.tags["aitag"]

}

