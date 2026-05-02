from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import random
import string

class Quiz(models.Model):
    """Quiz created by a Host/User"""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='quizzes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} by {self.created_by.username}"

    class Meta:
        ordering = ['-created_at']


class Question(models.Model):
    ANSWER_CHOICES = [
        ('A', 'Option A'),
        ('B', 'Option B'),
        ('C', 'Option C'),
        ('D', 'Option D'),
    ]

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_answer = models.CharField(max_length=1, choices=ANSWER_CHOICES)

    def __str__(self):
        return f"Q: {self.question_text[:50]}... ({self.quiz.title})"


class Room(models.Model):
    """Quiz session/room hosted by a user"""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='rooms')
    host = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='hosted_rooms')
    room_code = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    current_question_index = models.IntegerField(default=0)
    is_started = models.BooleanField(default=False)
    is_ended = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Room {self.room_code} - {self.quiz.title} (Host: {self.host.username})"

    @staticmethod
    def generate_room_code():
        """Generate a unique 6-character room code"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not Room.objects.filter(room_code=code).exists():
                return code

    def save(self, *args, **kwargs):
        if not self.room_code:
            self.room_code = self.generate_room_code()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']


class Participant(models.Model):
    """Student/participant joining a quiz room"""
    AVATAR_CHOICES = [
        ('avatar1', 'Blue Character'),
        ('avatar2', 'Red Character'),
        ('avatar3', 'Green Character'),
        ('avatar4', 'Yellow Character'),
        ('avatar5', 'Purple Character'),
    ]
    
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='participants')
    name = models.CharField(max_length=255)
    avatar = models.CharField(max_length=50, choices=AVATAR_CHOICES, default='avatar1')
    score = models.IntegerField(default=0)
    answered_count = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=100, null=True, blank=True)  # For WebSocket tracking

    def __str__(self):
        return f"{self.name} in {self.room.room_code}"

    class Meta:
        ordering = ['-score', '-answered_count', 'joined_at']
        unique_together = [['room', 'name']]
