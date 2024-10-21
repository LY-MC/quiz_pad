import eventlet
eventlet.monkey_patch()

import time
import logging
from flask import Flask, jsonify, request
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import uuid
from functools import wraps
from collections import deque
from datetime import datetime, timedelta
from flask_socketio import SocketIO, send, join_room
import signal

USER_SERVICE_URL = "http://user_management_service:5002"

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

client = MongoClient('mongodb://gamesdb:27017')
db = client['quiz_game_db']
games_collection = db['games']
questions_collection = db['questions']

executor = ThreadPoolExecutor(max_workers=2)

class TimeoutException(Exception):
    pass

def timeout_decorator(timeout):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            signal.alarm(timeout)
            try:
                return func(*args, **kwargs)
            except TimeoutException:
                return "Task timeout exceeded", 503
            finally:
                signal.alarm(0)
        return wrapper
    return decorator

class CircuitBreaker:
    def __init__(self, failure_threshold, recovery_timeout):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = 'CLOSED'
        self.last_failure_time = None

    def call(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            app.logger.info(f"Current state: {self.state}, failure count: {self.failure_count}")
            if self.state == 'OPEN':
                if datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                    self.state = 'HALF_OPEN'
                    app.logger.info(f"Circuit breaker state changed to HALF_OPEN for {func.__name__}")
                else:
                    app.logger.error(f"Circuit breaker OPEN: {func.__name__}")
                    return jsonify({"error": "Service unavailable", "failure_count": self.failure_count}), 503
            try:
                response = func(*args, **kwargs)
                if self.state == 'HALF_OPEN':
                    self.state = 'CLOSED'
                    app.logger.info(f"Circuit breaker state changed to CLOSED for {func.__name__}")
                self.failure_count = 0 
                app.logger.info(f"Request succeeded, resetting failure count to {self.failure_count}")
                return response
            except Exception as e:
                self.failure_count += 1
                app.logger.error(f"Exception in {func.__name__}: {e}")
                app.logger.info(f"Incremented failure count to {self.failure_count}")
                if self.failure_count >= self.failure_threshold:
                    self.state = 'OPEN'
                    self.last_failure_time = datetime.now()
                    app.logger.error(f"Circuit breaker triggered: {func.__name__}")
                    return jsonify({"error": "Service unavailable", "failure_count": self.failure_count}), 503
                return jsonify({"error": "Temporary unavailable", "failure_count": self.failure_count}), 503

        return wrapper

circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

@app.route('/game/simulate-failure', methods=['GET'])
@circuit_breaker.call
@timeout_decorator(3)
def simulate_failure():
    raise Exception("Simulated failure")


@app.route('/health')
def health():
    return 'OK', 200

@app.route('/game/status', methods=['GET'])
@circuit_breaker.call
@timeout_decorator(3)
def status():
    # time.sleep(200)
    return jsonify({
        "status": "Service is running",
        "service": "Game Engine Service",
        "version": "1.0.0"
    }), 200

@app.route('/game/start-game', methods=['POST'])
@circuit_breaker.call
@timeout_decorator(3)
def start_game():
    game_data = {
        "status": "in_progress",
        "players_scores": {},
        '_id': str(uuid.uuid4())
    }

    games_collection.insert_one(game_data)

    # Notify all clients that the game has started
    print("Emitting game_started event")  # Debug print statement
    socketio.emit('game_started', {
        "message": "Game started!",
        "game": game_data
    })

    return jsonify({
        "message": "Game started!",
        "game": game_data
    }), 200

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Global dictionary to manage game rooms
game_rooms = {}

@socketio.on('join_game')
@circuit_breaker.call
@timeout_decorator(3)
def join_game(data):
    game_id = data['game_id']
    user_id = data['user_id']
    sid = request.sid
    game = games_collection.find_one({"_id": game_id})
    logging.debug(f"Initial game rooms state: {game_rooms}")

    if not game:
        send({"error": "Game not found"}, room=sid)
        return

    if user_id in game['players_scores']:
        send({"message": "User already in the game"}, room=sid)
        return

    # Update player scores in the database
    games_collection.update_one(
        {"_id": game_id},
        {"$set": {f"players_scores.{user_id}": 0}}
    )

    updated_game = games_collection.find_one({"_id": game_id})

    # Ensure game_rooms has an entry for the game_id
    game_rooms.setdefault(game_id, []).append(sid)
        
    # Log the current state of game rooms
    logging.debug(f"Current game rooms: {game_rooms}")

    # Send a message to the new user
    send({"message": "You joined the game!", "game": updated_game}, room=sid)

    # Notify all connected users in the room that a new player has joined
    message = f"User {user_id} joined the game!"
    for user_sid in game_rooms[game_id]:
        if user_sid != sid:  # Avoid sending the message back to the new user
            send({"message": message, "game": updated_game}, room=user_sid)


@app.route('/game/game-status/<game_id>', methods=['GET'])
@circuit_breaker.call
@timeout_decorator(3)
def get_game_status(game_id):
    game = games_collection.find_one({"_id": game_id})
    if not game:
        return jsonify({"error": "Game not found"}), 404
    return jsonify({
        "game_id": str(game_id),
        "status": game['status'],
        "players_scores": game['players_scores']
    }), 200

@socketio.on('post_question')
@circuit_breaker.call
@timeout_decorator(3)
def post_question(data):
    game_id = data['game_id']
    question_data = data['question_data']

    required_fields = ['question', 'options', 'correct_answer']
    for field in required_fields:
        if field not in question_data:
            send({"error": f"{field} is required."}, room=request.sid)
            return

    question_data['_id'] = str(uuid.uuid4())
    questions_collection.insert_one(question_data)

    send({"message": "Question posted successfully!", "question": question_data}, room=game_id)

@app.route('/game/submit-answer/<game_id>/<user_id>/<question_id>', methods=['POST'])
@circuit_breaker.call
@timeout_decorator(3)
def submit_answer(game_id, user_id, question_id):
    data = request.json
    submitted_answer = data.get('answer')

    game = games_collection.find_one({"_id": game_id})
    if not game:
        return jsonify({"error": "Game not found"}), 404

    if user_id not in game['players_scores']:
        return jsonify({"error": "User not part of the game"}), 400

    question = questions_collection.find_one({"_id": question_id})

    if not question:
        return jsonify({"error": "Question not found"}), 404

    if submitted_answer == question['correct_answer']:
        games_collection.update_one(
            {"_id": game_id},
            {"$inc": {f"players_scores.{user_id}": 1}} 
        )
        updated_game = games_collection.find_one({"_id": game_id})

        return jsonify({"message": "Correct answer!", "new_score": updated_game['players_scores'][user_id]}), 200
    else:
        return jsonify({"message": "Incorrect answer."}), 200

@app.route('/game/questions', methods=['GET'])
@circuit_breaker.call
@timeout_decorator(3)
def get_all_questions():
    questions = list(questions_collection.find({}))
    for question in questions:
        question['_id'] = str(question['_id'])
    return jsonify(questions), 200

@app.route('/game/questions/<question_id>', methods=['GET'])
@circuit_breaker.call
@timeout_decorator(3)
def get_question(question_id):
    question = questions_collection.find_one({"_id": question_id})
    if not question:
        return jsonify({"error": "Question not found"}), 404
    return jsonify(question), 200

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5003)