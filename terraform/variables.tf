variable "tags" {
    description = "To logically devide a resource group"
    type = map(map(string))
}


variable "storage_container_Names" {
    description = "The names of the storage container" 
    type = map(string)
}

variable "rgname" {
    description = "The name of the resource group"
    type = string
}

variable "loc" {
    description = "The location of the resource group"
    type = string
} 