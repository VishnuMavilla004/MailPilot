from django.urls import path
from . import views

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("sync/", views.sync, name="sync"),
    path("classify/", views.classify, name="classify"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("<int:pk>/", views.email_detail, name="email_detail"),
    path("<int:pk>/draft/", views.make_draft, name="make_draft"),
    path("drafts/<int:pk>/", views.draft_action, name="draft_action"),
    path("<int:pk>/meeting/", views.meeting_create, name="meeting_create"),
    path("<int:pk>/meeting/extract/", views.meeting_extract, name="meeting_extract"),
]