"""WebSocket consumer for real-time quiz events"""
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Room, Participant, Question


class QuizConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time quiz interactions
    
    Events:
    - join: Join a quiz room
    - start_quiz: Start the quiz (host only)
    - next_question: Move to next question (host only)
    - submit_answer: Submit an answer
    - end_quiz: End the quiz (host only)
    """

    async def connect(self):
        """Handle WebSocket connection"""
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group_name = f'quiz_{self.room_code}'
        self.participant_id = None
        self.participant_name = None

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Remove participant if they existed
        if self.participant_id:
            await self._mark_participant_offline()
        
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            event_type = data.get('type')

            if event_type == 'join':
                await self.handle_join(data)
            elif event_type == 'start_quiz':
                await self.handle_start_quiz(data)
            elif event_type == 'next_question':
                await self.handle_next_question(data)
            elif event_type == 'submit_answer':
                await self.handle_submit_answer(data)
            elif event_type == 'end_quiz':
                await self.handle_end_quiz(data)
            elif event_type == 'get_leaderboard':
                await self.handle_get_leaderboard(data)
            else:
                await self.send(text_data=json.dumps({
                    'error': f'Unknown event type: {event_type}'
                }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'error': 'Invalid JSON'}))
        except Exception as e:
            await self.send(text_data=json.dumps({'error': str(e)}))

    async def handle_join(self, data):
        """Handle participant joining room"""
        participant_name = data.get('name')
        avatar = data.get('avatar', 'avatar1')
        role = data.get('role', 'student')

        if not participant_name:
            await self.send(text_data=json.dumps({'error': 'Name required'}))
            return

        room = await self._get_room()

        if role == 'host':
            self.participant_name = participant_name
            await self.send(text_data=json.dumps({
                'type': 'join_success',
                'host': True,
                'room': {
                    'room_code': room.room_code,
                    'quiz_title': room.quiz.title,
                    'is_started': room.is_started,
                }
            }))
            return

        # Create or get participant
        participant = await self._get_or_create_participant(
            participant_name, avatar
        )
        self.participant_id = participant.id
        self.participant_name = participant_name

        participants = await self._get_room_participants()

        # Send join confirmation
        await self.send(text_data=json.dumps({
            'type': 'join_success',
            'participant': {
                'id': participant.id,
                'name': participant.name,
                'avatar': participant.avatar,
                'score': participant.score,
            },
            'room': {
                'room_code': room.room_code,
                'quiz_title': room.quiz.title,
                'is_started': room.is_started,
            }
        }))

        # Broadcast participant joined to all in room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'participant_joined',
                'participant': {
                    'id': participant.id,
                    'name': participant.name,
                    'avatar': participant.avatar,
                    'score': participant.score,
                },
                'total_participants': len(participants)
            }
        )

    async def handle_start_quiz(self, data):
        """Handle host starting quiz"""
        room = await self._get_room()
        is_host = await self._is_host()

        if not is_host:
            await self.send(text_data=json.dumps({'error': 'Only host can start quiz'}))
            return

        # Update room state
        room = await self._start_room_quiz()

        # Get first question
        question = await self._get_question(0)

        if not question:
            await self.send(text_data=json.dumps({'error': 'No questions in quiz'}))
            return

        # Broadcast quiz started
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'quiz_started',
                'question': await self._format_question(question),
                'question_index': 0,
                'total_questions': await self._get_total_questions(),
            }
        )

    async def handle_next_question(self, data):
        """Handle moving to next question"""
        room = await self._get_room()
        is_host = await self._is_host()

        if not is_host:
            await self.send(text_data=json.dumps({'error': 'Only host can advance'}))
            return

        # Update question index
        new_index = room.current_question_index + 1
        total = await self._get_total_questions()

        if new_index >= total:
            # Quiz ended
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'quiz_ended'}
            )
            return

        # Get next question
        room = await self._increment_question_index()
        question = await self._get_question(new_index)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'next_question_event',
                'question': await self._format_question(question),
                'question_index': new_index,
                'total_questions': total,
            }
        )

    async def handle_submit_answer(self, data):
        """Handle participant submitting answer"""
        if not self.participant_id:
            await self.send(text_data=json.dumps({'error': 'Not joined'}))
            return

        answer = data.get('answer')
        if not answer:
            await self.send(text_data=json.dumps({'error': 'Answer required'}))
            return

        # Get current question
        room = await self._get_room()
        question = await self._get_question(room.current_question_index)

        if not question:
            await self.send(text_data=json.dumps({'error': 'Question not found'}))
            return

        # Check answer
        is_correct = answer == question.correct_answer
        points = 10 if is_correct else -5

        # Update participant score
        participant = await self._update_participant_score(points)

        # Send feedback to participant
        await self.send(text_data=json.dumps({
            'type': 'answer_processed',
            'is_correct': is_correct,
            'correct_answer': question.correct_answer,
            'points': points,
            'new_score': participant.score,
        }))

        # Broadcast leaderboard update
        leaderboard = await self._get_leaderboard()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'leaderboard_updated',
                'leaderboard': leaderboard,
            }
        )

    async def handle_get_leaderboard(self, data):
        """Send current leaderboard"""
        leaderboard = await self._get_leaderboard()
        await self.send(text_data=json.dumps({
            'type': 'leaderboard',
            'leaderboard': leaderboard,
        }))

    async def handle_end_quiz(self, data):
        """Handle host ending quiz"""
        is_host = await self._is_host()

        if not is_host:
            await self.send(text_data=json.dumps({'error': 'Only host can end'}))
            return

        await self._cleanup_room()
        leaderboard = await self._get_leaderboard()

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'quiz_ended_event',
                'final_leaderboard': leaderboard,
            }
        )

    # WebSocket group events

    async def participant_joined(self, event):
        """Broadcast participant joined"""
        await self.send(text_data=json.dumps({
            'type': 'participant_joined',
            'participant': event['participant'],
            'total_participants': event['total_participants'],
        }))

    async def quiz_started(self, event):
        """Broadcast quiz started"""
        await self.send(text_data=json.dumps({
            'type': 'quiz_started',
            'question': event['question'],
            'question_index': event['question_index'],
            'total_questions': event['total_questions'],
        }))

    async def next_question_event(self, event):
        """Broadcast next question"""
        await self.send(text_data=json.dumps({
            'type': 'next_question',
            'question': event['question'],
            'question_index': event['question_index'],
            'total_questions': event['total_questions'],
        }))

    async def leaderboard_updated(self, event):
        """Broadcast leaderboard update"""
        await self.send(text_data=json.dumps({
            'type': 'leaderboard_updated',
            'leaderboard': event['leaderboard'],
        }))

    async def quiz_ended_event(self, event):
        """Broadcast quiz ended"""
        await self.send(text_data=json.dumps({
            'type': 'quiz_ended',
            'final_leaderboard': event['final_leaderboard'],
        }))

    # Database helper methods

    @database_sync_to_async
    def _get_room(self):
        return Room.objects.get(room_code=self.room_code)

    @database_sync_to_async
    def _get_or_create_participant(self, name, avatar):
        room = Room.objects.get(room_code=self.room_code)
        participant, created = Participant.objects.get_or_create(
            room=room,
            name=name,
            defaults={'avatar': avatar, 'session_id': f"{self.room_code}_{name}"}
        )
        return participant

    @database_sync_to_async
    def _is_host(self):
        room = Room.objects.get(room_code=self.room_code)
        # In WebSocket, we can't easily verify auth, so we check if participant_id is set
        # A proper implementation would verify JWT token
        return room.host.id == getattr(self.scope.get('user'), 'id', None)

    @database_sync_to_async
    def _start_room_quiz(self):
        room = Room.objects.get(room_code=self.room_code)
        room.is_started = True
        room.started_at = timezone.now()
        room.current_question_index = 0
        room.save()
        return room

    @database_sync_to_async
    def _end_room_quiz(self):
        room = Room.objects.get(room_code=self.room_code)
        room.is_ended = True
        room.ended_at = timezone.now()
        room.is_active = False
        room.save()
        return room

    @database_sync_to_async
    def _cleanup_room(self):
        room = Room.objects.get(room_code=self.room_code)
        room.is_ended = True
        room.ended_at = timezone.now()
        room.is_active = False
        room.save()
        room.participants.all().delete()
        return room

    @database_sync_to_async
    def _increment_question_index(self):
        room = Room.objects.get(room_code=self.room_code)
        room.current_question_index += 1
        room.save()
        return room

    @database_sync_to_async
    def _get_question(self, index):
        room = Room.objects.get(room_code=self.room_code)
        try:
            return room.quiz.questions.all()[index]
        except IndexError:
            return None

    @database_sync_to_async
    def _get_total_questions(self):
        room = Room.objects.get(room_code=self.room_code)
        return room.quiz.questions.count()

    @database_sync_to_async
    def _format_question(self, question):
        return {
            'id': question.id,
            'text': question.question_text,
            'options': {
                'A': question.option_a,
                'B': question.option_b,
                'C': question.option_c,
                'D': question.option_d,
            }
        }

    @database_sync_to_async
    def _update_participant_score(self, points):
        participant = Participant.objects.get(id=self.participant_id)
        participant.score += points
        participant.answered_count += 1
        participant.save()
        return participant

    @database_sync_to_async
    def _get_room_participants(self):
        room = Room.objects.get(room_code=self.room_code)
        return list(room.participants.all().order_by('-score'))

    @database_sync_to_async
    def _get_leaderboard(self):
        room = Room.objects.get(room_code=self.room_code)
        participants = room.participants.all().order_by('-score', '-answered_count', 'joined_at')
        return [{
            'rank': idx + 1,
            'name': p.name,
            'avatar': p.avatar,
            'score': p.score,
            'answered': p.answered_count,
        } for idx, p in enumerate(participants)]

    @database_sync_to_async
    def _mark_participant_offline(self):
        if self.participant_id is None:
            return
        try:
            Participant.objects.filter(id=self.participant_id).delete()
        except:
            pass
