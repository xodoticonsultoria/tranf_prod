from django.contrib import admin
from .models import Product, TransferOrder, TransferOrderItem

class TransferOrderItemInline(admin.TabularInline):
    model = TransferOrderItem
    extra = 0

@admin.register(TransferOrder)
class TransferOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "from_branch", "to_branch", "created_by", "created_at")
    list_filter = ("status", "from_branch", "to_branch")
    search_fields = ("id", "created_by__username")
    inlines = [TransferOrderItemInline]

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "active", "unit")
    search_fields = ("sku", "name")
    list_filter = ("active",)
