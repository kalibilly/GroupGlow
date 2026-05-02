from django.contrib import admin
from .models import Quiz, Question, Room, Participant

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')
    search_fields = ('title',)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'quiz', 'correct_answer')
    search_fields = ('question_text',)
    list_filter = ('quiz',)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_code', 'quiz', 'is_active', 'current_question_index')
    search_fields = ('room_code',)
    list_filter = ('is_active', 'quiz')

@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('name', 'room', 'avatar', 'score', 'joined_at')
    search_fields = ('name',)
    list_filter = ('room',)
