import uuid
import signal
from flask import Flask, jsonify, request
from pymongo import MongoClient

app = Flask(__name__)

client = MongoClient('mongodb://mongodb:27017/')
db = client['users_game_db']
users_collection = db['users']


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
    signal.alarm(0)
    return response


@app.errorhandler(TimeoutException)
def handle_timeout_error(e):
    return jsonify({"error": str(e)}), 503


@app.route('/users/status', methods=['GET'])
def status():
    return jsonify({
        "status": "Service is running",
        "service": "User Management Service",
        "version": "1.0.0"
    }), 200


@app.route('/users/user/register', methods=['POST'])
def register_user():
    user_data = request.json

    required_fields = ['name', 'email', 'age']
    for field in required_fields:
        if field not in user_data:
            return jsonify({"error": f"{field} is required."}), 400

    user_data['_id'] = str(uuid.uuid4())
    users_collection.insert_one(user_data)

    return jsonify({"message": "User registered successfully!",
                    "user": user_data}
                   ), 201


@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    user = users_collection.find_one({"_id": user_id})
    if user:
        return jsonify(user), 200
    return jsonify({"error": "User not found"}), 404


@app.route('/users', methods=['GET'])
def get_all_users():
    users = list(users_collection.find())
    for user in users:
        user['_id'] = str(user['_id'])
    return jsonify(users), 200
