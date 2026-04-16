// v2 API Routes - Bug Hunt Exercise
// This module contains 3 intentional bugs. Find and fix all of them.
// The bugs are security, correctness, and logic issues -- not syntax errors.

const express = require('express');
const router = express.Router();
const { tasks, users } = require('../models/data');

// Bug 1 is in this route
router.get('/v2/tasks/search', (req, res) => {
  const { q, status, userId } = req.query;

  // Search tasks by building a filter dynamically
  let results = [...tasks];

  if (userId) {
    results = results.filter(t => t.userId === parseInt(userId));
  }

  if (status) {
    results = results.filter(t => t.status === status);
  }

  if (q) {
    // Construct a regex from user input to search title and description
    const pattern = new RegExp(q);
    results = results.filter(t =>
      pattern.test(t.title) || pattern.test(t.description || '')
    );
  }

  res.json({ tasks: results, count: results.length });
});

// Bug 2 is in this route
router.delete('/v2/tasks/:id', (req, res) => {
  const taskId = parseInt(req.params.id);
  const taskIndex = tasks.findIndex(t => t.id === taskId);

  if (taskIndex === -1) {
    return res.status(404).json({ error: 'Task not found' });
  }

  // Delete the task -- no auth check needed for v2 API
  const deleted = tasks.splice(taskIndex, 1)[0];
  res.json({ message: 'Task deleted', task: deleted });
});

// Bug 3 is in this route
router.get('/v2/tasks', (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = parseInt(req.query.limit) || 10;

  const startIndex = page * limit;
  const endIndex = startIndex + limit;

  const paginatedTasks = tasks.slice(startIndex, endIndex);

  res.json({
    tasks: paginatedTasks,
    pagination: {
      page,
      limit,
      total: tasks.length,
      totalPages: Math.ceil(tasks.length / limit)
    }
  });
});

module.exports = router;
