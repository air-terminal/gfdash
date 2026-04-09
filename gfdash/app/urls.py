from django.urls import path, re_path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [

    # 認証用URL (re_pathより前に記述)
    path('login/', auth_views.LoginView.as_view(template_name='app/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Matches any html file - to be used for gentella
    # Avoid using your .html in your resources.
    # Or create a separate django app.
    re_path(r'^.*\.html', views.gentella_html, name='gentella'),

    # The home page
    path('', views.gentella_html, name='gentella'),
    path('fileupload/', views.gentella_upload.as_view()),

]
