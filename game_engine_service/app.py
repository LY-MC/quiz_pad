from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import uuid
from functools import wraps
from collections import deque
from datetime import datetime, timedelta

USER_SERVICE_URL = "http://user_management_service:5002"

app = Flask(__name__)
socketio = SocketIO(app)

client = MongoClient('mongodb://gamesdb:27017')
db = client['quiz_game_db']
games_collection = db['games']
questions_collection = db['questions']

executor = ThreadPoolExecutor(max_workers=2)

class TimeoutException(Exception):
    pass

def run_with_timeout(func, *args, timeout=5):
    future = executor.submit(func, *args)
    try:
        return future.result(timeout=timeout)
    except TimeoutError:
        raise TimeoutException("Task timeout exceeded")

DEFAULT_TIMEOUT = 5

@app.errorhandler(TimeoutException)
def handle_timeout_error(e):
    return jsonify({"error": str(e)}), 503

@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"error": str(e)}), 500

class CircuitBreaker:
    def __init__(self, failure_threshold, recovery_timeout):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = deque(maxlen=failure_threshold)
        self.state = 'CLOSED'
        self.last_failure_time = None

    def call(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == 'OPEN':
                if datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                    self.state = 'HALF_OPEN'
                else:
                    return jsonify({"error": "Service unavailable"}), 503

            try:
                response = func(*args, **kwargs)
                if self.state == 'HALF_OPEN':
                    self.state = 'CLOSED'
                self.failures.clear()
                return response
            except Exception as e:
                self.failures.append(datetime.now())
                if len(self.failures) == self.failure_threshold:
                    self.state = 'OPEN'
                    self.last_failure_time = datetime.now()
                    shutdown = request.environ.get('werkzeug.server.shutdown')
                    if shutdown:
                        shutdown()
                raise e
        return wrapper

circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=int(DEFAULT_TIMEOUT * 3.5))

@app.route('/health')
def health():
    return 'OK', 200

@app.route('/game/status', methods=['GET'])
@circuit_breaker.call
def status():
    return jsonify({
        "status": "Service is running",
        "service": "Game Engine Service",
        "version": "1.0.0"
    }), 200

@app.route('/game/start-game', methods=['POST'])
@circuit_breaker.call
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

@app.route('/game/join/<game_id>/<user_id>', methods=['POST'])
@circuit_breaker.call
def join_game(game_id, user_id):
    game = games_collection.find_one({"_id": game_id})
    if not game:
        return jsonify({"error": "Game not found"}), 404

    if user_id in game['players_scores']:
        return jsonify({"message": "User already in the game"}), 200

    games_collection.update_one(
        {"_id": game_id},
        {"$set": {f"players_scores.{user_id}": 0}}
    )

    updated_game = games_collection.find_one({"_id": game_id})

    # Notify all clients that a new user has joined the game
    print("Emitting user_joined event")  # Debug print statement
    socketio.emit('user_joined', {
        "message": "User joined the game!",
        "game_id": game_id,
        "user_id": user_id,
        "players_scores": updated_game['players_scores']
    })

    return jsonify({"message": "User joined the game!", "game": updated_game}), 200

@app.route('/game/game-status/<game_id>', methods=['GET'])
@circuit_breaker.call
def get_game_status(game_id):
    game = games_collection.find_one({"_id": game_id})
    if not game:
        return jsonify({"error": "Game not found"}), 404
    return jsonify({
        "game_id": str(game_id),
        "status": game['status'],
        "players_scores": game['players_scores']
    }), 200

@app.route('/game/post-question', methods=['POST'])
@circuit_breaker.call
def post_question():
    question_data = request.json

    required_fields = ['question', 'options', 'correct_answer']
    for field in required_fields:
        if field not in question_data:
            return jsonify({"error": f"{field} is required."}), 400

    question_data['_id'] = str(uuid.uuid4())
    questions_collection.insert_one(question_data)

    socketio.emit('new_question', {
        "message": "New question posted!",
        "question": question_data
    })

    return jsonify({"message": "Question posted successfully!", "question": question_data}), 201

@app.route('/game/submit-answer/<game_id>/<user_id>/<question_id>', methods=['POST'])
@circuit_breaker.call
def submit_answer(game_id, user_id, question_id):
    data = request.json
    submitted_answer = data.get('answer')

    # Retrieve the game from the database
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

        socketio.emit('answer_submitted', {
            "message": "Correct answer!",
            "game_id": game_id,
            "user_id": user_id,
            "new_score": updated_game['players_scores'][user_id]
        })

        return jsonify({"message": "Correct answer!", "new_score": updated_game['players_scores'][user_id]}), 200
    else:
        # Notify all clients about the incorrect answer
        socketio.emit('answer_submitted', {
            "message": "Incorrect answer.",
            "game_id": game_id,
            "user_id": user_id
        })

        return jsonify({"message": "Incorrect answer."}), 200

@app.route('/game/questions', methods=['GET'])
@circuit_breaker.call
def get_all_questions():
    questions = list(questions_collection.find({}))
    for question in questions:
        question['_id'] = str(question['_id'])
    return jsonify(questions), 200

@app.route('/game/questions/<question_id>', methods=['GET'])
@circuit_breaker.call
def get_question(question_id):
    question = questions_collection.find_one({"_id": question_id})
    if not question:
        return jsonify({"error": "Question not found"}), 404
    return jsonify(question), 200

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5003)