package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"time"
)

// ... (TelemetryData struct and consts remain the same) ...
type TelemetryData struct {
	AgentID      string    `json:"agent_id"`
	Timestamp    time.Time `json:"timestamp"`
	Temperature  float64   `json:"temperature"`
	BatteryLevel int       `json:"battery_level"`
}

const (
	serverURL      = "http://localhost:8000/telemetry"
	bufferFile     = "buffer.jsonl"
	processingFile = "buffer_processing.jsonl"
)

var fileMutex sync.Mutex

func main() {
	agentID := "agent-001"
	fmt.Printf("🚀 Agent %s starting up (Linear Logic Mode)...\n", agentID)

	go flushBufferBackground()

	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		data := TelemetryData{
			AgentID:      agentID,
			Timestamp:    time.Now(),
			Temperature:  23.5,
			BatteryLevel: 85,
		}

		if !sendTelemetry(data) {
			saveToBuffer(data)
		}
	}
}

// ---------------- NETWORK HELPERS ----------------

func sendTelemetry(data TelemetryData) bool {
	jsonData, _ := json.Marshal(data)
	client := http.Client{Timeout: 2 * time.Second}

	resp, err := client.Post(serverURL, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

// ---------------- FILE HELPERS ----------------

func saveToBuffer(data TelemetryData) {
	fileMutex.Lock()
	defer fileMutex.Unlock()

	f, err := os.OpenFile(bufferFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Printf("❌ Error opening buffer: %v", err)
		return
	}
	defer f.Close()

	jsonData, _ := json.Marshal(data)
	f.Write(append(jsonData, '\n'))
	fmt.Printf("💾 Buffered: %v\n", data.Timestamp.Format(time.TimeOnly))
}

// ---------------- BACKGROUND WORKER ----------------

func flushBufferBackground() {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		processBuffer()
	}
}

// The Simplified Logic
func processBuffer() {
	// STEP 1: Handle existing processing file (Finish what we started)
	// We do NOT need the lock here because Main Loop only touches bufferFile.
	if _, err := os.Stat(processingFile); err == nil {
		// File exists, try to upload content
		if uploadBacklogFile(processingFile) {
			// Success! Remove the file.
			os.Remove(processingFile)
			fmt.Println("✅ Backlog batch cleared.")
		} else {
			// Failed. Return and try again next tick.
			fmt.Println("⚠️ Connection unstable. Retrying batch later.")
			return
		}
	}

	// STEP 2: Rotate new data (Grab new work)
	// We need the lock here because we are moving bufferFile.
	fileMutex.Lock()
	defer fileMutex.Unlock()

	// Check if main buffer exists and has data
	if info, err := os.Stat(bufferFile); err == nil && info.Size() > 0 {
		// Atomic Rename: buffer.jsonl -> buffer_processing.jsonl
		os.Rename(bufferFile, processingFile)
		fmt.Println("🔄 Rotating log file for processing...")
	}
}

// Helper to read a file and upload line-by-line
func uploadBacklogFile(filepath string) bool {
	content, err := os.ReadFile(filepath)
	if err != nil {
		return false // Can't read file? Treat as failure.
	}

	lines := bytes.Split(content, []byte("\n"))

	for _, line := range lines {
		if len(line) == 0 {
			continue
		}

		var data TelemetryData
		if err := json.Unmarshal(line, &data); err == nil {
			// If we fail to send even ONE line, we abort the whole batch.
			// This ensures strict ordering and no data gaps.
			if !sendTelemetry(data) {
				return false
			}
			fmt.Printf("   ⬆️ Restored upload: %v\n", data.Timestamp.Format(time.TimeOnly))
		}
	}
	return true
}
