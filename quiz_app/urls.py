from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views, api_views, auth_views, quiz_views

urlpatterns = [
    # ===== Original Views =====
    path('', views.home, name='home'),
    path('join/', views.join_room, name='join_room'),
    path('quiz/<str:room_code>/', views.quiz_room, name='quiz_room'),
    
    # ===== Authentication Endpoints =====
    path('api/auth/register/', auth_views.register_host, name='register'),
    path('api/auth/login/', auth_views.login_host, name='login'),
    path('api/auth/profile/', auth_views.get_user_profile, name='profile'),
    path('api/auth/logout/', auth_views.logout_host, name='logout'),
    
    # ===== Quiz Management (Host) =====
    path('api/quizzes/', quiz_views.get_my_quizzes, name='my_quizzes'),
    path('api/quizzes/create/', quiz_views.create_quiz, name='create_quiz'),
    path('api/quizzes/<int:quiz_id>/questions/', quiz_views.add_question, name='add_question'),
    path('api/quizzes/<int:quiz_id>/questions/', quiz_views.add_question, name='add_question'),
    path('api/quizzes/<int:quiz_id>/questions/list/', quiz_views.get_quiz_questions, name='get_quiz_questions'),
    path('api/quizzes/<int:quiz_id>/room/', quiz_views.create_room, name='create_room'),
    
    # ===== Room Management =====
    path('api/rooms/<str:room_code>/', quiz_views.get_room_info, name='room_info'),
    path('api/rooms/<str:room_code>/join/', quiz_views.join_room, name='api_join_room'),
    
    # ===== Real-time API Endpoints (Polling) =====
    path('api/quiz/<str:room_code>/start/', csrf_exempt(api_views.start_quiz), name='api_start_quiz'),
    path('api/quiz/<str:room_code>/next/', csrf_exempt(api_views.next_question), name='api_next_question'),
    path('api/quiz/<str:room_code>/submit/', csrf_exempt(api_views.submit_answer), name='api_submit_answer'),
    path('api/quiz/<str:room_code>/state/', api_views.get_quiz_state, name='api_quiz_state'),
    path('api/quiz/<str:room_code>/leaderboard/', api_views.get_leaderboard, name='api_leaderboard'),
]

