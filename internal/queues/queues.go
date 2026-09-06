// SPDX-FileCopyrightText: 2026 Jonas Kaninda
// SPDX-License-Identifier: AGPL-3.0-or-later

// Package queues names the Asynq queues.
//
// It is a leaf with no imports of its own so that both the worker, which weights
// and consumes the queues, and the cron jobs, which enqueue onto them, can refer
// to the same names. Package worker imports cron/jobs, so the names cannot live
// in either without one side resorting to a string literal — and a literal that
// drifts sends work to a queue nothing consumes, with no error anywhere.
package queues

const (
	// Transactional carries work a person is waiting on: API and relayed sends,
	// inbound parsing and forwarding, web form messages.
	Transactional = "transactional"
	// Bulk carries campaign work, which is large and can afford to wait.
	Bulk = "bulk"
	// Low carries scheduled background work such as daily reports.
	Low = "low"
)
