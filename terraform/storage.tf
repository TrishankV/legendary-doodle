resource "google_storage_bucket" "paani" { 
    for_each = toset(var.storage_buckets)
    name = each.value
    location = "US-EAST1"
    storage_class = "STANDARD"
    
    uniform_bucket_level_access = true

    autoclass {
        enabled = true
    }
    hierarchical_namespace {
        enabled = true
    }

}
