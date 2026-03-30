from django.db import models
from django.conf import settings
from django.db.models import F, Sum
from django.core.exceptions import ValidationError


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


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    image = models.ImageField(upload_to="categories/", null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    sku = models.CharField(max_length=50, blank=True, null=True)
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    unit = models.CharField(max_length=20, default="un")

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )

    image = models.ImageField(upload_to="products/", null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.sku or '-'})"


class TransferOrder(models.Model):
    from_branch = models.CharField(max_length=20, choices=Branch.choices, default=Branch.QUEIMADOS)
    to_branch = models.CharField(max_length=20, choices=Branch.choices, default=Branch.AUSTIN)

    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.DRAFT)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders_created"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    picking_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders_picking"
    )

    picking_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)

    notes_from_austin = models.TextField(blank=True, default="")

    # 🔥 status automático baseado nos itens
    @property
    def is_fully_sent(self):
        return all(item.is_fulfilled for item in self.items.all())

    @property
    def is_partially_sent(self):
        return any(item.qty_sent > 0 for item in self.items.all()) and not self.is_fully_sent

    def update_status_based_on_items(self):
        if not self.items.exists():
            return

        if self.is_fully_sent:
            self.status = OrderStatus.DISPATCHED

        elif self.is_partially_sent:
            self.status = OrderStatus.PICKING

        else:
            self.status = OrderStatus.SUBMITTED

        self.save(update_fields=["status"])

    def __str__(self):
        return f"Pedido #{self.id} {self.from_branch}->{self.to_branch} ({self.status})"


class TransferOrderItem(models.Model):
    order = models.ForeignKey(
        TransferOrder,
        on_delete=models.CASCADE,
        related_name="items"
    )

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

    @property
    def extra_qty(self):
        return max(0, self.qty_sent - self.qty_requested)

    def __str__(self):
        return f"{self.order_id} - {self.product.name}"


class OrderLog(models.Model):
    order = models.ForeignKey(
        TransferOrder,
        on_delete=models.CASCADE,
        related_name="logs"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    action = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.order.id} - {self.action}"


class Despacho(models.Model):
    order = models.ForeignKey("TransferOrder", related_name="despachos", on_delete=models.CASCADE)
    created_by = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    # 🔥 NOVO CAMPO
    is_complementar = models.BooleanField(default=False)

    def __str__(self):
        return f"Despacho {self.id} - Pedido {self.order.id}"
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Despacho #{self.id} - Pedido {self.order.id}"


class DespachoItem(models.Model):
    despacho = models.ForeignKey(
        Despacho,
        on_delete=models.CASCADE,
        related_name="itens"
    )

    order_item = models.ForeignKey(
        TransferOrderItem,
        on_delete=models.CASCADE
    )

    qty_sent_now = models.PositiveIntegerField()

    class Meta:
        unique_together = [("despacho", "order_item")]

    def save(self, *args, **kwargs):
        if self.qty_sent_now <= 0:
            raise ValueError("Quantidade deve ser maior que zero.")

        if self.qty_sent_now > self.order_item.missing_qty:
            raise ValueError("Quantidade maior que o faltante.")

        super().save(*args, **kwargs)

        self.order_item.qty_sent = F("qty_sent") + self.qty_sent_now
        self.order_item.save(update_fields=["qty_sent"])

        # 🔥 atualiza item
        self.order_item.refresh_from_db()

        # 🔥 pega order atualizado
        order = self.order_item.order
        order.refresh_from_db()



    def __str__(self):
        return f"{self.order_item.product.name} - {self.qty_sent_now}"