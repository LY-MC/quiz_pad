from flask import Flask, jsonify, request
from pymongo import MongoClient
from functools import wraps
from collections import deque
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import uuid

app = Flask(__name__)
client = MongoClient('mongodb://mongodb:27017/')
db = client['users_game_db']
users_collection = db['users']

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

@app.route('/users/simulate-failure', methods=['GET'])
@circuit_breaker.call
def simulate_failure():
    raise Exception("Simulated failure")

@app.route('/users/status', methods=['GET'])
@circuit_breaker.call
def status():
    return jsonify({"status": "Service is running"}), 200

@app.route('/users/user/register', methods=['POST'])
@circuit_breaker.call
def register_user():
    user_data = request.get_json()
    for field in ['name', 'email', 'age']:
        if field not in user_data:
            return jsonify({"error": f"{field} is required."}), 400
    user_data['_id'] = str(uuid.uuid4())
    try:
        run_with_timeout(lambda: users_collection.insert_one(user_data), timeout=DEFAULT_TIMEOUT)
        return jsonify({"message": "User registered successfully!", "user": user_data}), 201
    except TimeoutException:
        return jsonify({"error": "Request timed out"}), 504

@app.route('/users/<user_id>', methods=['GET'])
@circuit_breaker.call
def get_user(user_id):
    try:
        user = run_with_timeout(lambda: users_collection.find_one({"_id": user_id}), timeout=DEFAULT_TIMEOUT)
        if user:
            return jsonify(user), 200
        return jsonify({"error": "User not found"}), 404
    except TimeoutException:
        return jsonify({"error": "Request timed out"}), 504

@app.route('/users', methods=['GET'])
@circuit_breaker.call
def get_all_users():
    try:
        users = run_with_timeout(lambda: list(users_collection.find()), timeout=DEFAULT_TIMEOUT)
        for user in users:
            user['_id'] = str(user['_id'])
        return jsonify(users), 200
    except TimeoutException:
        return jsonify({"error": "Request timed out"}), 504

@app.route('/health', methods=['GET'])
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)