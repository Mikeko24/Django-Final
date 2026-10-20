from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import BeneficiaryNeed, CommunityUser, NeedCompletionSubmission, PreparednessTask, ResourceItem


class AdminUserCreateForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CommunityUser
        fields = ('username', 'first_name', 'last_name', 'email', 'role')


class AdminUserUpdateForm(forms.ModelForm):
    class Meta:
        model = CommunityUser
        fields = ('username', 'first_name', 'last_name', 'email', 'role', 'is_active', 'is_staff', 'is_superuser')
        labels = {'is_active': 'Account active', 'is_staff': 'Django maintenance access', 'is_superuser': 'Super admin access'}
        help_texts = {'is_superuser': 'Grants full access to administration and all community records.'}

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        if actor and actor.pk == self.instance.pk:
            for name in ('is_active', 'is_staff', 'is_superuser'):
                self.fields[name].disabled = True
                self.fields[name].help_text = 'Your own access cannot be removed here.'

    def clean(self):
        data = super().clean()
        if data.get('is_superuser'):
            data['is_staff'] = True
        return data


class CompletionReviewForm(forms.Form):
    decision = forms.ChoiceField(choices=(('approved', 'Approve completion'), ('rejected', 'Request another submission')))
    review_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}))

    def clean(self):
        data = super().clean()
        if data.get('decision') == 'rejected' and not data.get('review_notes'):
            self.add_error('review_notes', 'Explain what the volunteer should correct.')
        return data


class MapCoordinatesFormMixin:
    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')
        if (latitude is None) != (longitude is None):
            self.add_error('latitude', 'Select a map point or clear both coordinates.')
            self.add_error('longitude', 'Select a map point or clear both coordinates.')
        return cleaned_data


class PreparednessTaskForm(MapCoordinatesFormMixin, forms.ModelForm):
    class Meta:
        model = PreparednessTask
        fields = (
            'title',
            'description',
            'category',
            'location',
            'latitude',
            'longitude',
            'priority',
            'due_date',
            'assigned_to',
        )
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = self.fields['assigned_to'].queryset.filter(
            role__in=(CommunityUser.Role.LEADER, CommunityUser.Role.VOLUNTEER),
        )


class TaskStatusForm(forms.ModelForm):
    class Meta:
        model = PreparednessTask
        fields = ('status',)


class ResourceItemForm(MapCoordinatesFormMixin, forms.ModelForm):
    class Meta:
        model = ResourceItem
        fields = ('name', 'category', 'quantity', 'unit', 'location', 'latitude', 'longitude')
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }


class BeneficiaryNeedForm(MapCoordinatesFormMixin, forms.ModelForm):
    class Meta:
        model = BeneficiaryNeed
        fields = ('barangay', 'latitude', 'longitude', 'household_size', 'need_type', 'description', 'priority')
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }


class BeneficiaryNeedUpdateForm(BeneficiaryNeedForm):
    class Meta(BeneficiaryNeedForm.Meta):
        fields = BeneficiaryNeedForm.Meta.fields + ('status',)


class NeedCompletionSubmissionForm(forms.ModelForm):
    proof_image = forms.ImageField(
        label='Completion photo',
        help_text='Upload a clear JPG, PNG, or WebP image (maximum 5 MB).',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
    )

    class Meta:
        model = NeedCompletionSubmission
        fields = ('proof_image',)
