from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

urlpatterns = [
    path('signup', views.signup, name='signup'),
    path('login', views.login, name="login"),
    path('validate-email', csrf_exempt(views.EmailValidation), name="validate-email"),
    path('validate-phone', csrf_exempt(views.PhoneValidation), name="validate-phone"),
    path('logout', views.logout, name="logout"),
    path('reset-password', csrf_exempt(views.reset_password), name="reset-password"),
    path('set-new-password/<uidb64>/<token>', csrf_exempt(views.complete_reset_password), name="set-new-password")
]
