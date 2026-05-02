import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Room, Participant, Question


@require_http_methods(["POST"])
def start_quiz(request, room_code):
    """Start the quiz - reset question index"""
    try:
        room = Room.objects.get(room_code=room_code, is_active=True)
        room.current_question_index = 0
        room.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Quiz started'
        })
    except Room.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Room not found'
        }, status=404)


@require_http_methods(["POST"])
def next_question(request, room_code):
    """Move to next question"""
    try:
        room = Room.objects.get(room_code=room_code, is_active=True)
        room.current_question_index += 1
        room.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Moved to next question',
            'current_index': room.current_question_index
        })
    except Room.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Room not found'
        }, status=404)


@require_http_methods(["POST"])
def submit_answer(request, room_code):
    """Submit an answer"""
    try:
        data = json.loads(request.body)
        answer = data.get('answer')
        participant_name = data.get('name')
        
        room = Room.objects.get(room_code=room_code, is_active=True)
        participant = Participant.objects.get(room=room, name=participant_name)
        
        # Get current question
        questions = list(room.quiz.questions.all().order_by('id'))
        if room.current_question_index >= len(questions):
            return JsonResponse({
                'status': 'error',
                'message': 'Quiz has ended'
            })
        
        current_question = questions[room.current_question_index]
        
        # Check answer and update score
        is_correct = answer == current_question.correct_answer
        if is_correct:
            participant.score += 10
        else:
            if answer:  # Only deduct if an answer was provided
                participant.score -= 5
        
        participant.save()
        
        return JsonResponse({
            'status': 'success',
            'is_correct': is_correct,
            'correct_answer': current_question.correct_answer,
            'score_change': 10 if is_correct else -5,
            'new_score': participant.score
        })
    except (Room.DoesNotExist, Participant.DoesNotExist, json.JSONDecodeError):
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request'
        }, status=400)


@require_http_methods(["GET"])
def get_quiz_state(request, room_code):
    """Get current quiz state"""
    try:
        room = Room.objects.get(room_code=room_code, is_active=True)
        questions = list(room.quiz.questions.all().order_by('id'))
        
        if room.current_question_index >= len(questions):
            return JsonResponse({
                'status': 'complete',
                'message': 'Quiz has ended',
                'current_index': room.current_question_index,
                'total_questions': len(questions)
            })
        
        current_question = questions[room.current_question_index]
        
        return JsonResponse({
            'status': 'in_progress',
            'quiz_title': room.quiz.title,
            'question_id': current_question.id,
            'question_text': current_question.question_text,
            'option_a': current_question.option_a,
            'option_b': current_question.option_b,
            'option_c': current_question.option_c,
            'option_d': current_question.option_d,
            'current_index': room.current_question_index,
            'total_questions': len(questions)
        })
    except Room.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Room not found'
        }, status=404)


@require_http_methods(["GET"])
def get_leaderboard(request, room_code):
    """Get current leaderboard"""
    try:
        room = Room.objects.get(room_code=room_code, is_active=True)
        participants = room.participants.all().order_by('-score')
        
        leaderboard = [
            {
                'rank': idx + 1,
                'name': p.name,
                'avatar': p.avatar,
                'score': p.score
            }
            for idx, p in enumerate(participants)
        ]
        
        return JsonResponse({
            'status': 'success',
            'leaderboard': leaderboard
        })
    except Room.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Room not found'
        }, status=404)
