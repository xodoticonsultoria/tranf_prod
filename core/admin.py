from django.contrib import admin
from .models import Category, Product, TransferOrder, TransferOrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "active")
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "sku", "name", "category", "active")
    list_filter = ("active", "category")
    search_fields = ("name", "sku")


class TransferOrderItemInline(admin.TabularInline):
    model = TransferOrderItem
    extra = 0


@admin.register(TransferOrder)
class TransferOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "from_branch", "to_branch", "status", "created_at")
    list_filter = ("status", "from_branch", "to_branch")
    inlines = [TransferOrderItemInline]
