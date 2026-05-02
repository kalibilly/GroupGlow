"""Quiz and Room management views"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import json
from .models import Quiz, Question, Room, Participant


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_quiz(request):
    """Host creates a new quiz"""
    try:
        data = request.data
        title = data.get('title')
        description = data.get('description', '')
        
        if not title:
            return Response({'error': 'Title required'}, status=status.HTTP_400_BAD_REQUEST)
        
        quiz = Quiz.objects.create(
            title=title,
            description=description,
            created_by=request.user
        )
        
        return Response({
            'status': 'success',
            'quiz': {
                'id': quiz.id,
                'title': quiz.title,
                'description': quiz.description,
            }
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_question(request, quiz_id):
    """Host adds a question to a quiz"""
    try:
        quiz = Quiz.objects.get(id=quiz_id, created_by=request.user)
        data = request.data
        
        question = Question.objects.create(
            quiz=quiz,
            question_text=data.get('question_text'),
            option_a=data.get('option_a'),
            option_b=data.get('option_b'),
            option_c=data.get('option_c'),
            option_d=data.get('option_d'),
            correct_answer=data.get('correct_answer')
        )
        
        return Response({
            'status': 'success',
            'question': {
                'id': question.id,
                'question_text': question.question_text,
            }
        }, status=status.HTTP_201_CREATED)
    except Quiz.DoesNotExist:
        return Response({'error': 'Quiz not found or not owned by you'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_quizzes(request):
    """Host gets their quizzes"""
    quizzes = Quiz.objects.filter(created_by=request.user)
    return Response({
        'quizzes': [{
            'id': q.id,
            'title': q.title,
            'description': q.description,
            'question_count': q.questions.count(),
            'created_at': q.created_at,
        } for q in quizzes]
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_quiz_questions(request, quiz_id):
    """Host retrieves questions for a specific quiz"""
    try:
        quiz = Quiz.objects.get(id=quiz_id, created_by=request.user)
        return Response({
            'quiz': {
                'id': quiz.id,
                'title': quiz.title,
                'description': quiz.description,
                'questions': [{
                    'id': q.id,
                    'question_text': q.question_text,
                    'option_a': q.option_a,
                    'option_b': q.option_b,
                    'option_c': q.option_c,
                    'option_d': q.option_d,
                    'correct_answer': q.correct_answer,
                } for q in quiz.questions.all()]
            }
        })
    except Quiz.DoesNotExist:
        return Response({'error': 'Quiz not found or not owned by you'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_room(request, quiz_id):
    """Host creates a new room for a quiz"""
    try:
        quiz = Quiz.objects.get(id=quiz_id, created_by=request.user)
        
        room = Room.objects.create(
            quiz=quiz,
            host=request.user,
        )
        
        return Response({
            'status': 'success',
            'room': {
                'id': room.id,
                'room_code': room.room_code,
                'quiz_title': quiz.title,
                'quiz_id': quiz.id,
            }
        }, status=status.HTTP_201_CREATED)
    except Quiz.DoesNotExist:
        return Response({'error': 'Quiz not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_room_info(request, room_code):
    """Get room information (students and hosts)"""
    try:
        room = Room.objects.get(room_code=room_code)
        participants = room.participants.all()
        
        return Response({
            'room': {
                'id': room.id,
                'room_code': room.room_code,
                'quiz_title': room.quiz.title,
                'quiz_id': room.quiz.id,
                'host_username': room.host.username,
                'is_started': room.is_started,
                'is_ended': room.is_ended,
                'current_question_index': room.current_question_index,
                'total_questions': room.quiz.questions.count(),
                'participants': [{
                    'id': p.id,
                    'name': p.name,
                    'avatar': p.avatar,
                    'score': p.score,
                } for p in participants]
            }
        })
    except Room.DoesNotExist:
        return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(['POST'])
def join_room(request, room_code):
    """Student joins a room (no auth required)"""
    try:
        data = json.loads(request.body)
        name = data.get('name')
        avatar = data.get('avatar', 'avatar1')
        
        if not name:
            return JsonResponse({'error': 'Name required'}, status=400)
        
        room = Room.objects.get(room_code=room_code)
        
        # Check if already joined
        participant, created = Participant.objects.get_or_create(
            room=room,
            name=name,
            defaults={'avatar': avatar, 'session_id': f"{room_code}_{name}_{int(__import__('time').time())}"}
        )
        
        return JsonResponse({
            'status': 'success',
            'participant': {
                'id': participant.id,
                'name': participant.name,
                'avatar': participant.avatar,
                'score': participant.score,
                'session_id': participant.session_id,
            },
            'room': {
                'id': room.id,
                'room_code': room.room_code,
                'quiz_title': room.quiz.title,
                'is_started': room.is_started,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Room.DoesNotExist:
        return JsonResponse({'error': 'Room not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
