const axios = require('axios');

class SagaCoordinator {
    constructor() {
        this.steps = [];
        this.compensation_steps = [];
    }

    addStep(step, compensationStep) {
        this.steps.push(step);
        this.compensation_steps.unshift(compensationStep);
    }

    async execute() {
        for (const step of this.steps) {
            try {
                await step();
            } catch (e) {
                console.error(`Step failed: ${e}`);
                await this.rollback();
                throw e;
            }
        }
    }

    async rollback() {
        for (const compensationStep of this.compensation_steps) {
            try {
                await compensationStep();
            } catch (e) {
                console.error(`Compensation step failed: ${e}`);
            }
        }
    }
}

const createUserStep = (userData) => async () => {
    const response = await axios.post('http://user_management_service_1:5002/users/user/register', userData);
    userData._id = response.data.user._id;
};

const deleteUserStep = (userData) => async () => {
    await axios.delete(`http://user_management_service_1:5002/users/${userData._id}`);
};

const createGameSessionStep = (gameData) => async () => {
    const response = await axios.post('http://game_engine_service_1:5003/game/start-game', gameData);
    gameData._id = response.data.game._id;
};

const deleteGameSessionStep = (gameData) => async () => {
    await axios.delete(`http://game_engine_service_1:5003/game/${gameData._id}`);
};

module.exports = {
    SagaCoordinator,
    createUserStep,
    deleteUserStep,
    createGameSessionStep,
    deleteGameSessionStep
};