from flask import Flask, jsonify, request
from pymongo import MongoClient
from functools import wraps
from collections import deque
from datetime import datetime, timedelta
import uuid
import time
import signal
import os

app = Flask(__name__)
client = MongoClient('mongodb://mongodb:27017/')
db = client['users_game_db']
users_collection = db['users']

class TimeoutException(Exception):
    pass

def timeout_decorator(timeout):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            signal.alarm(timeout)
            try:
                return func(*args, **kwargs)
            except TimeoutException as e:
                return jsonify({"error": str(e)}), 503
            finally:
                signal.alarm(0)
        return wrapper
    return decorator


@app.route('/users/simulate-failure', methods=['GET'])
def simulate_failure():
    try:
        time.sleep(1)
        if int(os.getenv('FAIL')):
            raise Exception(f"{os.getenv('SERVICE_ADDRESS')} simulated failure")
        else:
            return jsonify({"message": f"{os.getenv('SERVICE_ADDRESS')} managed not to fail"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/users/status', methods=['GET'])
@timeout_decorator(3)
def status():
    return jsonify({
        "status": "Service is running",
        "service": "User Management Service",
        "version": "1.0.0",
        "port": os.getenv('PORT')
    }), 200

@app.route('/users/user/register', methods=['POST'])
@timeout_decorator(3)
def register_user():
    user_data = request.json
    user_data['_id'] = str(uuid.uuid4())
    users_collection.insert_one(user_data)
    return jsonify({"message": "User registered successfully", "user": user_data}), 201

@app.route('/users/<user_id>', methods=['GET'])
@timeout_decorator(3)
def get_user(user_id):
    user = users_collection.find_one({"_id": user_id})
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user), 200

@app.route('/users', methods=['GET'])
@timeout_decorator(3)
def get_all_users():
    # time.sleep(500)
    users = list(users_collection.find())
    return jsonify(users), 200

@app.route('/health', methods=['GET'])
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)