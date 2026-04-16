// In-memory data store

let users = [];
let tasks = [];
let nextUserId = 1;
let nextTaskId = 1;

module.exports = {
  users,
  tasks,
  getNextUserId: () => nextUserId++,
  getNextTaskId: () => nextTaskId++
};
