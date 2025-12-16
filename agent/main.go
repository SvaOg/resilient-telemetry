package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

type TelemetryData struct {
	AgentID      string    `json:"agent_id"`
	Timestamp    time.Time `json:"timestamp"`
	Temperature  float64   `json:"temperature"`
	BatteryLevel int       `json:"battery_level"`
}

const (
	serverURL  = "http://localhost:8000/telemetry"
	bufferFile = "buffer.jsonl" // .jsonl denotes "JSON Lines"
)

func main() {
	agentID := "agent-001"

	fmt.Printf("🚀 Agent %s starting up...\n", agentID)

	// 2. The Loop: Send data every 1 second
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		// Create dummy data
		data := TelemetryData{
			AgentID:      agentID,
			Timestamp:    time.Now(),
			Temperature:  23.5, // Static for now
			BatteryLevel: 85,   // Static for now
		}

		// Try to send to network
		success := sendTelemetry(serverURL, data)
		if !success {
			saveToBuffer(data)
		}
	}
}

func sendTelemetry(url string, data TelemetryData) bool {
	// Marshal struct to JSON
	jsonData, err := json.Marshal(data)
	if err != nil {
		log.Printf("❌ Error marshalling JSON: %v", err)
		return false
	}

	// Create POST request
	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		log.Printf("❌ Connection failed: %v", err)
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		fmt.Printf("✅ Data sent successfully: %v\n", resp.Status)
	} else {
		log.Printf("⚠️ Server returned status: %s", resp.Status)
		return false
	}

	return true
}

func saveToBuffer(data TelemetryData) {
	// Open file in Append mode, Create if not exists, Write Only
	f, err := os.OpenFile(bufferFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Printf("❌ CRITICAL: Cannot open buffer file: %v", err)
		return
	}
	defer f.Close()

	// Marshal to JSON
	jsonData, _ := json.Marshal(data)

	// Write the JSON + a newline character
	if _, err := f.Write(append(jsonData, '\n')); err != nil {
		log.Printf("❌ CRITICAL: Cannot write to buffer: %v", err)
		return
	}

	fmt.Printf("💾 Buffered to disk %v\n", data.Timestamp.Format(time.TimeOnly))
}
