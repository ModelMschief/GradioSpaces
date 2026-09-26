package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"runtime"
	"time"
)

type StatusResponse struct {
	Status     string    `json:"status"`
	Message    string    `json:"message"`
	GoVersion  string    `json:"go_version"`
	OS         string    `json:"os"`
	Arch       string    `json:"arch"`
	NumCPU     int       `json:"num_cpu"`
	Goroutines int       `json:"goroutines"`
	Timestamp  time.Time `json:"timestamp"`
}

type PingResponse struct {
	Message string `json:"message"`
	Success bool   `json:"success"`
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		resp := StatusResponse{
			Status:     "success",
			Message:    "Hello from Golang Docker Container running on Hugging Face!",
			GoVersion:  runtime.Version(),
			OS:         runtime.GOOS,
			Arch:       runtime.GOARCH,
			NumCPU:     runtime.NumCPU(),
			Goroutines: runtime.NumGoroutine(),
			Timestamp:  time.Now().UTC(),
		}
		json.NewEncoder(w).Encode(resp)
	})

	http.HandleFunc("/ping", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(PingResponse{
			Message: "pong from Go service",
			Success: true,
		})
	})

	http.HandleFunc("/api/info", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		var m runtime.MemStats
		runtime.ReadMemStats(&m)
		data := map[string]interface{}{
			"alloc_mb":       float64(m.Alloc) / 1024 / 1024,
			"total_alloc_mb": float64(m.TotalAlloc) / 1024 / 1024,
			"sys_mb":         float64(m.Sys) / 1024 / 1024,
			"num_gc":         m.NumGC,
		}
		json.NewEncoder(w).Encode(data)
	})

	addr := ":" + port
	fmt.Printf("Golang server starting on http://0.0.0.0:%s\n", port)
	if err := http.ListenAndServe(addr, nil); err != nil {
		log.Fatalf("Server failed to start: %v\n", err)
	}
}
