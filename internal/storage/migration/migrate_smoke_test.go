// SPDX-FileCopyrightText: 2026 Jonas Kaninda
// SPDX-License-Identifier: AGPL-3.0-or-later

package migration

import (
	"os"
	"testing"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	gl "gorm.io/gorm/logger"
)

// TestMigrateSmoke runs the full schema migration against a scratch database.
// It is skipped unless MIGRATION_SMOKE_DSN is set.
func TestMigrateSmoke(t *testing.T) {
	dsn := os.Getenv("MIGRATION_SMOKE_DSN")
	if dsn == "" {
		t.Skip("set MIGRATION_SMOKE_DSN to run")
	}
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{Logger: gl.Default.LogMode(gl.Silent)})
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	if err := Run(db); err != nil {
		t.Fatalf("migrate: %v", err)
	}

	var idx string
	if err := db.Raw(`SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_notification_open'`).
		Scan(&idx).Error; err != nil || idx == "" {
		t.Fatalf("partial unique index missing: %v (%q)", err, idx)
	}
	t.Logf("index: %s", idx)
}
