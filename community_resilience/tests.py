from io import BytesIO
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .forms import PreparednessTaskForm, ResourceItemForm
from .models import BeneficiaryNeed, CommunityUser, NeedCompletionSubmission, PreparednessTask, ResourceItem


class CommunityResilienceTests(TestCase):
    def setUp(self):
        self.leader = CommunityUser.objects.create_user(
            username='leader',
            password='test-password-123',
            role=CommunityUser.Role.LEADER,
        )
        self.volunteer = CommunityUser.objects.create_user(
            username='volunteer',
            password='test-password-123',
            role=CommunityUser.Role.VOLUNTEER,
        )
        self.other_volunteer = CommunityUser.objects.create_user(
            username='other',
            password='test-password-123',
            role=CommunityUser.Role.VOLUNTEER,
        )
        self.beneficiary = CommunityUser.objects.create_user(
            username='beneficiary',
            password='test-password-123',
            role=CommunityUser.Role.BENEFICIARY,
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f'{reverse("login")}?next={reverse("dashboard")}')

    def test_login_page_has_accessible_sign_in_feedback(self):
        response = self.client.post(reverse('login'), {
            'username': 'unknown-user',
            'password': 'incorrect-password',
        })

        self.assertContains(response, 'Welcome back')
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, 'Check both fields and try again.')

    def test_shared_ui_shell_identifies_each_role_and_current_page(self):
        super_admin = CommunityUser.objects.create_superuser(
            username='ui-admin',
            password='test-password-123',
            role=CommunityUser.Role.VOLUNTEER,
        )
        cases = (
            (super_admin, 'super-admin', 'admin-dashboard', 'Administration'),
            (self.leader, 'leader', 'dashboard', 'Dashboard'),
            (self.volunteer, 'volunteer', 'dashboard', 'Dashboard'),
        )

        for account, role_name, route_name, current_label in cases:
            with self.subTest(role=role_name):
                self.client.force_login(account)
                response = self.client.get(reverse(route_name))
                self.assertContains(response, f'data-role="{role_name}"')
                self.assertContains(response, 'community_resilience/ui.js')
                self.assertContains(response, f'aria-current="page"')
                self.assertContains(response, current_label)
                self.client.logout()

    def test_dashboard_uses_attributed_photo_and_opens_entry_actions_in_modals(self):
        self.client.force_login(self.leader)
        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'Preparation_for_Relief_Giving_Operation.jpg')
        self.assertContains(response, 'Wikimedia Commons, CC BY-SA 4.0')
        self.assertContains(response, 'href="/tasks/new/" data-entry-modal')

    def test_entry_forms_support_modal_requests_for_leaders_and_volunteers(self):
        self.client.force_login(self.leader)
        for route_name in ('task-create', 'resource-create', 'need-create'):
            with self.subTest(route=route_name):
                response = self.client.get(
                    reverse(route_name),
                    HTTP_X_MODAL_REQUEST='true',
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-entry-form')
                self.assertContains(response, 'data-close-entry')
                self.assertNotContains(response, '<html')

        task = PreparednessTask.objects.create(
            title='Check evacuation route',
            created_by=self.leader,
            assigned_to=self.volunteer,
        )
        self.client.force_login(self.volunteer)
        response = self.client.get(
            reverse('task-status', args=(task.pk,)),
            HTTP_X_MODAL_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-entry-form')

        response = self.client.post(
            reverse('task-status', args=(task.pk,)),
            {'status': PreparednessTask.Status.IN_PROGRESS},
            HTTP_X_MODAL_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], 'Task status updated.')

        frame_url = f'{reverse("task-status", args=(task.pk,))}?modal=frame'
        frame_response = self.client.get(frame_url)
        self.assertEqual(frame_response.status_code, 200)
        self.assertContains(frame_response, 'entry-frame-document')
        self.assertContains(frame_response, 'data-entry-form')

        frame_save = self.client.post(
            frame_url,
            {'status': PreparednessTask.Status.DONE},
        )
        self.assertEqual(frame_save.status_code, 200)
        self.assertContains(frame_save, 'entry-modal-saved')
        task.refresh_from_db()
        self.assertEqual(task.status, PreparednessTask.Status.DONE)

    def test_leader_can_create_task(self):
        self.client.force_login(self.leader)
        response = self.client.post(reverse('task-create'), {
            'title': 'Fill sandbags',
            'description': 'Prepare the community stock',
            'category': PreparednessTask.Category.SANDBAG,
            'location': 'Barangay hall',
            'priority': PreparednessTask.Priority.HIGH,
            'assigned_to': self.volunteer.pk,
        })
        self.assertRedirects(response, reverse('task-list'))
        task = PreparednessTask.objects.get(title='Fill sandbags')
        self.assertEqual(task.created_by, self.leader)
        self.assertEqual(task.assigned_to, self.volunteer)

    def test_leader_can_create_resource_and_record_poster(self):
        self.client.force_login(self.leader)
        response = self.client.post(reverse('resource-create'), {
            'name': 'Drinking water',
            'category': ResourceItem.Category.WATER,
            'quantity': '40',
            'unit': 'liters',
            'location': 'Community center',
        })
        self.assertRedirects(response, reverse('resource-list'))
        resource = ResourceItem.objects.get(name='Drinking water')
        self.assertEqual(resource.created_by, self.leader)

    def test_volunteer_only_sees_assigned_tasks_and_can_update_own_status(self):
        own_task = PreparednessTask.objects.create(
            title='Prepare water station',
            created_by=self.leader,
            assigned_to=self.volunteer,
        )
        other_task = PreparednessTask.objects.create(
            title='Inspect evacuation center',
            created_by=self.leader,
            assigned_to=self.other_volunteer,
        )
        self.client.force_login(self.volunteer)
        status_form_response = self.client.get(reverse('task-status', args=(own_task.pk,)))
        self.assertContains(status_form_response, 'Update task status')
        self.assertNotContains(status_form_response, 'location-picker-map')

        response = self.client.get(reverse('task-list'))
        self.assertContains(response, own_task.title)
        self.assertNotContains(response, other_task.title)

        response = self.client.post(
            reverse('task-status', args=(own_task.pk,)),
            {'status': PreparednessTask.Status.IN_PROGRESS},
        )
        self.assertRedirects(response, reverse('task-list'))
        own_task.refresh_from_db()
        self.assertEqual(own_task.status, PreparednessTask.Status.IN_PROGRESS)
        self.assertEqual(
            self.client.get(reverse('task-status', args=(other_task.pk,))).status_code,
            404,
        )

    def test_non_leader_cannot_manage_inventory(self):
        self.client.force_login(self.volunteer)
        self.assertEqual(self.client.get(reverse('resource-create')).status_code, 403)

    def test_task_assignment_excludes_beneficiaries(self):
        form = PreparednessTaskForm()
        self.assertEqual(
            set(form.fields['assigned_to'].queryset.values_list('pk', flat=True)),
            {self.leader.pk, self.volunteer.pk, self.other_volunteer.pk},
        )
        self.client.force_login(self.volunteer)
        self.assertEqual(self.client.get(reverse('task-create')).status_code, 403)

    def test_resource_quantity_cannot_be_negative(self):
        form = ResourceItemForm(data={
            'name': 'Drinking water',
            'category': ResourceItem.Category.WATER,
            'quantity': '-1',
            'unit': 'liters',
            'location': 'Barangay hall',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('quantity', form.errors)

    def test_map_coordinates_must_be_a_complete_valid_pair(self):
        form = PreparednessTaskForm(data={
            'title': 'Check water station',
            'latitude': '14.599500',
            'longitude': '',
            'assigned_to': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('latitude', form.errors)
        self.assertIn('longitude', form.errors)

        invalid_form = ResourceItemForm(data={
            'name': 'Water',
            'category': ResourceItem.Category.WATER,
            'quantity': '10',
            'unit': 'liters',
            'location': 'Community center',
            'latitude': '95',
            'longitude': '121',
        })
        self.assertFalse(invalid_form.is_valid())
        self.assertIn('latitude', invalid_form.errors)

    def test_leader_and_beneficiary_can_save_pinned_records(self):
        self.client.force_login(self.leader)
        task_response = self.client.post(reverse('task-create'), {
            'title': 'Set up water point',
            'category': PreparednessTask.Category.WATER,
            'location': 'Community center',
            'latitude': '14.599500',
            'longitude': '120.984200',
            'priority': PreparednessTask.Priority.HIGH,
            'assigned_to': self.volunteer.pk,
        })
        self.assertRedirects(task_response, reverse('task-list'))
        task = PreparednessTask.objects.get(title='Set up water point')
        self.assertEqual(str(task.latitude), '14.599500')
        self.assertEqual(str(task.longitude), '120.984200')

        resource_response = self.client.post(reverse('resource-create'), {
            'name': 'Drinking water',
            'category': ResourceItem.Category.WATER,
            'quantity': '40',
            'unit': 'liters',
            'location': 'Community center',
            'latitude': '14.600000',
            'longitude': '120.985000',
        })
        self.assertRedirects(resource_response, reverse('resource-list'))
        resource = ResourceItem.objects.get(name='Drinking water')
        self.assertEqual(str(resource.latitude), '14.600000')

        self.client.force_login(self.beneficiary)
        need_response = self.client.post(reverse('need-create'), {
            'barangay': 'San Isidro',
            'household_size': 3,
            'need_type': BeneficiaryNeed.NeedType.WATER,
            'description': 'Water distribution point needed.',
            'priority': BeneficiaryNeed.Priority.URGENT,
            'latitude': '14.601000',
            'longitude': '120.986000',
        })
        self.assertRedirects(need_response, reverse('need-list'))
        need = BeneficiaryNeed.objects.get(reported_by=self.beneficiary, barangay='San Isidro')
        self.assertEqual(str(need.longitude), '120.986000')

    def test_dashboard_map_respects_user_visibility_and_omits_private_need_details(self):
        own_need = BeneficiaryNeed.objects.create(
            barangay='San Isidro',
            household_size=4,
            need_type=BeneficiaryNeed.NeedType.WATER,
            description='Private household details must not be included in map data.',
            reported_by=self.beneficiary,
            latitude='14.600000',
            longitude='120.985000',
        )
        BeneficiaryNeed.objects.create(
            barangay='Santa Cruz',
            household_size=2,
            need_type=BeneficiaryNeed.NeedType.FOOD,
            description='Another household need.',
            reported_by=self.other_volunteer,
            latitude='14.610000',
            longitude='120.995000',
        )
        PreparednessTask.objects.create(
            title='Inspect evacuation center',
            created_by=self.leader,
            assigned_to=self.volunteer,
            latitude='14.620000',
            longitude='121.005000',
        )
        ResourceItem.objects.create(
            name='Water stock',
            category=ResourceItem.Category.WATER,
            quantity='100',
            unit='liters',
            location='Community center',
            created_by=self.leader,
            latitude='14.605000',
            longitude='120.990000',
        )
        self.client.force_login(self.beneficiary)
        response = self.client.get(reverse('dashboard'))
        markers = response.context['map_markers']
        self.assertEqual({item['kind'] for item in markers}, {'need', 'resource'})
        self.assertTrue(any(own_need.barangay in item['title'] for item in markers))
        self.assertNotIn('Private household details', str(markers))
        self.assertNotContains(response, 'Santa Cruz')

        self.client.force_login(self.leader)
        leader_markers = self.client.get(reverse('dashboard')).context['map_markers']
        self.assertEqual({item['kind'] for item in leader_markers}, {'need', 'resource', 'task'})
        self.assertNotIn('Private household details', str(leader_markers))

    def test_dashboard_map_markers_include_poster_and_safe_activity_details(self):
        task = PreparednessTask.objects.create(
            title='Prepare water station',
            description='Set up the public drinking water station.',
            category=PreparednessTask.Category.WATER,
            location='Community center',
            created_by=self.leader,
            assigned_to=self.volunteer,
            latitude='14.620000',
            longitude='121.005000',
        )
        resource = ResourceItem.objects.create(
            name='Water stock',
            category=ResourceItem.Category.WATER,
            quantity='100',
            unit='liters',
            location='Community center',
            created_by=self.leader,
            latitude='14.605000',
            longitude='120.990000',
        )
        need = BeneficiaryNeed.objects.create(
            barangay='San Isidro',
            household_size=4,
            need_type=BeneficiaryNeed.NeedType.WATER,
            description='Private household details stay off the public map.',
            reported_by=self.beneficiary,
            latitude='14.600000',
            longitude='120.985000',
        )

        self.client.force_login(self.leader)
        response = self.client.get(reverse('dashboard'))
        markers_by_title = {item['title']: item for item in response.context['map_markers']}

        task_marker = markers_by_title[task.title]
        self.assertEqual(task_marker['posted_by'], str(self.leader))
        self.assertEqual(task_marker['posted_by_role'], self.leader.get_role_display())
        task_details = {detail['label']: detail['value'] for detail in task_marker['details']}
        self.assertEqual(task_details['Description'], task.description)
        self.assertEqual(task_details['Category'], task.get_category_display())
        self.assertEqual(task_details['Assigned to'], str(self.volunteer))

        resource_marker = markers_by_title[resource.name]
        self.assertEqual(resource_marker['posted_by'], str(self.leader))
        self.assertEqual(resource_marker['timestamp_label'], 'Last updated')
        self.assertEqual(resource_marker['details'][1]['value'], '100.00 liters')

        need_marker = markers_by_title[f'{need.get_need_type_display()} · {need.barangay}']
        self.assertEqual(need_marker['posted_by'], str(self.beneficiary))
        self.assertEqual(need_marker['details'][0]['value'], need.get_need_type_display())
        self.assertNotIn('Private household details', str(need_marker))
        self.assertContains(response, 'activity-dialog')
        self.assertContains(response, 'id="activity-dialog-map-link"')
        self.assertContains(response, 'Open in Google Maps')
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, 'rel="noopener noreferrer"')

    def test_beneficiary_sees_only_needs_they_reported(self):
        own_need = BeneficiaryNeed.objects.create(
            barangay='San Isidro',
            household_size=4,
            need_type=BeneficiaryNeed.NeedType.WATER,
            description='Need drinking water',
            reported_by=self.beneficiary,
        )
        other_need = BeneficiaryNeed.objects.create(
            barangay='Santa Cruz',
            household_size=2,
            need_type=BeneficiaryNeed.NeedType.FOOD,
            description='Need food packs',
            reported_by=self.other_volunteer,
        )
        self.client.force_login(self.beneficiary)
        response = self.client.get(reverse('need-list'))
        self.assertContains(response, own_need.barangay)
        self.assertNotContains(response, other_need.barangay)
        self.assertContains(response, reverse('need-detail', args=(own_need.pk,)))

    def test_need_detail_shows_full_report_and_map_pin_but_respects_beneficiary_access(self):
        own_need = BeneficiaryNeed.objects.create(
            barangay='San Isidro',
            household_size=4,
            need_type=BeneficiaryNeed.NeedType.WATER,
            description='Four household members need safe drinking water.',
            priority=BeneficiaryNeed.Priority.URGENT,
            status=BeneficiaryNeed.Status.IN_PROGRESS,
            reported_by=self.beneficiary,
            latitude='14.600000',
            longitude='120.985000',
        )
        other_need = BeneficiaryNeed.objects.create(
            barangay='Santa Cruz',
            household_size=2,
            need_type=BeneficiaryNeed.NeedType.FOOD,
            description='This report belongs to a different person.',
            reported_by=self.other_volunteer,
            latitude='14.610000',
            longitude='120.995000',
        )

        self.client.force_login(self.beneficiary)
        response = self.client.get(reverse('need-detail', args=(own_need.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_need.description)
        self.assertContains(response, '14.600000')
        self.assertContains(response, '120.985000')
        self.assertContains(response, 'need-detail-map')
        self.assertContains(
            response,
            'https://www.google.com/maps/search/?api=1&amp;query=14.600000,120.985000',
        )
        self.assertContains(response, 'Open this pin in Google Maps')
        self.assertNotContains(
            response,
            'For safety, this location should identify a public support point',
        )
        self.assertNotContains(response, 'Reported by')
        self.assertEqual(self.client.get(reverse('need-detail', args=(other_need.pk,))).status_code, 404)

        self.client.force_login(self.leader)
        leader_response = self.client.get(reverse('need-detail', args=(own_need.pk,)))
        self.assertContains(leader_response, own_need.description)
        self.assertNotContains(leader_response, 'Reported by')

    def test_need_detail_shows_pin_when_a_coordinate_is_zero(self):
        need = BeneficiaryNeed.objects.create(
            barangay='San Isidro',
            household_size=1,
            need_type=BeneficiaryNeed.NeedType.WATER,
            description='A support location on the equator.',
            reported_by=self.beneficiary,
            latitude='0.000000',
            longitude='120.985000',
        )
        self.client.force_login(self.beneficiary)

        response = self.client.get(reverse('need-detail', args=(need.pk,)))

        self.assertContains(response, '0.000000, 120.985000')
        self.assertContains(response, 'need-detail-map')

    def test_leader_can_mark_need_done_but_beneficiary_cannot_change_status(self):
        need = BeneficiaryNeed.objects.create(
            barangay='San Isidro',
            household_size=2,
            need_type=BeneficiaryNeed.NeedType.WATER,
            description='Provide drinking water.',
            reported_by=self.beneficiary,
        )
        self.client.force_login(self.leader)

        response = self.client.get(reverse('need-update', args=(need.pk,)))
        self.assertContains(response, 'Done (fulfilled)')
        response = self.client.post(reverse('need-update', args=(need.pk,)), {
            'barangay': need.barangay,
            'household_size': need.household_size,
            'need_type': need.need_type,
            'description': need.description,
            'priority': need.priority,
            'status': BeneficiaryNeed.Status.FULFILLED,
            'latitude': '',
            'longitude': '',
        })

        self.assertRedirects(response, reverse('need-list'))
        need.refresh_from_db()
        self.assertEqual(need.status, BeneficiaryNeed.Status.FULFILLED)

        self.client.force_login(self.beneficiary)
        self.assertEqual(
            self.client.get(reverse('need-update', args=(need.pk,))).status_code,
            403,
        )

    def test_need_update_can_load_and_save_inside_modal(self):
        need = BeneficiaryNeed.objects.create(
            barangay='San Isidro',
            household_size=2,
            need_type=BeneficiaryNeed.NeedType.WATER,
            description='Provide drinking water.',
            reported_by=self.beneficiary,
        )
        self.client.force_login(self.leader)

        modal_response = self.client.get(
            reverse('need-update', args=(need.pk,)),
            HTTP_X_MODAL_REQUEST='true',
        )
        self.assertEqual(modal_response.status_code, 200)
        self.assertContains(modal_response, 'data-need-update-form')
        self.assertNotContains(modal_response, '<html')

        invalid_response = self.client.post(
            reverse('need-update', args=(need.pk,)),
            {
                'barangay': '',
                'household_size': 2,
                'need_type': need.need_type,
                'description': need.description,
                'priority': need.priority,
                'status': need.status,
                'latitude': '',
                'longitude': '',
            },
            HTTP_X_MODAL_REQUEST='true',
        )
        self.assertEqual(invalid_response.status_code, 422)
        self.assertContains(invalid_response, 'This field is required.', status_code=422)

        success_response = self.client.post(
            reverse('need-update', args=(need.pk,)),
            {
                'barangay': 'Santa Cruz',
                'household_size': 2,
                'need_type': need.need_type,
                'description': 'Water delivery is being coordinated.',
                'priority': need.priority,
                'status': need.status,
                'latitude': '',
                'longitude': '',
            },
            HTTP_X_MODAL_REQUEST='true',
        )
        self.assertEqual(success_response.status_code, 200)
        self.assertEqual(success_response.json()['message'], 'Community need updated successfully.')
        need.refresh_from_db()
        self.assertEqual(need.barangay, 'Santa Cruz')

    def test_volunteer_can_submit_one_completion_photo_for_admin_review(self):
        need = BeneficiaryNeed.objects.create(
            barangay='San Isidro',
            household_size=2,
            need_type=BeneficiaryNeed.NeedType.WATER,
            description='Provide drinking water.',
            reported_by=self.beneficiary,
        )
        image_buffer = BytesIO()
        Image.new('RGB', (2, 2), color='blue').save(image_buffer, format='PNG')
        image = SimpleUploadedFile('proof.png', image_buffer.getvalue(), content_type='image/png')

        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                self.client.force_login(self.volunteer)
                detail_response = self.client.get(reverse('need-detail', args=(need.pk,)))
                self.assertContains(detail_response, 'Submit completion photo')
                invalid_image = SimpleUploadedFile(
                    'not-an-image.png',
                    b'not a valid image',
                    content_type='image/png',
                )
                invalid_response = self.client.post(
                    reverse('need-completion-submit', args=(need.pk,)),
                    {'proof_image': invalid_image},
                )
                self.assertEqual(invalid_response.status_code, 200)
                self.assertContains(invalid_response, 'Upload a valid image')
                self.assertFalse(NeedCompletionSubmission.objects.filter(need=need).exists())

                response = self.client.post(
                    reverse('need-completion-submit', args=(need.pk,)),
                    {'proof_image': image},
                )

                self.assertRedirects(response, reverse('need-detail', args=(need.pk,)))
                submission = NeedCompletionSubmission.objects.get(need=need)
                self.assertEqual(submission.submitted_by, self.volunteer)
                self.assertEqual(submission.review_status, NeedCompletionSubmission.ReviewStatus.PENDING)
                need.refresh_from_db()
                self.assertNotEqual(need.status, BeneficiaryNeed.Status.FULFILLED)
                self.assertTrue(submission.proof_image.storage.exists(submission.proof_image.name))

                repeated_image_buffer = BytesIO()
                Image.new('RGB', (2, 2), color='red').save(repeated_image_buffer, format='PNG')
                repeated_image = SimpleUploadedFile(
                    'another-proof.png',
                    repeated_image_buffer.getvalue(),
                    content_type='image/png',
                )
                repeated_response = self.client.post(
                    reverse('need-completion-submit', args=(need.pk,)),
                    {'proof_image': repeated_image},
                )
                self.assertEqual(repeated_response.status_code, 200)
                self.assertContains(repeated_response, 'already awaiting system administrator review')
                self.assertEqual(NeedCompletionSubmission.objects.filter(need=need).count(), 1)

        self.client.force_login(self.beneficiary)
        self.assertEqual(
            self.client.get(reverse('need-completion-submit', args=(need.pk,))).status_code,
            403,
        )

    def test_system_admin_can_review_submission_and_only_staff_can_view_proof(self):
        need = BeneficiaryNeed.objects.create(
            barangay='San Isidro',
            household_size=2,
            need_type=BeneficiaryNeed.NeedType.WATER,
            description='Provide drinking water.',
            reported_by=self.beneficiary,
        )
        reviewer = CommunityUser.objects.create_user(
            username='reviewer',
            password='test-password-123',
            role=CommunityUser.Role.LEADER,
            is_staff=True,
            is_superuser=True,
        )
        image_buffer = BytesIO()
        Image.new('RGB', (2, 2), color='green').save(image_buffer, format='PNG')
        image = SimpleUploadedFile('proof.png', image_buffer.getvalue(), content_type='image/png')

        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                submission = NeedCompletionSubmission.objects.create(
                    need=need,
                    submitted_by=self.volunteer,
                    proof_image=image,
                )
                proof_url = reverse('need-completion-proof', args=(submission.pk,))
                self.client.force_login(self.volunteer)
                self.assertEqual(self.client.get(proof_url).status_code, 403)

                self.client.force_login(reviewer)
                proof_response = self.client.get(proof_url)
                self.assertEqual(proof_response.status_code, 200)
                self.assertEqual(proof_response['Content-Type'], 'image/png')
                self.assertEqual(proof_response['Cache-Control'], 'private, no-store')
                proof_response.close()

                response = self.client.post(
                    reverse(
                        'admin:community_resilience_needcompletionsubmission_change',
                        args=(submission.pk,),
                    ),
                    {
                        'review_status': NeedCompletionSubmission.ReviewStatus.APPROVED,
                        'review_notes': 'The completion was verified.',
                        '_save': 'Save',
                    },
                )

                self.assertEqual(response.status_code, 302)
                submission.refresh_from_db()
                need.refresh_from_db()
                self.assertEqual(submission.review_status, NeedCompletionSubmission.ReviewStatus.APPROVED)
                self.assertEqual(submission.reviewed_by, reviewer)
                self.assertIsNotNone(submission.reviewed_at)
                self.assertEqual(need.status, BeneficiaryNeed.Status.FULFILLED)

    def test_rejected_completion_can_be_submitted_again_with_new_photo(self):
        need = BeneficiaryNeed.objects.create(
            barangay='San Isidro',
            household_size=2,
            need_type=BeneficiaryNeed.NeedType.WATER,
            description='Provide drinking water.',
            reported_by=self.beneficiary,
            status=BeneficiaryNeed.Status.IN_PROGRESS,
        )
        reviewer = CommunityUser.objects.create_user(
            username='reviewer',
            password='test-password-123',
            role=CommunityUser.Role.LEADER,
            is_staff=True,
            is_superuser=True,
        )
        image_buffer = BytesIO()
        Image.new('RGB', (2, 2), color='yellow').save(image_buffer, format='PNG')
        image = SimpleUploadedFile('proof.png', image_buffer.getvalue(), content_type='image/png')

        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                submission = NeedCompletionSubmission.objects.create(
                    need=need,
                    submitted_by=self.volunteer,
                    proof_image=image,
                )
                self.client.force_login(reviewer)
                response = self.client.post(
                    reverse(
                        'admin:community_resilience_needcompletionsubmission_change',
                        args=(submission.pk,),
                    ),
                    {
                        'review_status': NeedCompletionSubmission.ReviewStatus.REJECTED,
                        'review_notes': 'Please upload a clearer photo.',
                        '_save': 'Save',
                    },
                )
                self.assertEqual(response.status_code, 302)
                submission.refresh_from_db()
                need.refresh_from_db()
                self.assertEqual(submission.review_status, NeedCompletionSubmission.ReviewStatus.REJECTED)
                self.assertEqual(need.status, BeneficiaryNeed.Status.IN_PROGRESS)

                image_buffer = BytesIO()
                Image.new('RGB', (2, 2), color='purple').save(image_buffer, format='PNG')
                replacement_image = SimpleUploadedFile(
                    'replacement.png',
                    image_buffer.getvalue(),
                    content_type='image/png',
                )
                self.client.force_login(self.volunteer)
                response = self.client.post(
                    reverse('need-completion-submit', args=(need.pk,)),
                    {'proof_image': replacement_image},
                )
                self.assertRedirects(response, reverse('need-detail', args=(need.pk,)))
                self.assertEqual(
                    NeedCompletionSubmission.objects.filter(
                        need=need,
                        review_status=NeedCompletionSubmission.ReviewStatus.PENDING,
                    ).count(),
                    1,
                )

    def test_authenticated_user_can_report_a_need(self):
        self.client.force_login(self.beneficiary)
        response = self.client.post(reverse('need-create'), {
            'barangay': 'San Isidro',
            'household_size': 3,
            'need_type': BeneficiaryNeed.NeedType.EVACUATION,
            'description': 'An older resident needs transport to the evacuation center.',
            'priority': BeneficiaryNeed.Priority.URGENT,
        })
        self.assertRedirects(response, reverse('need-list'))
        self.assertTrue(
            BeneficiaryNeed.objects.filter(reported_by=self.beneficiary, barangay='San Isidro').exists()
        )
