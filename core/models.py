from django.db import models
from django.conf import settings

class Branch(models.TextChoices):
    AUSTIN = "AUSTIN", "Austin (Base)"
    QUEIMADOS = "QUEIMADOS", "Queimados (Filial)"

class OrderStatus(models.TextChoices):
    DRAFT = "DRAFT", "Rascunho"
    SUBMITTED = "SUBMITTED", "Enviado para Austin"
    PICKING = "PICKING", "Em separação"
    DISPATCHED = "DISPATCHED", "Despachado/Enviado"
    RECEIVED = "RECEIVED", "Recebido (confirmado)"
    CANCELLED = "CANCELLED", "Cancelado"

class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    unit = models.CharField(max_length=20, default="un")

    def __str__(self):
        return f"{self.name} ({self.sku})"

class TransferOrder(models.Model):
    from_branch = models.CharField(max_length=20, choices=Branch.choices, default=Branch.QUEIMADOS)
    to_branch = models.CharField(max_length=20, choices=Branch.choices, default=Branch.AUSTIN)

    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.DRAFT)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders_created")
    created_at = models.DateTimeField(auto_now_add=True)

    picking_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="orders_picking")
    picking_at = models.DateTimeField(null=True, blank=True)

    dispatched_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)

    notes_from_austin = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Pedido #{self.id} {self.from_branch}->{self.to_branch} ({self.status})"

class TransferOrderItem(models.Model):
    order = models.ForeignKey(TransferOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)

    qty_requested = models.PositiveIntegerField()
    qty_sent = models.PositiveIntegerField(default=0)

    note = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        unique_together = [("order", "product")]

    @property
    def missing_qty(self):
        return max(0, self.qty_requested - self.qty_sent)

    @property
    def is_fulfilled(self):
        return self.qty_sent >= self.qty_requested

    def __str__(self):
        return f"{self.order_id} - {self.product.name}"
