from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView

from .forms import AdminUserCreateForm, AdminUserUpdateForm, CompletionReviewForm
from .models import BeneficiaryNeed, CommunityUser, NeedCompletionSubmission
from .views import ModalFormMixin


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_active and self.request.user.is_superuser


class AdminDashboardView(SuperuserRequiredMixin, TemplateView):
    template_name = 'community_resilience/admin_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_count'] = CommunityUser.objects.count()
        context['inactive_count'] = CommunityUser.objects.filter(is_active=False).count()
        context['pending_count'] = NeedCompletionSubmission.objects.filter(review_status='pending').count()
        return context


class AdminUserListView(SuperuserRequiredMixin, ListView):
    template_name = 'community_resilience/admin_users.html'
    context_object_name = 'accounts'
    paginate_by = 25

    def get_queryset(self):
        query = self.request.GET.get('q', '').strip()
        return CommunityUser.objects.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
            | Q(first_name__icontains=query) | Q(last_name__icontains=query)
        ).order_by('username')


class AdminUserCreateView(ModalFormMixin, SuperuserRequiredMixin, CreateView):
    form_class = AdminUserCreateForm
    template_name = 'community_resilience/admin_form.html'
    success_url = reverse_lazy('admin-users')
    extra_context = {
        'title': 'Create community account',
        'cancel_url': reverse_lazy('admin-users'),
        'submit_label': 'Create account',
        'modal_eyebrow': 'PEOPLE & ACCESS',
        'modal_description': 'Add a community member and assign their initial role.',
    }
    modal_success_message = 'Community account created.'

    def form_valid(self, form):
        messages.success(self.request, 'Account created. You can edit its admin access from the user list.')
        return super().form_valid(form)


class AdminUserUpdateView(ModalFormMixin, SuperuserRequiredMixin, UpdateView):
    model = CommunityUser
    form_class = AdminUserUpdateForm
    template_name = 'community_resilience/admin_form.html'
    success_url = reverse_lazy('admin-users')
    extra_context = {
        'title': 'Edit account and access',
        'cancel_url': reverse_lazy('admin-users'),
        'submit_label': 'Save account',
        'modal_eyebrow': 'PEOPLE & ACCESS',
        'modal_description': 'Update this member’s profile, role, status, and administrative access.',
    }
    modal_success_message = 'Account and access updated.'

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), 'actor': self.request.user}

    def form_valid(self, form):
        messages.success(self.request, 'Account and access updated.')
        return super().form_valid(form)


class AdminReviewListView(SuperuserRequiredMixin, ListView):
    template_name = 'community_resilience/admin_reviews.html'
    context_object_name = 'submissions'
    paginate_by = 25

    def get_queryset(self):
        return NeedCompletionSubmission.objects.filter(review_status='pending').select_related('need', 'submitted_by').order_by('submitted_at')


class AdminReviewView(ModalFormMixin, SuperuserRequiredMixin, FormView):
    form_class = CompletionReviewForm
    template_name = 'community_resilience/admin_form.html'
    success_url = reverse_lazy('admin-reviews')
    extra_context = {
        'title': 'Review completion photo',
        'cancel_url': reverse_lazy('admin-reviews'),
        'submit_label': 'Save review',
        'modal_eyebrow': 'DELIVERED SUPPORT',
        'modal_description': 'Review the evidence, then approve the completion or request another submission.',
    }
    modal_success_message = 'Completion review saved.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['submission'] = get_object_or_404(NeedCompletionSubmission.objects.select_related('need', 'submitted_by'), pk=self.kwargs['pk'])
        return context

    def form_valid(self, form):
        with transaction.atomic():
            submission = get_object_or_404(NeedCompletionSubmission.objects.select_for_update(), pk=self.kwargs['pk'])
            if submission.review_status != 'pending':
                form.add_error(None, 'This submission has already been reviewed. Return to the review queue.')
                return self.form_invalid(form)
            submission.review_status = form.cleaned_data['decision']
            submission.review_notes = form.cleaned_data['review_notes']
            submission.reviewed_by = self.request.user
            submission.reviewed_at = timezone.now()
            submission.save(update_fields=['review_status', 'review_notes', 'reviewed_by', 'reviewed_at'])
            if submission.review_status == 'approved':
                BeneficiaryNeed.objects.filter(pk=submission.need_id).update(status='fulfilled', updated_at=timezone.now())
        messages.success(self.request, 'Completion approved and need marked done.' if submission.review_status == 'approved' else 'Another submission requested.')
        return super().form_valid(form)
