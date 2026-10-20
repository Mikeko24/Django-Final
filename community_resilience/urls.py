from django.urls import path

from . import views

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('tasks/', views.TaskListView.as_view(), name='task-list'),
    path('tasks/new/', views.TaskCreateView.as_view(), name='task-create'),
    path('tasks/<int:pk>/edit/', views.TaskUpdateView.as_view(), name='task-update'),
    path('tasks/<int:pk>/status/', views.TaskStatusUpdateView.as_view(), name='task-status'),
    path('tasks/<int:pk>/delete/', views.TaskDeleteView.as_view(), name='task-delete'),
    path('resources/', views.ResourceListView.as_view(), name='resource-list'),
    path('resources/new/', views.ResourceCreateView.as_view(), name='resource-create'),
    path('resources/<int:pk>/edit/', views.ResourceUpdateView.as_view(), name='resource-update'),
    path('resources/<int:pk>/delete/', views.ResourceDeleteView.as_view(), name='resource-delete'),
    path('needs/', views.NeedListView.as_view(), name='need-list'),
    path('needs/<int:pk>/', views.NeedDetailView.as_view(), name='need-detail'),
    path('needs/new/', views.NeedCreateView.as_view(), name='need-create'),
    path('needs/<int:pk>/edit/', views.NeedUpdateView.as_view(), name='need-update'),
    path('needs/<int:pk>/delete/', views.NeedDeleteView.as_view(), name='need-delete'),
    path('needs/<int:pk>/submit-completion/', views.NeedCompletionSubmitView.as_view(), name='need-completion-submit'),
    path(
        'needs/completion-submissions/<int:pk>/proof/',
        views.NeedCompletionProofView.as_view(),
        name='need-completion-proof',
    ),
]
