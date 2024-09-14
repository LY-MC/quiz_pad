# Multiplayer quiz game
## Application Suitability
In the multiplayer quiz game many users can join simultaneously and if we are talking about the scalability as more users join the quiz game, the system must handle an increasing number of game sessions, real-time updates, and user interactions without compromising performance. For example, Kahoot uses microservices to handle its quizzes, allowing millions of players to participate simultaneously by independently scaling each component (real-time game sessions, question fetching, etc.). Also, Kahoot’s real-time quiz functionality relies on WebSocket communication to broadcast questions and answers, track scores, and update leaderboards instantly, so I can use this as well in my project (not all of course). The game requires real-time updates and communication between players, which can be efficiently handled using WebSockets in a dedicated service (Game Engine). The API Gateway allows smooth client-server communication. Separation of components leads to fault isolation so even failing of one component doesn't lead to the entire app's failing like if on Netflix (that uses microservices to isolate components) one service (like recommendations) fails, it won’t affect video streaming.
## Service Boundaries
1. API Gateway - acts as the single point of entry for client requests, routing the system to User Management Service or Game Engine Service and also handling WebSocket connections
2. User Management Service - manages user authentication, profiles and leaderboards
3. Game Engine Service - handles the quiz game logic, scoring and gameplay sessions

![image](https://github.com/user-attachments/assets/9056f079-357d-4184-96cc-7e20ea82c745)

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
* WebSocket /game/submit-answer (Opens a WebSocket connection for submitting answers in the Game Engine Service)
  The client opens a WebSocket connection to /game/submit-answer, passing the game_id and JWT token as query parameters (e.g., ws://gameengine.com/game/submit-answer?game_id=GAME_ID&token=JWT-TOKEN).
  ```
  {
    "answer": "string"
  }
  ```

## Deployment and Scaling
Usage of Docker for containerization and Docker Compose for running multi-container applications
