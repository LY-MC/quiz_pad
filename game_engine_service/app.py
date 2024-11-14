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
from flask_socketio import SocketIO, send, emit, join_room, leave_room
import signal
import redis
import threading
import os

USER_SERVICE_URL = "http://user_management_service:5002"

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

client = MongoClient('mongodb://gamesdb:27017')
db = client['quiz_game_db']
games_collection = db['games']
questions_collection = db['questions']
redis_client = redis.StrictRedis(host='redis', port=6379, db=0)
pubsub = redis_client.pubsub()

executor = ThreadPoolExecutor(max_workers=2)

class TimeoutException(Exception):
    pass


def broadcast_messages():
    """Function to publish messages to all WebSocket clients every 5 seconds."""
    while True:
        socketio.emit('broadcast_message', {"message": "This is a broadcast message to all clients"})
        socketio.sleep(5)  # Sleep for 5 seconds before sending the next message
        
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

@app.route('/game/simulate-failure', methods=['GET'])
@timeout_decorator(3)
def simulate_failure():
    raise Exception("Simulated failure")


@app.route('/health')
def health():
    return 'OK', 200

@app.route('/game/status', methods=['GET'])
@timeout_decorator(3)
def status():
    return jsonify({
        "status": "Service is running",
        "service": "Game Engine Service",
        "version": "1.0.0",
        "port": os.getenv('PORT')
    }), 200

@app.route('/game/start-game', methods=['POST'])
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

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    send('Connected to WebSocket server')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('join_game')
@timeout_decorator(3)
def join_game(data):
    game_id = data['game_id']
    user_id = data['user_id']
    sid = request.sid

    game = games_collection.find_one({"_id": game_id})
    logging.debug(f"Joining game: {game_id} by user: {user_id}")

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

    # Send a message to the user who just joined
    send({"message": "You joined the game!", "game": updated_game}, room=sid)

    # Join the user to the game room
    join_room(game_id)
    logging.debug(f"User {user_id} joined room: {game_id}")

    # Debug: Check existing rooms
    logging.debug(f"Current rooms: {socketio.server.manager.rooms}")
        # Notify only users in the same game room
    socketio.emit('user_joined', {
        "message": f"User {user_id} has joined the game!",
        "game_id": game_id
    }, room=game_id)  # Specify the room as the game_id
    logging.debug(f"Emitted 'user_joined' to room: {game_id}")

@socketio.on('leave_game')
def on_leave(data):
    game_id = data['game_id']
    user_id = data['user_id']
    leave_room(game_id)
    send(user_id + ' has left the room.', to=game_id)

@app.route('/game/game-status/<game_id>', methods=['GET'])
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

@app.route('/game/post-question', methods=['POST'])
@timeout_decorator(3)
def post_question():
    try:
        question_data = request.json
        question_data['_id'] = str(uuid.uuid4())
        questions_collection.insert_one(question_data)
        return jsonify({"message": "Question posted successfully", "question": question_data}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@socketio.on_error()        # Handles the default namespace
def error_handler(e):
    print(f"An error has occurred: {e}")

@socketio.on_error_default  # handles all namespaces without an explicit error handler
def default_error_handler(e):
    print(f"An error has occurred: {e}")

@app.route('/game/submit-answer/<game_id>/<user_id>/<question_id>', methods=['POST'])
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
@timeout_decorator(3)
def get_all_questions():
    questions = list(questions_collection.find({}))
    for question in questions:
        question['_id'] = str(question['_id'])
    return jsonify(questions), 200

@app.route('/game/questions/<question_id>', methods=['GET'])
@timeout_decorator(3)
def get_question(question_id):
    question = questions_collection.find_one({"_id": question_id})
    if not question:
        return jsonify({"error": "Question not found"}), 404
    return jsonify(question), 200

def redis_listener():
    pubsub.subscribe([game_id for game_id in game_rooms.keys()])
    for message in pubsub.listen():
        if message['type'] == 'message':
            game_id = message['channel'].decode('utf-8')
            data = message['data'].decode('utf-8')
            socketio.emit('user_joined', {"message": data}, room=game_id)

# Start the broadcast message thread
broadcast_thread = threading.Thread(target=broadcast_messages)
broadcast_thread.daemon = True  # This ensures the thread will close when the main program exits
broadcast_thread.start()

if __name__ == '__main__':
    listener_thread = threading.Thread(target=redis_listener)
    listener_thread.start()
    socketio.run(app, host='0.0.0.0', port=5003)