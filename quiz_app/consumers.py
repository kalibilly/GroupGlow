import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Room, Participant, Question


class QuizConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time quiz functionality"""

    async def connect(self):
        """Handle WebSocket connection"""
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group_name = f'quiz_{self.room_code}'
        self.participant_name = None

        # Join the room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Notify others that someone joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'message': 'A user joined the quiz'
            }
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'start_quiz':
                await self.handle_start_quiz()
            elif message_type == 'next_question':
                await self.handle_next_question()
            elif message_type == 'submit_answer':
                await self.handle_submit_answer(data)
            elif message_type == 'join':
                self.participant_name = data.get('name')

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))

    # ============ Handler Methods ============

    async def handle_start_quiz(self):
        """Start the quiz - reset and broadcast first question"""
        # Reset room question index
        await self._reset_room()

        # Get and broadcast first question
        question = await self._get_current_question()

        if question:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'send_question',
                    'question_id': question['id'],
                    'question_text': question['text'],
                    'option_a': question['option_a'],
                    'option_b': question['option_b'],
                    'option_c': question['option_c'],
                    'option_d': question['option_d'],
                    'current_index': 0,
                }
            )

            # Broadcast initial leaderboard
            leaderboard = await self._get_leaderboard()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'send_leaderboard',
                    'leaderboard': leaderboard
                }
            )

    async def handle_next_question(self):
        """Move to next question"""
        # Increment question index
        question = await self._increment_and_get_next_question()

        if question:
            # Broadcast next question
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'send_question',
                    'question_id': question['id'],
                    'question_text': question['text'],
                    'option_a': question['option_a'],
                    'option_b': question['option_b'],
                    'option_c': question['option_c'],
                    'option_d': question['option_d'],
                    'current_index': question['current_index'],
                }
            )

            # Broadcast updated leaderboard
            leaderboard = await self._get_leaderboard()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'send_leaderboard',
                    'leaderboard': leaderboard
                }
            )
        else:
            # Quiz ended
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'quiz_complete',
                    'message': 'Quiz completed!'
                }
            )

    async def handle_submit_answer(self, data):
        """Process answer submission"""
        answer = data.get('answer')
        participant_name = data.get('name', self.participant_name)

        if not participant_name or not answer:
            return

        # Get current question
        question = await self._get_current_question()
        if not question:
            return

        # Check answer correctness and update score
        is_correct = answer == question['correct_answer']
        score_change = 0

        if is_correct:
            score_change = 10
        else:
            score_change = -5

        # Update participant score in database
        await self._update_participant_score(participant_name, score_change)

        # Broadcast answer result
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'answer_processed',
                'name': participant_name,
                'is_correct': is_correct,
                'correct_answer': question['correct_answer'],
                'score_change': score_change
            }
        )

    # ============ Database Queries (Async) ============

    @database_sync_to_async
    def _reset_room(self):
        """Reset room question index to 0"""
        try:
            room = Room.objects.get(room_code=self.room_code)
            room.current_question_index = 0
            room.save()
        except Room.DoesNotExist:
            pass

    @database_sync_to_async
    def _get_current_question(self):
        """Get current question based on room index"""
        try:
            room = Room.objects.get(room_code=self.room_code)
            questions = list(room.quiz.questions.all().order_by('id'))
            
            if room.current_question_index < len(questions):
                q = questions[room.current_question_index]
                return {
                    'id': q.id,
                    'text': q.question_text,
                    'option_a': q.option_a,
                    'option_b': q.option_b,
                    'option_c': q.option_c,
                    'option_d': q.option_d,
                    'correct_answer': q.correct_answer,
                    'current_index': room.current_question_index,
                }
            return None
        except Room.DoesNotExist:
            return None

    @database_sync_to_async
    def _increment_and_get_next_question(self):
        """Increment question index and get next question"""
        try:
            room = Room.objects.get(room_code=self.room_code)
            room.current_question_index += 1
            room.save()

            questions = list(room.quiz.questions.all().order_by('id'))

            if room.current_question_index < len(questions):
                q = questions[room.current_question_index]
                return {
                    'id': q.id,
                    'text': q.question_text,
                    'option_a': q.option_a,
                    'option_b': q.option_b,
                    'option_c': q.option_c,
                    'option_d': q.option_d,
                    'correct_answer': q.correct_answer,
                    'current_index': room.current_question_index,
                }
            return None
        except Room.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_leaderboard(self):
        """Get all participants sorted by score"""
        try:
            room = Room.objects.get(room_code=self.room_code)
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
            return leaderboard
        except Room.DoesNotExist:
            return []

    @database_sync_to_async
    def _update_participant_score(self, participant_name, score_change):
        """Update participant score in database"""
        try:
            room = Room.objects.get(room_code=self.room_code)
            participant = room.participants.get(name=participant_name)
            participant.score += score_change
            participant.save()
        except (Room.DoesNotExist, Participant.DoesNotExist):
            pass

    # ============ Group Event Handlers ============

    async def send_question(self, event):
        """Send question to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'question',
            'question_id': event['question_id'],
            'question_text': event['question_text'],
            'option_a': event['option_a'],
            'option_b': event['option_b'],
            'option_c': event['option_c'],
            'option_d': event['option_d'],
            'current_index': event['current_index'],
        }))

    async def send_leaderboard(self, event):
        """Send leaderboard to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'leaderboard',
            'leaderboard': event['leaderboard']
        }))

    async def answer_processed(self, event):
        """Send answer processing result to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'answer_result',
            'name': event['name'],
            'is_correct': event['is_correct'],
            'correct_answer': event['correct_answer'],
            'score_change': event['score_change']
        }))

    async def quiz_complete(self, event):
        """Send quiz completion message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'quiz_complete',
            'message': event['message']
        }))

    async def user_joined(self, event):
        """Notify user joined"""
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'message': event['message']
        }))
