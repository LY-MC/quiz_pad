from flask import Flask, jsonify, request
from pymongo import MongoClient
from functools import wraps
import uuid
import time
import signal
import os
import logging
import requests
from saga_coordinator import SagaCoordinator, create_user_step, create_game_session_step, delete_user_step, delete_game_session_step

app = Flask(__name__)
client = MongoClient('mongodb://mongodb:27017/')
db = client['users_game_db']
users_collection = db['users']

LOGSTASH_HOST = os.getenv('LOGSTASH_HOST', 'logstash')
LOGSTASH_HTTP_PORT = int(os.getenv('LOGSTASH_HTTP_PORT', 6000))

logger = logging.getLogger('user_management_service')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def logMsg(msg):
    logger.info(msg)
    try:
        requests.post(f'http://{LOGSTASH_HOST}:{LOGSTASH_HTTP_PORT}', json={
            "service": "user_management_service",
            "msg": msg
        })
    except Exception as e:
        logger.error(f"Failed to send log to Logstash: {e}")

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

@app.route('/users/create_with_game', methods=['POST'])
@timeout_decorator(10)
def create_user_with_game():
    user_data = request.json.get('user')
    game_data = {}

    if not user_data:
        return jsonify({"error": "Invalid request data"}), 400

    saga = SagaCoordinator()
    saga.add_step(create_user_step(user_data), delete_user_step(user_data))
    saga.add_step(create_game_session_step(game_data), delete_game_session_step(game_data))
    try:
        saga.execute()
        logMsg(f"User and game session created: {user_data['_id']}, {game_data['_id']}")
        return jsonify({"message": "User and game session created successfully", "user_id": user_data['_id'], "game_id": game_data['_id']}), 201
    except Exception as e:
        logMsg(f"Failed to create user and game session: {e}")
        return jsonify({"error": "Failed to create user and game session"}), 500
    
@app.route('/users/simulate-failure', methods=['GET'])
def simulate_failure():
    try:
        time.sleep(1)
        if int(os.getenv('FAIL')):
            raise Exception(f"{os.getenv('SERVICE_ADDRESS')} simulated failure")
        else:
            return jsonify({"message": f"{os.getenv('SERVICE_ADDRESS')} managed not to fail"}), 200
    except Exception as e:
        logMsg(f"Simulate failure error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/users/status', methods=['GET'])
@timeout_decorator(3)
def status():
    logMsg("Status endpoint called")
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
    logMsg(f"User registered: {user_data}")
    return jsonify({"message": "User registered successfully", "user": user_data}), 201

@app.route('/users/<user_id>', methods=['GET'])
@timeout_decorator(3)
def get_user(user_id):
    user = users_collection.find_one({"_id": user_id})
    if not user:
        logMsg(f"User not found: {user_id}")
        return jsonify({"error": "User not found"}), 404
    logMsg(f"User retrieved: {user}")
    return jsonify(user), 200

@app.route('/users/<user_id>', methods=['DELETE'])
@timeout_decorator(3)
def delete_user(user_id):
    result = users_collection.delete_one({"_id": user_id})
    if result.deleted_count == 0:
        logMsg(f"User not found for deletion: {user_id}")
        return jsonify({"error": "User not found"}), 404
    logMsg(f"User deleted: {user_id}")
    return jsonify({"message": "User deleted successfully"}), 200

@app.route('/users', methods=['GET'])
@timeout_decorator(3)
def get_all_users():
    users = list(users_collection.find())
    logMsg(f"All users retrieved: {users}")
    return jsonify(users), 200

@app.route('/health', methods=['GET'])
def health():
    logMsg("Health check endpoint called")
    return "OK", 200

if __name__ == '__main__':
    logMsg("User Management Service starting")
    app.run(host='0.0.0.0', port=5002)