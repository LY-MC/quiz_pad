import unittest
from unittest.mock import patch, MagicMock
from app import app, users_collection, TimeoutException

class UserManagementServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('app.users_collection')
    def test_get_all_users(self, mock_users_collection):
        mock_users_collection.find.return_value = [
            {'_id': '1', 'name': 'John Doe', 'email': 'john@example.com', 'age': 30},
            {'_id': '2', 'name': 'Jane Doe', 'email': 'jane@example.com', 'age': 25}
        ]
        response = self.app.get('/users')
        self.assertEqual(response.status_code, 200)
        self.assertIn('John Doe', response.get_data(as_text=True))
        self.assertIn('Jane Doe', response.get_data(as_text=True))

    @patch('app.users_collection')
    def test_get_user(self, mock_users_collection):
        mock_users_collection.find_one.return_value = {'_id': '1', 'name': 'John Doe', 'email': 'john@example.com', 'age': 30}
        response = self.app.get('/users/1')
        self.assertEqual(response.status_code, 200)
        self.assertIn('John Doe', response.get_data(as_text=True))

    @patch('app.users_collection')
    def test_register_user(self, mock_users_collection):
        user_data = {'name': 'John Doe', 'email': 'john@example.com', 'age': 30}
        response = self.app.post('/users/user/register', json=user_data)
        self.assertEqual(response.status_code, 201)
        self.assertIn('User registered successfully!', response.get_data(as_text=True))

    def test_health(self):
        response = self.app.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), 'OK')

    @patch('app.users_collection')
    def test_status(self, mock_users_collection):
        response = self.app.get('/users/status')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Service is running', response.get_data(as_text=True))

    def test_simulate_failure(self):
        response = self.app.get('/users/simulate-failure')
        self.assertEqual(response.status_code, 500)
        self.assertIn('Simulated failure', response.get_data(as_text=True))

if __name__ == '__main__':
    unittest.main()