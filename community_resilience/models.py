from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models


def validate_completion_image_size(image):
    if image.size > 5 * 1024 * 1024:
        raise ValidationError('The proof image must be 5 MB or smaller.')


class CommunityUser(AbstractUser):
    class Role(models.TextChoices):
        LEADER = 'leader', 'Community leader'
        VOLUNTEER = 'volunteer', 'Volunteer'
        BENEFICIARY = 'beneficiary', 'Beneficiary'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VOLUNTEER,
    )

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def can_manage_community(self):
        return self.is_superuser or self.role == self.Role.LEADER


class PreparednessTask(models.Model):
    class Category(models.TextChoices):
        EVACUATION = 'evacuation', 'Evacuation'
        WATER = 'water', 'Water conservation'
        DISTRIBUTION = 'distribution', 'Supply distribution'
        SANDBAG = 'sandbag', 'Sandbag preparation'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In progress'
        DONE = 'done', 'Done'

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    location = models.CharField(max_length=160, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    due_date = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        'CommunityUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='preparedness_tasks',
    )
    created_by = models.ForeignKey(
        'CommunityUser',
        on_delete=models.PROTECT,
        related_name='created_preparedness_tasks',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('due_date', 'created_at')
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(latitude__isnull=True, longitude__isnull=True)
                    | models.Q(latitude__isnull=False, longitude__isnull=False)
                ),
                name='task_coordinates_both_or_neither',
            ),
            models.CheckConstraint(
                condition=models.Q(latitude__isnull=True) | models.Q(latitude__gte=-90, latitude__lte=90),
                name='task_latitude_in_range',
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__isnull=True) | models.Q(longitude__gte=-180, longitude__lte=180),
                name='task_longitude_in_range',
            ),
        ]

    def __str__(self):
        return self.title


class ResourceItem(models.Model):
    class Category(models.TextChoices):
        WATER = 'water', 'Water'
        FOOD = 'food', 'Food'
        MEDICAL = 'medical', 'Medical'
        SHELTER = 'shelter', 'Shelter'
        SANDBAGS = 'sandbags', 'Sandbags'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    unit = models.CharField(max_length=40, help_text='For example: liters, packs, or pieces')
    location = models.CharField(max_length=160)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    created_by = models.ForeignKey(
        'CommunityUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_resource_items',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('category', 'name')
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name='resource_quantity_nonnegative'),
            models.CheckConstraint(
                condition=(
                    models.Q(latitude__isnull=True, longitude__isnull=True)
                    | models.Q(latitude__isnull=False, longitude__isnull=False)
                ),
                name='resource_coordinates_both_or_neither',
            ),
            models.CheckConstraint(
                condition=models.Q(latitude__isnull=True) | models.Q(latitude__gte=-90, latitude__lte=90),
                name='resource_latitude_in_range',
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__isnull=True) | models.Q(longitude__gte=-180, longitude__lte=180),
                name='resource_longitude_in_range',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.quantity} {self.unit})'


class BeneficiaryNeed(models.Model):
    class NeedType(models.TextChoices):
        WATER = 'water', 'Drinking water'
        FOOD = 'food', 'Food'
        SHELTER = 'shelter', 'Shelter'
        MEDICAL = 'medical', 'Medical support'
        EVACUATION = 'evacuation', 'Evacuation assistance'
        OTHER = 'other', 'Other'

    class Priority(models.TextChoices):
        ROUTINE = 'routine', 'Routine'
        URGENT = 'urgent', 'Urgent'
        CRITICAL = 'critical', 'Critical'

    class Status(models.TextChoices):
        OPEN = 'open', 'Needs assistance'
        IN_PROGRESS = 'in_progress', 'Assistance in progress'
        FULFILLED = 'fulfilled', 'Done (fulfilled)'

    barangay = models.CharField(max_length=120)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    household_size = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    need_type = models.CharField(max_length=20, choices=NeedType.choices)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.ROUTINE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    reported_by = models.ForeignKey(
        'CommunityUser',
        on_delete=models.PROTECT,
        related_name='reported_needs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('priority', '-created_at')
        constraints = [
            models.CheckConstraint(condition=models.Q(household_size__gte=1), name='need_household_size_positive'),
            models.CheckConstraint(
                condition=(
                    models.Q(latitude__isnull=True, longitude__isnull=True)
                    | models.Q(latitude__isnull=False, longitude__isnull=False)
                ),
                name='need_coordinates_both_or_neither',
            ),
            models.CheckConstraint(
                condition=models.Q(latitude__isnull=True) | models.Q(latitude__gte=-90, latitude__lte=90),
                name='need_latitude_in_range',
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__isnull=True) | models.Q(longitude__gte=-180, longitude__lte=180),
                name='need_longitude_in_range',
            ),
        ]

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None

    def __str__(self):
        return f'{self.get_need_type_display()} need in {self.barangay}'


class NeedCompletionSubmission(models.Model):
    class ReviewStatus(models.TextChoices):
        PENDING = 'pending', 'Awaiting review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Needs another submission'

    need = models.ForeignKey(
        BeneficiaryNeed,
        on_delete=models.CASCADE,
        related_name='completion_submissions',
    )
    submitted_by = models.ForeignKey(
        'CommunityUser',
        on_delete=models.PROTECT,
        related_name='need_completion_submissions',
    )
    proof_image = models.ImageField(
        upload_to='need_completion_proofs/%Y/%m/',
        validators=[
            FileExtensionValidator(allowed_extensions=('jpg', 'jpeg', 'png', 'webp')),
            validate_completion_image_size,
        ],
    )
    review_status = models.CharField(
        max_length=10,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        'CommunityUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_need_completions',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ('-submitted_at',)
        verbose_name = 'need completion submission'
        verbose_name_plural = 'need completion submissions'
        constraints = [
            models.UniqueConstraint(
                fields=('need',),
                condition=models.Q(review_status='pending'),
                name='one_pending_completion_per_need',
            ),
        ]

    def __str__(self):
        return f'Completion for {self.need} ({self.get_review_status_display()})'
