"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from community_resilience import admin_views

urlpatterns = [
    path('admin/', admin_views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/accounts/', admin_views.AdminUserListView.as_view(), name='admin-users'),
    path('admin/accounts/new/', admin_views.AdminUserCreateView.as_view(), name='admin-user-create'),
    path('admin/accounts/<int:pk>/edit/', admin_views.AdminUserUpdateView.as_view(), name='admin-user-update'),
    path('admin/reviews/', admin_views.AdminReviewListView.as_view(), name='admin-reviews'),
    path('admin/reviews/<int:pk>/', admin_views.AdminReviewView.as_view(), name='admin-review'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('community_resilience.urls')),
]
