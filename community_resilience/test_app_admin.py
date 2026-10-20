from django.test import TestCase
from django.urls import reverse
from .models import CommunityUser, BeneficiaryNeed, NeedCompletionSubmission


class AppAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = CommunityUser.objects.create_superuser(username='super', password='Test-pass-938!', role='beneficiary')
        cls.member = CommunityUser.objects.create_user(username='member', password='Test-pass-938!', role='leader', is_staff=True)
        cls.need = BeneficiaryNeed.objects.create(barangay='Test barangay', household_size=2, need_type='food', description='Food needed', reported_by=cls.member)
        cls.submission = NeedCompletionSubmission.objects.create(need=cls.need, submitted_by=cls.member, proof_image='test.png')

    def routes(self):
        return [('admin-dashboard', []), ('admin-users', []), ('admin-user-create', []), ('admin-user-update', [self.member.pk]), ('admin-reviews', []), ('admin-review', [self.submission.pk])]

    def test_admin_pages_require_superuser_for_reads_and_writes(self):
        for name, args in self.routes():
            url = reverse(name, args=args)
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.member)
        for name, args in self.routes():
            for method in (self.client.get, self.client.post):
                self.assertEqual(method(reverse(name, args=args)).status_code, 403)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_superuser)

    def test_superuser_gets_app_pages_and_community_access_for_any_role(self):
        self.client.force_login(self.admin)
        for name, args in self.routes():
            response = self.client.get(reverse(name, args=args))
            self.assertContains(response, 'Bayanihan')
        for name in ['task-create', 'resource-create', 'need-list']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertContains(self.client.get(reverse('need-list')), 'Test barangay')
        self.assertContains(self.client.get(reverse('dashboard')), 'Super admin')

    def test_non_superuser_navigation_hides_admin(self):
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(reverse('dashboard')), 'title="Administration"')

    def test_create_account_hashes_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin-user-create'), {'username': 'new-user', 'role': 'volunteer', 'password1': 'Secure-pass-892!', 'password2': 'Secure-pass-892!'})
        self.assertRedirects(response, reverse('admin-users'))
        account = CommunityUser.objects.get(username='new-user')
        self.assertTrue(account.check_password('Secure-pass-892!'))
        self.assertFalse(account.is_superuser)

    def test_admin_account_create_and_update_support_modal_flow(self):
        self.client.force_login(self.admin)

        create_response = self.client.get(
            reverse('admin-user-create'),
            HTTP_X_MODAL_REQUEST='true',
        )
        self.assertContains(create_response, 'data-entry-form')
        self.assertContains(create_response, 'Create community account')
        self.assertNotContains(create_response, '<html')

        invalid_response = self.client.post(
            reverse('admin-user-create'),
            {
                'username': self.admin.username,
                'role': 'volunteer',
                'password1': 'Secure-pass-892!',
                'password2': 'Secure-pass-892!',
            },
            HTTP_X_MODAL_REQUEST='true',
        )
        self.assertEqual(invalid_response.status_code, 422)
        self.assertContains(invalid_response, 'already exists', status_code=422)

        success_response = self.client.post(
            reverse('admin-user-create'),
            {
                'username': 'modal-user',
                'role': 'volunteer',
                'password1': 'Secure-pass-892!',
                'password2': 'Secure-pass-892!',
            },
            HTTP_X_MODAL_REQUEST='true',
        )
        self.assertEqual(success_response.status_code, 200)
        self.assertEqual(success_response.json()['message'], 'Community account created.')
        self.assertTrue(CommunityUser.objects.filter(username='modal-user').exists())

        update_response = self.client.get(
            reverse('admin-user-update', args=[self.member.pk]),
            HTTP_X_MODAL_REQUEST='true',
        )
        self.assertContains(update_response, 'data-entry-form')
        self.assertContains(update_response, 'Edit account and access')

    def test_completion_review_supports_modal_flow_with_evidence(self):
        self.client.force_login(self.admin)
        url = reverse('admin-review', args=[self.submission.pk])

        response = self.client.get(url, HTTP_X_MODAL_REQUEST='true')
        self.assertContains(response, 'data-entry-form')
        self.assertContains(response, 'entry-review-summary')
        self.assertContains(response, reverse('need-completion-proof', args=[self.submission.pk]))
        self.assertContains(response, 'Save review')

        invalid_response = self.client.post(
            url,
            {'decision': 'rejected', 'review_notes': ''},
            HTTP_X_MODAL_REQUEST='true',
        )
        self.assertEqual(invalid_response.status_code, 422)
        self.assertContains(invalid_response, 'Explain what', status_code=422)

    def test_admin_can_update_access_and_cannot_lock_self_out(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin-user-update', args=[self.member.pk]), {'username': 'member', 'role': 'volunteer', 'is_active': 'on', 'is_superuser': 'on'})
        self.assertRedirects(response, reverse('admin-users'))
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_superuser)
        self.assertTrue(self.member.is_staff)
        self.client.post(reverse('admin-user-update', args=[self.admin.pk]), {'username': 'super', 'role': 'beneficiary'})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_superuser and self.admin.is_active)

    def test_approval_records_reviewer_and_cannot_be_replayed(self):
        self.client.force_login(self.admin)
        url = reverse('admin-review', args=[self.submission.pk])
        self.assertRedirects(self.client.post(url, {'decision': 'approved', 'review_notes': 'Verified'}), reverse('admin-reviews'))
        self.need.refresh_from_db()
        self.submission.refresh_from_db()
        self.assertEqual(self.need.status, 'fulfilled')
        self.assertEqual(self.submission.reviewed_by, self.admin)
        self.assertIsNotNone(self.submission.reviewed_at)
        self.assertContains(self.client.post(url, {'decision': 'rejected', 'review_notes': 'Changed'}), 'already been reviewed')
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.review_status, 'approved')

    def test_rejection_requires_notes_and_keeps_need_open(self):
        self.client.force_login(self.admin)
        url = reverse('admin-review', args=[self.submission.pk])
        self.assertContains(self.client.post(url, {'decision': 'rejected'}), 'Explain what')
        self.assertRedirects(self.client.post(url, {'decision': 'rejected', 'review_notes': 'Please show delivered supplies.'}), reverse('admin-reviews'))
        self.need.refresh_from_db()
        self.submission.refresh_from_db()
        self.assertEqual(self.need.status, 'open')
        self.assertEqual(self.submission.review_status, 'rejected')
