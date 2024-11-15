import requests
import logging

logger = logging.getLogger('saga_coordinator')

class SagaCoordinator:
    def __init__(self):
        self.steps = []
        self.compensation_steps = []

    def add_step(self, step, compensation_step):
        self.steps.append(step)
        self.compensation_steps.insert(0, compensation_step)

    def execute(self):
        for step in self.steps:
            try:
                step()
            except Exception as e:
                logger.error(f"Step failed: {e}")
                self.rollback()
                raise e

    def rollback(self):
        for compensation_step in self.compensation_steps:
            try:
                compensation_step()
            except Exception as e:
                logger.error(f"Compensation step failed: {e}")

def create_user_step(user_data):
    def step():
        response = requests.post('http://gateway:5000/users/user/register', json=user_data)
        response.raise_for_status()
        user_data['_id'] = response.json()['user']['_id']
    return step

def create_game_session_step(game_data):
    def step():
        response = requests.post('http://gateway:5000/game/start-game', json=game_data)
        response.raise_for_status()
        game_data['_id'] = response.json()['game']['_id']
    return step

def delete_user_step(user_data):
    def step():
        response = requests.delete(f'http://gateway:5000/users/{user_data["_id"]}')
        response.raise_for_status()
    return step

def delete_game_session_step(game_data):
    def step():
        response = requests.delete(f'http://gateway:5000/game/{game_data["_id"]}')
        response.raise_for_status()
    return step