from flask import Flask, jsonify, request
from pymongo import MongoClient
from functools import wraps
from collections import deque
from datetime import datetime, timedelta
import uuid
import time
import signal

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
                    return jsonify({"error": "Service unavailable"}), 503
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
                    return jsonify({"error": "Service unavailable"}), 503
                return jsonify({"error": "Temporary unavailable"}), 503

        return wrapper

circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=500)

@app.route('/users/simulate-failure', methods=['GET'])
@circuit_breaker.call
# @timeout_decorator(3)
def simulate_failure():
    raise Exception("Simulated failure")

@app.route('/users/status', methods=['GET'])
@circuit_breaker.call
# @timeout_decorator(3)
def status():
    return jsonify({
        "status": "Service is running",
        "service": "User Management Service",
        "version": "1.0.0"
    }), 200

@app.route('/users/user/register', methods=['POST'])
@circuit_breaker.call
# @timeout_decorator(3)
def register_user():
    user_data = request.json
    user_data['_id'] = str(uuid.uuid4())
    users_collection.insert_one(user_data)
    return jsonify({"message": "User registered successfully", "user": user_data}), 201

@app.route('/users/<user_id>', methods=['GET'])
@circuit_breaker.call
# @timeout_decorator(3)
def get_user(user_id):
    user = users_collection.find_one({"_id": user_id})
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user), 200

@app.route('/users', methods=['GET'])
@circuit_breaker.call
# @timeout_decorator(3)
def get_all_users():
    # time.sleep(500)
    users = list(users_collection.find())
    return jsonify(users), 200

@app.route('/health', methods=['GET'])
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)