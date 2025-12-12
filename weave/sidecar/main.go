package main

import (
	"bufio"
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
	"path/filepath"
	"strings"
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
	Method  string          `json:"method"` // "call_start", "call_end", or "flush"
	Payload json.RawMessage `json:"payload"`
}

// Response to Python client
type Response struct {
	Success bool   `json:"success"`
	Error   string `json:"error,omitempty"`
	Pending int    `json:"pending,omitempty"` // Number of items still pending
}

// Number of parallel flush workers
const numFlushWorkers = 4

// Sidecar is the main server
type Sidecar struct {
	config     Config
	httpClient *http.Client
	listener   net.Listener

	mu        sync.Mutex
	batch     []BatchItem
	batchSize int // current size in bytes

	// batchChan receives batches ready to be sent to backend
	batchChan chan []BatchItem
	stopChan  chan struct{}
	wg        sync.WaitGroup
	sendWg    sync.WaitGroup // tracks in-flight batch sends for flushSync
}

func NewSidecar(config Config) *Sidecar {
	return &Sidecar{
		config: config,
		httpClient: &http.Client{
			Timeout: config.RequestTimeout,
			Transport: &http.Transport{
				MaxIdleConns:        100,
				MaxIdleConnsPerHost: 100,
				IdleConnTimeout:     90 * time.Second,
			},
		},
		batch:     make([]BatchItem, 0, config.FlushMaxCount),
		batchChan: make(chan []BatchItem, numFlushWorkers*2), // buffered to allow some queuing
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
	log.Printf("Flush config: interval=%v, maxCount=%d, maxBytes=%d, workers=%d",
		s.config.FlushInterval, s.config.FlushMaxCount, s.config.FlushMaxBytes, numFlushWorkers)

	// Start flush workers (parallel HTTP senders)
	for i := 0; i < numFlushWorkers; i++ {
		s.wg.Add(1)
		go s.flushWorker(i)
	}

	// Start batch collector (collects items and dispatches batches to workers)
	s.wg.Add(1)
	go s.batchCollector()

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
	switch req.Method {
	case "call_start":
		s.enqueue(BatchItem{Mode: "start", Req: req.Payload})
		return Response{Success: true, Pending: s.getPendingCount()}

	case "call_end":
		s.enqueue(BatchItem{Mode: "end", Req: req.Payload})
		return Response{Success: true, Pending: s.getPendingCount()}

	case "flush":
		// Synchronously flush all pending items and wait for completion
		s.flushSync()
		return Response{Success: true, Pending: 0}

	default:
		return Response{Success: false, Error: fmt.Sprintf("unknown method: %s", req.Method)}
	}
}

func (s *Sidecar) getPendingCount() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.batch)
}

func (s *Sidecar) enqueue(item BatchItem) {
	itemSize := len(item.Req) + 50 // rough estimate for JSON overhead

	s.mu.Lock()
	s.batch = append(s.batch, item)
	s.batchSize += itemSize

	// Check if we should dispatch this batch to workers
	if len(s.batch) >= s.config.FlushMaxCount || s.batchSize >= s.config.FlushMaxBytes {
		batch := s.batch
		s.batch = make([]BatchItem, 0, s.config.FlushMaxCount)
		s.batchSize = 0
		s.sendWg.Add(1) // Track this batch
		s.mu.Unlock()

		// Send batch to workers (may block if workers are busy - this is back-pressure)
		s.batchChan <- batch
		return
	}
	s.mu.Unlock()
}

// batchCollector periodically flushes partial batches that haven't reached the size threshold
func (s *Sidecar) batchCollector() {
	defer s.wg.Done()

	ticker := time.NewTicker(s.config.FlushInterval)
	defer ticker.Stop()

	for {
		select {
		case <-s.stopChan:
			// Final flush on shutdown - dispatch any remaining items
			s.dispatchCurrentBatch()
			return
		case <-ticker.C:
			s.dispatchCurrentBatch()
		}
	}
}

// dispatchCurrentBatch sends the current batch to workers if non-empty
func (s *Sidecar) dispatchCurrentBatch() {
	s.mu.Lock()
	if len(s.batch) == 0 {
		s.mu.Unlock()
		return
	}

	batch := s.batch
	s.batch = make([]BatchItem, 0, s.config.FlushMaxCount)
	s.batchSize = 0
	s.sendWg.Add(1)
	s.mu.Unlock()

	// Send to workers
	s.batchChan <- batch
}

// flushWorker processes batches from batchChan and sends them to the backend
func (s *Sidecar) flushWorker(id int) {
	defer s.wg.Done()

	for batch := range s.batchChan {
		log.Printf("[worker %d] Sending %d items to backend...", id, len(batch))

		if err := s.sendBatch(batch); err != nil {
			log.Printf("[worker %d] Failed to send %d items: %v", id, len(batch), err)
		} else {
			log.Printf("[worker %d] Successfully sent %d items", id, len(batch))
		}

		s.sendWg.Done() // Mark this batch complete
	}
}

// flushSync flushes all pending items synchronously and waits for completion.
// It dispatches remaining items to workers and waits for all in-flight batches to complete.
func (s *Sidecar) flushSync() {
	// Dispatch any remaining items in current batch
	s.dispatchCurrentBatch()

	// Wait for all in-flight batches to complete
	s.sendWg.Wait()
	log.Printf("Sync flush: complete, all sends finished")
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

	// Signal stop to batchCollector
	close(s.stopChan)

	// Close listener to stop accepting new connections
	if s.listener != nil {
		s.listener.Close()
	}

	// Wait briefly for batchCollector to dispatch final batch
	time.Sleep(100 * time.Millisecond)

	// Close batchChan to signal workers to exit after processing remaining batches
	close(s.batchChan)

	// Wait for all goroutines to finish
	s.wg.Wait()

	// Cleanup socket file
	os.RemoveAll(s.config.SocketPath)

	log.Println("Sidecar shutdown complete")
}

// getAPIKeyFromNetrc reads the API key from ~/.netrc for api.wandb.ai
func getAPIKeyFromNetrc() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}

	netrcPath := filepath.Join(home, ".netrc")
	file, err := os.Open(netrcPath)
	if err != nil {
		return ""
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	var inWandbMachine bool
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		fields := strings.Fields(line)

		for i := 0; i < len(fields); i++ {
			if fields[i] == "machine" && i+1 < len(fields) {
				inWandbMachine = fields[i+1] == "api.wandb.ai"
				i++
			} else if inWandbMachine && fields[i] == "password" && i+1 < len(fields) {
				return fields[i+1]
			}
		}
	}

	return ""
}

func main() {
	// Command line flags
	socketPath := flag.String("socket", "/tmp/weave_sidecar.sock", "Unix socket path")
	backendURL := flag.String("backend", "", "Backend trace server URL (required)")
	apiKey := flag.String("api-key", "", "API key for authentication (or set WANDB_API_KEY env var)")
	flushInterval := flag.Duration("flush-interval", 1*time.Second, "Flush interval")
	flushMaxCount := flag.Int("flush-max-count", 500, "Max items before flush")
	flushMaxBytes := flag.Int("flush-max-bytes", 5*1024*1024, "Max bytes before flush (5MB default)")
	requestTimeout := flag.Duration("request-timeout", 30*time.Second, "HTTP request timeout")

	flag.Parse()

	if *backendURL == "" {
		log.Fatal("--backend flag is required")
	}

	// Use API key from flag, environment variable, or netrc file
	authKey := *apiKey
	if authKey == "" {
		authKey = os.Getenv("WANDB_API_KEY")
	}
	if authKey == "" {
		authKey = getAPIKeyFromNetrc()
		if authKey != "" {
			log.Println("Using API key from ~/.netrc")
		}
	}
	if authKey == "" {
		log.Println("Warning: No API key provided. Set --api-key, WANDB_API_KEY, or run 'wandb login'.")
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
