package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"
)

// Configuration with defaults
type Config struct {
	SocketPath     string
	BackendURL     string
	APIKey         string
	FlushInterval  time.Duration
	FlushMaxCount  int
	FlushMaxBytes  int
	RequestTimeout time.Duration
}

// BatchItem represents a single call start or end request
type BatchItem struct {
	Mode string          `json:"mode"` // "start" or "end"
	Req  json.RawMessage `json:"req"`
}

// Batch is what we send to the server
type Batch struct {
	Batch []BatchItem `json:"batch"`
}

// Request from Python client
type Request struct {
	Method  string          `json:"method"` // "call_start" or "call_end"
	Payload json.RawMessage `json:"payload"`
}

// Response to Python client
type Response struct {
	Success bool   `json:"success"`
	Error   string `json:"error,omitempty"`
}

// Sidecar is the main server
type Sidecar struct {
	config     Config
	httpClient *http.Client
	listener   net.Listener

	mu        sync.Mutex
	batch     []BatchItem
	batchSize int // current size in bytes

	flushChan chan struct{}
	stopChan  chan struct{}
	wg        sync.WaitGroup
}

func NewSidecar(config Config) *Sidecar {
	return &Sidecar{
		config: config,
		httpClient: &http.Client{
			Timeout: config.RequestTimeout,
			Transport: &http.Transport{
				MaxIdleConns:        10,
				MaxIdleConnsPerHost: 10,
				IdleConnTimeout:     90 * time.Second,
			},
		},
		batch:     make([]BatchItem, 0, config.FlushMaxCount),
		flushChan: make(chan struct{}, 1),
		stopChan:  make(chan struct{}),
	}
}

func (s *Sidecar) Start() error {
	// Remove existing socket file if it exists
	if err := os.RemoveAll(s.config.SocketPath); err != nil {
		return fmt.Errorf("failed to remove existing socket: %w", err)
	}

	// Create Unix domain socket listener
	listener, err := net.Listen("unix", s.config.SocketPath)
	if err != nil {
		return fmt.Errorf("failed to listen on socket: %w", err)
	}
	s.listener = listener

	// Make socket accessible
	if err := os.Chmod(s.config.SocketPath, 0666); err != nil {
		return fmt.Errorf("failed to chmod socket: %w", err)
	}

	log.Printf("Sidecar listening on %s", s.config.SocketPath)
	log.Printf("Backend URL: %s", s.config.BackendURL)
	log.Printf("Flush config: interval=%v, maxCount=%d, maxBytes=%d",
		s.config.FlushInterval, s.config.FlushMaxCount, s.config.FlushMaxBytes)

	// Start background flush goroutine
	s.wg.Add(1)
	go s.flushLoop()

	// Accept connections
	s.wg.Add(1)
	go s.acceptLoop()

	return nil
}

func (s *Sidecar) acceptLoop() {
	defer s.wg.Done()

	for {
		conn, err := s.listener.Accept()
		if err != nil {
			select {
			case <-s.stopChan:
				return
			default:
				log.Printf("Accept error: %v", err)
				continue
			}
		}

		go s.handleConnection(conn)
	}
}

func (s *Sidecar) handleConnection(conn net.Conn) {
	defer conn.Close()

	decoder := json.NewDecoder(conn)
	encoder := json.NewEncoder(conn)

	for {
		var req Request
		if err := decoder.Decode(&req); err != nil {
			if err != io.EOF {
				log.Printf("Decode error: %v", err)
			}
			return
		}

		resp := s.handleRequest(&req)
		if err := encoder.Encode(resp); err != nil {
			log.Printf("Encode error: %v", err)
			return
		}
	}
}

func (s *Sidecar) handleRequest(req *Request) Response {
	var mode string
	switch req.Method {
	case "call_start":
		mode = "start"
	case "call_end":
		mode = "end"
	default:
		return Response{Success: false, Error: fmt.Sprintf("unknown method: %s", req.Method)}
	}

	item := BatchItem{
		Mode: mode,
		Req:  req.Payload,
	}

	s.enqueue(item)

	return Response{Success: true}
}

func (s *Sidecar) enqueue(item BatchItem) {
	s.mu.Lock()
	defer s.mu.Unlock()

	itemSize := len(item.Req) + 50 // rough estimate for JSON overhead
	s.batch = append(s.batch, item)
	s.batchSize += itemSize

	// Check if we should trigger a flush
	if len(s.batch) >= s.config.FlushMaxCount || s.batchSize >= s.config.FlushMaxBytes {
		select {
		case s.flushChan <- struct{}{}:
		default:
			// Flush already pending
		}
	}
}

func (s *Sidecar) flushLoop() {
	defer s.wg.Done()

	ticker := time.NewTicker(s.config.FlushInterval)
	defer ticker.Stop()

	for {
		select {
		case <-s.stopChan:
			// Final flush on shutdown
			s.flush()
			return
		case <-ticker.C:
			s.flush()
		case <-s.flushChan:
			s.flush()
		}
	}
}

func (s *Sidecar) flush() {
	s.mu.Lock()
	if len(s.batch) == 0 {
		s.mu.Unlock()
		return
	}

	// Take the current batch and reset
	batch := s.batch
	s.batch = make([]BatchItem, 0, s.config.FlushMaxCount)
	s.batchSize = 0
	s.mu.Unlock()

	log.Printf("Flushing %d items to backend", len(batch))

	// Send to backend
	if err := s.sendBatch(batch); err != nil {
		log.Printf("Failed to send batch: %v", err)
		// TODO: Could implement retry logic or disk fallback here
	}
}

func (s *Sidecar) sendBatch(batch []BatchItem) error {
	payload := Batch{Batch: batch}

	data, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal batch: %w", err)
	}

	url := s.config.BackendURL + "/call/upsert_batch"

	ctx, cancel := context.WithTimeout(context.Background(), s.config.RequestTimeout)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(data))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	// Add authentication if API key is configured
	if s.config.APIKey != "" {
		req.SetBasicAuth("api", s.config.APIKey)
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("backend returned status %d: %s", resp.StatusCode, string(body))
	}

	return nil
}

func (s *Sidecar) Stop() {
	log.Println("Shutting down sidecar...")

	// Signal stop
	close(s.stopChan)

	// Close listener to stop accepting new connections
	if s.listener != nil {
		s.listener.Close()
	}

	// Wait for goroutines to finish (includes final flush)
	s.wg.Wait()

	// Cleanup socket file
	os.RemoveAll(s.config.SocketPath)

	log.Println("Sidecar shutdown complete")
}

func main() {
	// Command line flags
	socketPath := flag.String("socket", "/tmp/weave_sidecar.sock", "Unix socket path")
	backendURL := flag.String("backend", "", "Backend trace server URL (required)")
	apiKey := flag.String("api-key", "", "API key for authentication (or set WANDB_API_KEY env var)")
	flushInterval := flag.Duration("flush-interval", 1*time.Second, "Flush interval")
	flushMaxCount := flag.Int("flush-max-count", 2000, "Max items before flush")
	flushMaxBytes := flag.Int("flush-max-bytes", 10*1024*1024, "Max bytes before flush (10MB default)")
	requestTimeout := flag.Duration("request-timeout", 30*time.Second, "HTTP request timeout")

	flag.Parse()

	if *backendURL == "" {
		log.Fatal("--backend flag is required")
	}

	// Use API key from flag or environment variable
	authKey := *apiKey
	if authKey == "" {
		authKey = os.Getenv("WANDB_API_KEY")
	}
	if authKey == "" {
		log.Println("Warning: No API key provided. Set --api-key or WANDB_API_KEY environment variable.")
	}

	config := Config{
		SocketPath:     *socketPath,
		BackendURL:     *backendURL,
		APIKey:         authKey,
		FlushInterval:  *flushInterval,
		FlushMaxCount:  *flushMaxCount,
		FlushMaxBytes:  *flushMaxBytes,
		RequestTimeout: *requestTimeout,
	}

	sidecar := NewSidecar(config)

	if err := sidecar.Start(); err != nil {
		log.Fatalf("Failed to start sidecar: %v", err)
	}

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	sidecar.Stop()
}
