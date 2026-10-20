import mimetypes

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Value, When
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .forms import (
    BeneficiaryNeedForm,
    BeneficiaryNeedUpdateForm,
    NeedCompletionSubmissionForm,
    PreparednessTaskForm,
    ResourceItemForm,
    TaskStatusForm,
)
from .models import BeneficiaryNeed, CommunityUser, NeedCompletionSubmission, PreparednessTask, ResourceItem


def marker(
    kind,
    latitude,
    longitude,
    title,
    detail,
    *,
    posted_by=None,
    posted_by_role=None,
    timestamp_label='Posted',
    timestamp=None,
    details=None,
):
    return {
        'kind': kind,
        'latitude': float(latitude),
        'longitude': float(longitude),
        'title': title,
        'detail': detail,
        'posted_by': posted_by,
        'posted_by_role': posted_by_role,
        'timestamp_label': timestamp_label,
        'timestamp': timestamp.isoformat() if timestamp else None,
        'details': details or [],
    }


def order_needs_by_priority(queryset):
    return queryset.annotate(
        priority_order=Case(
            When(priority=BeneficiaryNeed.Priority.CRITICAL, then=Value(0)),
            When(priority=BeneficiaryNeed.Priority.URGENT, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        ),
    ).order_by('priority_order', '-created_at')


class LeaderRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.can_manage_community


class ModalFormMixin:
    modal_template_name = 'community_resilience/entry_modal_form.html'
    modal_frame_template_name = 'community_resilience/entry_modal_frame.html'
    modal_success_message = 'Changes saved successfully.'

    def is_frame_request(self):
        return self.request.GET.get('modal') == 'frame'

    def is_modal_request(self):
        return self.request.headers.get('X-Modal-Request') == 'true' or self.is_frame_request()

    def get_template_names(self):
        if self.is_frame_request():
            return [self.modal_frame_template_name]
        if self.is_modal_request():
            return [self.modal_template_name]
        return super().get_template_names()

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.is_frame_request():
            return render(self.request, 'community_resilience/entry_modal_success.html', {
                'message': self.modal_success_message,
            })
        if self.is_modal_request():
            return JsonResponse({
                'message': self.modal_success_message,
                'redirect_url': str(self.get_success_url()),
            })
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.is_modal_request():
            response.status_code = 422
        return response


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'community_resilience/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.can_manage_community:
            tasks = PreparednessTask.objects.all()
            needs = BeneficiaryNeed.objects.all()
        elif self.request.user.role == CommunityUser.Role.VOLUNTEER:
            tasks = PreparednessTask.objects.filter(assigned_to=self.request.user)
            needs = BeneficiaryNeed.objects.all()
        else:
            tasks = PreparednessTask.objects.none()
            needs = BeneficiaryNeed.objects.filter(reported_by=self.request.user)
        tasks = tasks.select_related('assigned_to', 'created_by')
        needs = needs.select_related('reported_by')
        map_markers = [
            marker(
                'task',
                task.latitude,
                task.longitude,
                task.title,
                ' · '.join(part for part in (task.get_category_display(), task.location) if part),
                posted_by=str(task.created_by),
                posted_by_role=task.created_by.get_role_display(),
                timestamp=task.created_at,
                details=[
                    *(
                        [{'label': 'Description', 'value': task.description}]
                        if task.description else []
                    ),
                    {'label': 'Category', 'value': task.get_category_display()},
                    {'label': 'Location', 'value': task.location},
                    {'label': 'Status', 'value': task.get_status_display()},
                    {'label': 'Priority', 'value': task.get_priority_display()},
                    *(
                        [{'label': 'Assigned to', 'value': str(task.assigned_to)}]
                        if task.assigned_to else []
                    ),
                    *(
                        [{'label': 'Due date', 'value': task.due_date.isoformat()}]
                        if task.due_date else []
                    ),
                ],
            )
            for task in tasks.filter(latitude__isnull=False, longitude__isnull=False)
        ]
        map_markers.extend(
            marker(
                'resource',
                resource.latitude,
                resource.longitude,
                resource.name,
                resource.location,
                posted_by=str(resource.created_by) if resource.created_by else None,
                posted_by_role=resource.created_by.get_role_display() if resource.created_by else None,
                timestamp_label='Last updated',
                timestamp=resource.updated_at,
                details=[
                    {'label': 'Category', 'value': resource.get_category_display()},
                    {'label': 'Quantity', 'value': f'{resource.quantity} {resource.unit}'},
                    {'label': 'Location', 'value': resource.location},
                ],
            )
            for resource in ResourceItem.objects.filter(
                latitude__isnull=False,
                longitude__isnull=False,
            ).select_related('created_by')
        )
        map_markers.extend(
            marker(
                'need',
                need.latitude,
                need.longitude,
                f'{need.get_need_type_display()} · {need.barangay}',
                need.get_priority_display(),
                posted_by=str(need.reported_by),
                posted_by_role=need.reported_by.get_role_display(),
                timestamp=need.created_at,
                details=[
                    {'label': 'Need', 'value': need.get_need_type_display()},
                    {'label': 'Barangay', 'value': need.barangay},
                    {'label': 'Priority', 'value': need.get_priority_display()},
                    {'label': 'Status', 'value': need.get_status_display()},
                ],
            )
            for need in needs.filter(
                latitude__isnull=False,
                longitude__isnull=False,
            ).exclude(status=BeneficiaryNeed.Status.FULFILLED).select_related('reported_by')
        )
        context.update({
            'open_task_count': tasks.exclude(status=PreparednessTask.Status.DONE).count(),
            'resource_count': ResourceItem.objects.count(),
            'open_need_count': needs.exclude(status=BeneficiaryNeed.Status.FULFILLED).count(),
            'recent_tasks': tasks.select_related('assigned_to')[:5],
            'urgent_needs': order_needs_by_priority(
                needs.exclude(status=BeneficiaryNeed.Status.FULFILLED).filter(
                    priority__in=(BeneficiaryNeed.Priority.URGENT, BeneficiaryNeed.Priority.CRITICAL),
                ),
            )[:5],
            'map_markers': map_markers,
        })
        return context


class TaskListView(LoginRequiredMixin, ListView):
    model = PreparednessTask
    template_name = 'community_resilience/task_list.html'
    context_object_name = 'tasks'

    def get_queryset(self):
        queryset = PreparednessTask.objects.select_related('assigned_to', 'created_by')
        if self.request.user.can_manage_community:
            return queryset
        if self.request.user.role == CommunityUser.Role.VOLUNTEER:
            return queryset.filter(assigned_to=self.request.user)
        return queryset.none()


class TaskCreateView(ModalFormMixin, LeaderRequiredMixin, CreateView):
    model = PreparednessTask
    form_class = PreparednessTaskForm
    template_name = 'community_resilience/form.html'
    success_url = reverse_lazy('task-list')
    extra_context = {'title': 'Create preparedness task', 'submit_label': 'Create task'}
    modal_success_message = 'Preparedness task created.'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class TaskUpdateView(ModalFormMixin, LeaderRequiredMixin, UpdateView):
    model = PreparednessTask
    form_class = PreparednessTaskForm
    template_name = 'community_resilience/form.html'
    success_url = reverse_lazy('task-list')
    extra_context = {'title': 'Edit preparedness task', 'submit_label': 'Save task'}
    modal_success_message = 'Preparedness task updated.'


class TaskDeleteView(LeaderRequiredMixin, DeleteView):
    model = PreparednessTask
    template_name = 'community_resilience/confirm_delete.html'
    success_url = reverse_lazy('task-list')
    extra_context = {'title': 'Delete preparedness task'}


class TaskStatusUpdateView(ModalFormMixin, LoginRequiredMixin, UpdateView):
    model = PreparednessTask
    form_class = TaskStatusForm
    template_name = 'community_resilience/form.html'
    success_url = reverse_lazy('task-list')
    extra_context = {'title': 'Update task status', 'submit_label': 'Update status'}
    modal_success_message = 'Task status updated.'

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.can_manage_community:
            return queryset
        if user.role == CommunityUser.Role.VOLUNTEER:
            return queryset.filter(assigned_to=user)
        return queryset.none()


class ResourceListView(LoginRequiredMixin, ListView):
    model = ResourceItem
    template_name = 'community_resilience/resource_list.html'
    context_object_name = 'resources'


class ResourceCreateView(ModalFormMixin, LeaderRequiredMixin, CreateView):
    model = ResourceItem
    form_class = ResourceItemForm
    template_name = 'community_resilience/form.html'
    success_url = reverse_lazy('resource-list')
    extra_context = {'title': 'Add resource', 'submit_label': 'Add resource'}
    modal_success_message = 'Resource added.'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ResourceUpdateView(ModalFormMixin, LeaderRequiredMixin, UpdateView):
    model = ResourceItem
    form_class = ResourceItemForm
    template_name = 'community_resilience/form.html'
    success_url = reverse_lazy('resource-list')
    extra_context = {'title': 'Update resource', 'submit_label': 'Save resource'}
    modal_success_message = 'Resource updated.'


class ResourceDeleteView(LeaderRequiredMixin, DeleteView):
    model = ResourceItem
    template_name = 'community_resilience/confirm_delete.html'
    success_url = reverse_lazy('resource-list')
    extra_context = {'title': 'Remove resource'}


class NeedListView(LoginRequiredMixin, ListView):
    model = BeneficiaryNeed
    template_name = 'community_resilience/need_list.html'
    context_object_name = 'needs'

    def get_queryset(self):
        queryset = BeneficiaryNeed.objects.select_related('reported_by')
        if not self.request.user.is_superuser and self.request.user.role == CommunityUser.Role.BENEFICIARY:
            queryset = queryset.filter(reported_by=self.request.user)
        return order_needs_by_priority(queryset)


class NeedDetailView(LoginRequiredMixin, DetailView):
    model = BeneficiaryNeed
    template_name = 'community_resilience/need_detail.html'
    context_object_name = 'need'

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser and self.request.user.role == CommunityUser.Role.BENEFICIARY:
            return queryset.filter(reported_by=self.request.user)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_completion_submission'] = self.object.completion_submissions.filter(
            review_status=NeedCompletionSubmission.ReviewStatus.PENDING,
        ).exists()
        return context


class NeedCreateView(ModalFormMixin, LoginRequiredMixin, CreateView):
    model = BeneficiaryNeed
    form_class = BeneficiaryNeedForm
    template_name = 'community_resilience/form.html'
    success_url = reverse_lazy('need-list')
    extra_context = {'title': 'Report a community need', 'submit_label': 'Report need'}
    modal_success_message = 'Community need reported.'

    def form_valid(self, form):
        form.instance.reported_by = self.request.user
        return super().form_valid(form)


class NeedUpdateView(ModalFormMixin, LeaderRequiredMixin, UpdateView):
    model = BeneficiaryNeed
    form_class = BeneficiaryNeedUpdateForm
    template_name = 'community_resilience/form.html'
    success_url = reverse_lazy('need-list')
    extra_context = {'title': 'Update reported need', 'submit_label': 'Save need'}
    modal_success_message = 'Community need updated successfully.'


class NeedDeleteView(LeaderRequiredMixin, DeleteView):
    model = BeneficiaryNeed
    template_name = 'community_resilience/confirm_delete.html'
    success_url = reverse_lazy('need-list')
    extra_context = {'title': 'Delete reported need'}


class NeedCompletionSubmitView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = NeedCompletionSubmission
    form_class = NeedCompletionSubmissionForm
    template_name = 'community_resilience/need_completion_form.html'

    def test_func(self):
        return self.request.user.role == CommunityUser.Role.VOLUNTEER

    def get_need(self):
        return get_object_or_404(BeneficiaryNeed, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['need'] = self.get_need()
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                need = get_object_or_404(
                    BeneficiaryNeed.objects.select_for_update(),
                    pk=self.kwargs['pk'],
                )
                pending_exists = need.completion_submissions.filter(
                    review_status=NeedCompletionSubmission.ReviewStatus.PENDING,
                ).exists()
                if need.status == BeneficiaryNeed.Status.FULFILLED:
                    form.add_error(None, 'This community need has already been marked done.')
                    return self.form_invalid(form)
                if pending_exists:
                    form.add_error(None, 'A completion photo is already awaiting system administrator review.')
                    return self.form_invalid(form)
                form.instance.need = need
                form.instance.submitted_by = self.request.user
                response = super().form_valid(form)
        except IntegrityError:
            if form.instance.proof_image and form.instance.proof_image.name:
                form.instance.proof_image.delete(save=False)
            form.add_error(None, 'A completion photo is already awaiting system administrator review.')
            return self.form_invalid(form)

        messages.success(self.request, 'Your completion photo was submitted for system administrator review.')
        return response

    def get_success_url(self):
        return reverse('need-detail', args=(self.object.need_id,))


class NeedCompletionProofView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.is_staff and (
            user.has_perm('community_resilience.view_needcompletionsubmission')
            or user.has_perm('community_resilience.change_needcompletionsubmission')
        )

    def get(self, request, pk):
        submission = get_object_or_404(NeedCompletionSubmission, pk=pk)
        if not submission.proof_image or not submission.proof_image.storage.exists(submission.proof_image.name):
            raise Http404('The uploaded proof image could not be found.')

        content_type = mimetypes.guess_type(submission.proof_image.name)[0] or 'application/octet-stream'
        response = FileResponse(submission.proof_image.open('rb'), content_type=content_type)
        response['Content-Disposition'] = 'inline'
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
