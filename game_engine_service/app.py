import uuid
import signal
import requests
from flask import Flask, jsonify, request
from pymongo import MongoClient

app = Flask(__name__)

client = MongoClient('mongodb://gamesdb:27017')
db = client['quiz_game_db']
games_collection = db['games']
questions_collection = db['questions']

USER_SERVICE_URL = "http://user_management_service:5002"


class TimeoutException(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutException("Task timeout exceeded")


DEFAULT_TIMEOUT = 5


@app.before_request
def before_request():
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(DEFAULT_TIMEOUT)


@app.after_request
def after_request(response):
    signal.alarm(0)  #
    return response


@app.errorhandler(TimeoutException)
def handle_timeout_error(e):
    return jsonify({"error": str(e)}), 503


@app.route('/game/status', methods=['GET'])
def status():
    return jsonify({
        "status": "Service is running",
        "service": "Game Engine Service",
        "version": "1.0.0"
    }), 200


@app.route('/game/start-game', methods=['POST'])
def start_game():
    response = requests.get(f"{USER_SERVICE_URL}/users")

    if response.status_code == 200:
        users = response.json()

        if not users:
            return jsonify({"error": "No users found."}), 404

        game_data = {"status": "in_progress", "players_scores": {user['_id']: 0 for user in users},
                     '_id': str(uuid.uuid4())}

        games_collection.insert_one(game_data)

        return jsonify({
            "message": "Game started for all users!",
            "game": game_data,
            "players": [user['name'] for user in users]  # Return player names
        }), 200
    else:
        return jsonify({"error": "Unable to fetch users from User Management Service."}), response.status_code


@app.route('/game/game-status/<game_id>', methods=['GET'])
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
def post_question():
    question_data = request.json

    # Validate the question data
    required_fields = ['question', 'options', 'correct_answer']
    for field in required_fields:
        if field not in question_data:
            return jsonify({"error": f"{field} is required."}), 400

    question_data['_id'] = str(uuid.uuid4())
    questions_collection.insert_one(question_data)

    return jsonify({"message": "Question posted successfully!", "question": question_data}), 201


@app.route('/game/submit-answer/<game_id>/<user_id>/<question_id>', methods=['POST'])
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
            {"$inc": {f"players_scores.{user_id}": 1}}  # Increment the score by 1
        )
        updated_game = games_collection.find_one({"_id": game_id})
        return jsonify({"message": "Correct answer!", "new_score": updated_game['players_scores'][user_id]}), 200
    else:
        return jsonify({"message": "Incorrect answer."}), 200


@app.route('/game/questions', methods=['GET'])
def get_all_questions():
    questions = list(questions_collection.find({}))
    for question in questions:
        question['_id'] = str(question['_id'])
    return jsonify(questions), 200


@app.route('/game/questions/<question_id>', methods=['GET'])
def get_question(question_id):
    question = questions_collection.find_one({"_id": question_id})
    if not question:
        return jsonify({"error": "Question not found"}), 404
    return jsonify(question), 200
