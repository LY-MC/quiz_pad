# Multiplayer quiz game
## Application Suitability
In the multiplayer quiz game many users can join simultaneously and if we are talking about the scalability as more users join the quiz game, the system must handle an increasing number of game sessions, real-time updates, and user interactions without compromising performance. For example, Kahoot uses microservices to handle its quizzes, allowing millions of players to participate simultaneously by independently scaling each component (real-time game sessions, question fetching, etc.). Also, Kahoot’s real-time quiz functionality relies on WebSocket communication to broadcast questions and answers, track scores, and update leaderboards instantly, so I can use this as well in my project (not all of course). The game requires real-time updates and communication between players, which can be efficiently handled using WebSockets in a dedicated service (Game Engine). The API Gateway allows smooth client-server communication. Separation of components leads to fault isolation so even failing of one component doesn't lead to the entire app's failing like if on Netflix (that uses microservices to isolate components) one service (like recommendations) fails, it won’t affect video streaming.
## Service Boundaries
1. API Gateway - acts as the single point of entry for client requests, routing the system to User Management Service or Game Engine Service and also handling WebSocket connections
2. User Management Service - manages user authentication, profiles and leaderboards
3. Game Engine Service - handles the quiz game logic, scoring and gameplay sessions

![image](https://github.com/user-attachments/assets/a8eb279b-eff9-4b45-a251-8c4455ea5692)

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

### Running the Project
1. Clone the repository:
    ```sh
    git clone https://github.com/LY-MC/quiz_pad.git
    cd your-repo
    ```
2. Build and run Docker containers:
    ```sh
    docker-compose up --build
    ```
3. Access the services:
    - Gateway: `http://localhost:5000`
    - User Management Service: `http://localhost:5000/users`
    - Game Engine Service: `http://localhost:5000/game`
    - Service Discovery: `http://localhost:3000`

### Testing Docker Images
1. Run tests for User Management Service:
    ```sh
    docker-compose run user_management_service pytest
    ```
2. Run tests for Game Engine Service:
    ```sh
    docker-compose run game_engine_service pytest
    ```

## Data Management
1. User Management Service:
* GET /users/status    
Description: Check the status of the User Management Service.
  * Response
    * 200 OK: Returns service status and version. 
     ```
     {
       "status": "Service is running",
       "service": "User Management Service",
       "version": "1.0.0"
     }
     ```
     
* POST /users/user/register    
Description: Register a new user.     
  * Request Body (JSON object containing user information (e.g., name, email, etc.).)
  ```
  {
    "name": "John Doe",
    "email": "john@example.com"
  }
  ```
  * Response
    * 201 Created: Returns a success message and the registered user data.
     ```
     {
       "message": "User registered successfully",
       "user": {
         "_id": "unique-uuid",
         "name": "John Doe",
         "email": "john@example.com"
       }
     }
     ```
    * 503 Service Unavailable: When the service is temporarily unavailable.
      
* GET /users/<user_id>    
Description: Retrieve a specific user's details        
user_id: The unique identifier of the user.
  * Response
    *  200 OK: Returns the user data.
     ```
     {
       "_id": "unique-uuid",
       "name": "John Doe",
       "email": "john@example.com"
     }
     ```
     *  404 Not Found: If the user does not exist.
     *  503 Service Unavailable: When the service is temporarily unavailable.
      
* GET /users     
Description: Retrieve a list of all registered users.     
  * Response
    *  200 OK: Returns a list of all users.
     ```
    [
      {
        "_id": "unique-uuid-1",
        "name": "John Doe",
        "email": "john@example.com"
      },
      {
        "_id": "unique-uuid-2",
        "name": "Jane Smith",
        "email": "jane@example.com"
      }
    ]
     ```
     *  503 Service Unavailable: When the service is temporarily unavailable.
   
* GET /users/simulate-failure   
Description: Simulate a service failure to test the Circuit Breaker.    
  * Response
    *  503 Service Unavailable: Always returns a simulated error message.
     ```
    {
      "error": "Service unavailable"
    }
     ```
     
2. Game Engine Service:
* GET /game/status    
Description: Get the status of the Game Engine Service.    
  * Response
    * 200 OK: Returns service status and version. 
     ```
     {
       "status": "Service is running",
       "service": "Game Engine Service",
       "version": "1.0.0"
     }
     ```
     
* POST /game/submit-answer/<game_id>/<user_id>/<question_id>    
Description: Submits an answer to a question in the specified game.
  * Request Body
  ```
  {
    "answer": "user's answer"
  }
  ```
  * Response
    * 200 OK: Correct Answer:
     ```
    {
      "message": "Correct answer!",
      "new_score": 1
    }
     ```
    * 200 OK: Correct Answer:
     ```
     {
       "message": "Incorrect answer."
     }
     ```
    * 404 Not Found: If game or question not found.
    * 503 Service Unavailable: When the service is temporarily unavailable.
      
* GET /game/game-status/<game_id>    
Description: Retrieves the status of a specific game.    
game_id: The unique identifier of the game.
  * Response
    *  200 OK: Returns the game data.
     ```
     {
       "game_id": "game-id",
       "status": "in_progress",
       "players_scores": {}
     }
     ```
     *  404 Not Found: If the game does not exist.
     *  503 Service Unavailable: When the service is temporarily unavailable.
      
* GET /game/game-status/<game_id>    
Description: Retrieves the status of a specific game.
  * Response
    *  200 OK: Returns a list of all users.
     ```
    {
      "game_id": "game-id",
      "status": "in_progress",
      "players_scores": {}
    }
     ```
    *  404 Not Found: If the game does not exist.
    *  503 Service Unavailable: When the service is temporarily unavailable.

* GET /game/questions    
Description: Simulates a failure to demonstrate the Circuit Breaker functionality.
  * Response
    *  200 OK: Returns a list of all questions.
    *  404 Not Found: If the game does not exist.
    *  503 Service Unavailable: When the service is temporarily unavailable.
   
* GET /game/questions/<question_id>    
Description: Retrieves a specific question by its ID.
  * Response
    *  200 OK: Returns a list of all questions.
    *  404 Not Found: If the game does not exist.
    *  503 Service Unavailable: When the service is temporarily unavailable.
   
* GET /game/simulate-failure    
Description: Simulates a failure to demonstrate the Circuit Breaker functionality.
  * Response
    *  503 Service Unavailable: Always returns a simulated error message.
     ```
    {
      "error": "Service unavailable"
    }
     ```
     
* WebSocket Events
  * Connect    
    Event: connect    
    Description: Triggered when a client connects to the WebSocket server.    
    Response: Confirmation message.    
    
  * Disconnect    
    Event: disconnect    
    Description: Triggered when a client disconnects from the WebSocket server.    
    
  * Join Game    
    Event: join_game     
    Description: Allows a user to join a game. Adds the user to the game and sends a confirmation message.     
    Request Data:   
    ```
    {
      "game_id": "game-id",
      "user_id": "user-id"
    }
    ```
    
    Response: Confirmation or error message.
    
  * Leave Game    
    Event: leave_game    
    Description: Allows a user to leave a game and sends a notification to the room.    
    Request Data:   
    ```
    {
      "game_id": "game-id",
      "user_id": "user-id"
    }
    ```
    
  * Post Question    
    Event: post_question    
    Description: Posts a new question to a specific game.     
    Request Data:    
    ```
    {
      "game_id": "game-id",
      "question_data": {
        "question": "Sample question?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_answer": "Option A"
      }
    }
    ```
    Response: Success or error message.    
    

## Deployment and Scaling
1. **Docker Compose**: Use [docker-compose.yml](https://github.com/LY-MC/quiz_pad/blob/main/docker-compose.yml) to run multi-container applications.
2. **High Availability**: Implement service high availability and consistent hashing for cache.
3. **Monitoring and Logging**: Implement ELK stack, Prometheus, and Grafana for logging and monitoring.
4. **Data Management**: Implement database redundancy/replication and create a data warehouse with periodic updates.
