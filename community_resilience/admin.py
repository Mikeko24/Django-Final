from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import BeneficiaryNeed, CommunityUser, NeedCompletionSubmission, PreparednessTask, ResourceItem


@admin.register(CommunityUser)
class CommunityUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('Community role', {'fields': ('role',)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Community role', {'fields': ('role',)}),)
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active')


@admin.register(PreparednessTask)
class PreparednessTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'status', 'priority', 'assigned_to', 'due_date')
    list_filter = ('category', 'status', 'priority')
    search_fields = ('title', 'description', 'location')


@admin.register(ResourceItem)
class ResourceItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'unit', 'location', 'updated_at')
    list_filter = ('category',)
    search_fields = ('name', 'location')


@admin.register(BeneficiaryNeed)
class BeneficiaryNeedAdmin(admin.ModelAdmin):
    list_display = ('need_type', 'barangay', 'household_size', 'priority', 'status', 'created_at')
    list_filter = ('need_type', 'priority', 'status')
    search_fields = ('barangay', 'description')


@admin.register(NeedCompletionSubmission)
class NeedCompletionSubmissionAdmin(admin.ModelAdmin):
    list_display = ('need', 'submitted_by', 'submitted_at', 'review_status', 'reviewed_by', 'reviewed_at')
    list_filter = ('review_status', 'submitted_at')
    search_fields = ('need__barangay', 'need__description', 'submitted_by__username')
    readonly_fields = ('need', 'submitted_by', 'submitted_at', 'proof_preview', 'reviewed_by', 'reviewed_at')
    fields = (
        'need',
        'submitted_by',
        'submitted_at',
        'proof_preview',
        'review_status',
        'review_notes',
        'reviewed_by',
        'reviewed_at',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'need',
            'submitted_by',
            'reviewed_by',
        )

    @admin.display(description='Completion photo')
    def proof_preview(self, obj):
        if not obj or not obj.pk:
            return 'Save the submission before reviewing its image.'
        proof_url = reverse('need-completion-proof', args=(obj.pk,))
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Open submitted image</a>',
            proof_url,
        )

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = NeedCompletionSubmission.objects.get(pk=obj.pk).review_status

        status_changed = change and obj.review_status != previous_status
        if status_changed and obj.review_status != NeedCompletionSubmission.ReviewStatus.PENDING:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        elif status_changed:
            obj.reviewed_by = None
            obj.reviewed_at = None

        super().save_model(request, obj, form, change)

        if status_changed and obj.review_status == NeedCompletionSubmission.ReviewStatus.APPROVED:
            BeneficiaryNeed.objects.filter(pk=obj.need_id).update(
                status=BeneficiaryNeed.Status.FULFILLED,
                updated_at=timezone.now(),
            )
        elif (
            status_changed
            and previous_status == NeedCompletionSubmission.ReviewStatus.APPROVED
            and obj.review_status == NeedCompletionSubmission.ReviewStatus.REJECTED
        ):
            BeneficiaryNeed.objects.filter(
                pk=obj.need_id,
                status=BeneficiaryNeed.Status.FULFILLED,
            ).update(status=BeneficiaryNeed.Status.IN_PROGRESS, updated_at=timezone.now())
