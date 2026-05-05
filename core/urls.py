from django.urls import path, include
from .views import *

from django.conf import settings
from django.conf.urls.static import static


app_name = "core"

urlpatterns = [
    path("", home, name="home"),
    path("administration", app_administration, name="app_administration"),
    path("administration/song/<int:id>/votes", admin_song_votes, name="admin_song_votes"),
    path('upload', songUpload, name='upload'),
    path('artist/promo', artist_promo, name='artist_promo'),
    # path('add/addrecord/', views.addRecord, name='addrecord'),
    path('delete_songs/<int:id>', delete_song, name='delete_song'),
    path('update/<int:id>', update_song, name='update_song'),
    path('update/updaterecord/<int:id>', updaterecord, name='updaterecord'),
    path('song_view', song_view, name='song_view'),
    path('song_view/hide/<int:id>', hide_song, name='hide_song'),
    path('song_view/unhide/<int:id>', unhide_song, name='unhide_song'),
    path('song_view/reset_votes/<int:id>', reset_song_votes, name='reset_song_votes'),
    path('song_view/publish_status/<int:id>', catalog_publish_song, name='catalog_publish_song'),
    path('song_view/reject_status/<int:id>', catalog_reject_song, name='catalog_reject_song'),
    path('vote_view/<int:id>', vote_view, name='vote_view'),
    path('accept/<int:id>', accept_video, name='accept_video'),
    path('publish/<int:id>', publish_video, name='publish_video'),
    path('reject/<int:id>', reject_video, name='reject_video'),
    path('about', about, name='about'),
    path('vote', vote, name='vote'),
    path('confirm_vote/<str:token>',confirm_vote, name='confirm_vote'),
    path('contact_us',contact, name='contact'),

    
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)