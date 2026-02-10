from django.contrib import admin
from .models import Category, Product, TransferOrder, TransferOrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "active")
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "unit", "active", "category")
    list_filter = ("active", "category")
    search_fields = ("name", "sku")
    list_select_related = ("category",)


class TransferOrderItemInline(admin.TabularInline):
    model = TransferOrderItem
    extra = 0


@admin.register(TransferOrder)
class TransferOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "from_branch", "to_branch", "created_by", "created_at")
    list_filter = ("status", "from_branch", "to_branch")
    search_fields = ("id", "created_by__username")
    inlines = [TransferOrderItemInline]
