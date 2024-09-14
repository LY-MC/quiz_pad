# Multiplayer quiz game
## Application Suitability
In the multiplayer quiz game many users can join simultaneously and if we are talking about the scalability as more users join the quiz game, the system must handle an increasing number of game sessions, real-time updates, and user interactions without compromising performance. For example, Kahoot uses microservices to handle its quizzes, allowing millions of players to participate simultaneously by independently scaling each component (real-time game sessions, question fetching, etc.). Also, Kahoot’s real-time quiz functionality relies on WebSocket communication to broadcast questions and answers, track scores, and update leaderboards instantly, so I can use this as well in my project (not all of course). The game requires real-time updates and communication between players, which can be efficiently handled using WebSockets in a dedicated service (Game Engine). The API Gateway allows smooth client-server communication. Separation of components leads to fault isolation so even failing of one component doesn't lead to the entire app's failing like if on Netflix (that uses microservices to isolate components) one service (like recommendations) fails, it won’t affect video streaming.
## Service Boundaries
1. API Gateway - acts as the single point of entry for client requests, routing the system to User Management Service or Game Engine Service and also handling WebSocket connections
2. User Management Service - manages user authentication, profiles and leaderboards
3. Game Engine Service - handles the quiz game logic, scoring and gameplay sessions

![Screenshot 2024-09-14 002150](https://github.com/user-attachments/assets/cd7e1f5c-cdfe-49e3-9233-16cc1dcecae8)

Load Balancer is used to distribute incoming requests across multiple instances of services for better performance and reliability.
Service Discovery is used to allow microservices to find and communicate with each other dynamically.

## Technology stack
1. User Management and Game Engine Service:
Language - Python
Communication - gRPC, WebSockets
Database - MongoDB
2. API Gateway:
Language - JavaScript
Framework - Node.js with Express.js

## Data Management
1. User Management Service:
* POST /user/register
  * Request Body 
  ```
    {
    "username": "newuser",
    "password": "securepassword"
    } 
  ```
* POST /user/login
  * Request Body
  ```
    {
    "username": "username",
    "password": "securepassword"
    }
  ```
  * Response
  ```
    {
    "auth_token": "string"
    }
  ```
* GET /user/:id
  * Response
  ```
   {
    "user_id": "string",
    "username": "string",
    "score_history": [],
    "place": "integer",
    "score" : "integer",
  }
  ```
2. Game Engine Service:
* POST /start-game
  * Request Body 
  ```
  {
    "quiz_id": "string",
    "players": ["user_ids"]
  }
  ```
  * Response
  ```
  {
    "game_id": "string",
    "status": "string"
  }
  ```
* POST /submit-answer
  * Request Body
  ```
  {
    "game_id": "string",
    "user_id": "string",
    "answer": "string"
  }
  ```
  * Response
  ```
  {
    "correct": "boolean",
    "current_score": "integer"
  }
  ```
* GET /game-status/:id
  * Response
  ```
  {
    "game_id": "string",
    "status": "string",
    "current_question": "string",
    "players_scores": {}
  }
  ```
* GET /questions/
  * Response
  ```
  {
    "quiz_id": "string",
    "questions": [
      {
        "question_id": "string",
        "question_text": "string",
        "options": [
          "option1",
          "option2",
          "option3",
          "option4"
        ]
      }
    ]
  }
  ```

## Deployment and Scaling
Usage of Docker for containerization and Docker Compose for running multi-container applications
