from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from .models import Quiz, Question, Room, Participant

# Avatar choices
AVATARS = ['avatar1', 'avatar2', 'avatar3', 'avatar4', 'avatar5']

def home(request):
    """Display the home page"""
    context = {
        'title': 'GroupGlow - Quiz Application'
    }
    return render(request, 'home.html', context)

def join_room(request):
    """Handle joining a room"""
    if request.method == 'POST':
        name = request.POST.get('name')
        room_code = request.POST.get('room_code')
        avatar = request.POST.get('avatar', 'avatar1')
        
        # Get the room
        room = get_object_or_404(Room, room_code=room_code, is_active=True)
        
        # Create participant
        participant = Participant.objects.create(
            room=room,
            name=name,
            avatar=avatar
        )
        
        # Store participant ID in session
        request.session['participant_id'] = participant.id
        
        # Redirect to quiz room
        return redirect('quiz_room', room_code=room_code)
    
    # GET request - show the join form
    context = {
        'avatars': AVATARS
    }
    return render(request, 'join.html', context)

def quiz_room(request, room_code):
    """Display the quiz room with WebSocket support"""
    # Get the room
    room = get_object_or_404(Room, room_code=room_code, is_active=True)
    
    # Get the quiz associated with the room
    quiz = room.quiz
    
    # Get participant from session
    participant_id = request.session.get('participant_id')
    participant = None
    if participant_id:
        try:
            participant = Participant.objects.get(id=participant_id, room=room)
        except Participant.DoesNotExist:
            participant = None
    
    if not participant:
        return redirect('join_room')
    
    context = {
        'room': room,
        'quiz': quiz,
        'participant': participant,
    }
    return render(request, 'quiz.html', context)
