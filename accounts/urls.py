from django.urls import path
from .views import *

app_name = "accounts"

urlpatterns = [
    path('register', register_user, name='register'),
    path('login', login_user, name='login'),
   
    # path('forget-password', forget-password name='forget-password'),
    path('logout', logout_user, name='logout'),
    path('list_of_artist', list_of_artist, name='list_of_artist'),
    
]
