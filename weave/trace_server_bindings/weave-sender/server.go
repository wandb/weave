package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"
)

// Server handles JSON-RPC style communication over Unix Domain Socket
type Server struct {
	socketPath string
	listener   net.Listener

	queue   *Queue
	batcher *Batcher
	sender  *HTTPSender

	mu       sync.Mutex
	running  bool
	shutdown chan struct{}

	// Track connected clients
	clients   map[net.Conn]struct{}
	clientsMu sync.Mutex
}

// Request represents an incoming request from a client
type Request struct {
	ID     int             `json:"id"`
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
}

// Response represents an outgoing response to a client
type Response struct {
	ID     int             `json:"id"`
	Result json.RawMessage `json:"result,omitempty"`
	Error  *ErrorResponse  `json:"error,omitempty"`
}

// ErrorResponse represents an error in the response
type ErrorResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// InitParams contains initialization parameters
type InitParams struct {
	ServerURL string            `json:"server_url"`
	Auth      *AuthParams       `json:"auth,omitempty"`
	Headers   map[string]string `json:"headers,omitempty"`
	Config    *ConfigParams     `json:"config,omitempty"`
}

// AuthParams contains authentication parameters
type AuthParams struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

// ConfigParams contains optional configuration
type ConfigParams struct {
	MaxBatchSize    int `json:"max_batch_size,omitempty"`
	MaxBatchBytes   int `json:"max_batch_bytes,omitempty"`
	FlushIntervalMs int `json:"flush_interval_ms,omitempty"`
	MaxQueueSize    int `json:"max_queue_size,omitempty"`
}

// EnqueueParams contains parameters for enqueueing items
type EnqueueParams struct {
	Items []EnqueueItem `json:"items"`
}

// EnqueueItem is a single item to enqueue
type EnqueueItem struct {
	Type    string          `json:"type"` // "start" or "end"
	Payload json.RawMessage `json:"payload"`
}

// StatsResult contains statistics
type StatsResult struct {
	Sent      uint64 `json:"sent"`
	Failed    uint64 `json:"failed"`
	Pending   uint64 `json:"pending"`
	Dropped   uint64 `json:"dropped"`
	QueueSize int    `json:"queue_size"`
}

// NewServer creates a new server instance
func NewServer(socketPath string) *Server {
	return &Server{
		socketPath: socketPath,
		shutdown:   make(chan struct{}),
		clients:    make(map[net.Conn]struct{}),
	}
}

// Run starts the server and listens for connections
func (s *Server) Run() error {
	// Remove existing socket file if it exists
	if err := os.RemoveAll(s.socketPath); err != nil {
		return fmt.Errorf("failed to remove existing socket: %w", err)
	}

	// Create the Unix socket listener
	listener, err := net.Listen("unix", s.socketPath)
	if err != nil {
		return fmt.Errorf("failed to listen on socket: %w", err)
	}
	s.listener = listener

	// Set socket permissions (readable/writable by owner)
	if err := os.Chmod(s.socketPath, 0600); err != nil {
		listener.Close()
		return fmt.Errorf("failed to set socket permissions: %w", err)
	}

	log.Printf("Listening on %s", s.socketPath)

	// Handle shutdown signals
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigChan
		log.Println("Received shutdown signal")
		s.Shutdown()
	}()

	// Accept connections
	for {
		conn, err := listener.Accept()
		if err != nil {
			select {
			case <-s.shutdown:
				return nil
			default:
				log.Printf("Accept error: %v", err)
				continue
			}
		}

		s.clientsMu.Lock()
		s.clients[conn] = struct{}{}
		s.clientsMu.Unlock()

		go s.handleConnection(conn)
	}
}

func (s *Server) handleConnection(conn net.Conn) {
	defer func() {
		conn.Close()
		s.clientsMu.Lock()
		delete(s.clients, conn)
		s.clientsMu.Unlock()
	}()

	reader := bufio.NewReader(conn)
	encoder := json.NewEncoder(conn)

	for {
		line, err := reader.ReadBytes('\n')
		if err != nil {
			return // Connection closed
		}

		var req Request
		if err := json.Unmarshal(line, &req); err != nil {
			s.sendError(encoder, 0, -32700, "Parse error")
			continue
		}

		resp := s.handleRequest(&req)
		if err := encoder.Encode(resp); err != nil {
			log.Printf("Failed to encode response: %v", err)
			return
		}
	}
}

func (s *Server) handleRequest(req *Request) Response {
	switch req.Method {
	case "init":
		return s.handleInit(req)
	case "enqueue":
		return s.handleEnqueue(req)
	case "flush":
		return s.handleFlush(req)
	case "stats":
		return s.handleStats(req)
	case "shutdown":
		return s.handleShutdown(req)
	default:
		return Response{
			ID:    req.ID,
			Error: &ErrorResponse{Code: -32601, Message: "Method not found"},
		}
	}
}

func (s *Server) handleInit(req *Request) Response {
	var params InitParams
	if err := json.Unmarshal(req.Params, &params); err != nil {
		return Response{
			ID:    req.ID,
			Error: &ErrorResponse{Code: -32602, Message: "Invalid params: " + err.Error()},
		}
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	if s.running {
		// Already initialized - just return OK
		// This allows multiple Python processes to connect
		result, _ := json.Marshal(map[string]bool{"ok": true})
		return Response{ID: req.ID, Result: result}
	}

	// Create queue
	maxQueueSize := 100000
	if params.Config != nil && params.Config.MaxQueueSize > 0 {
		maxQueueSize = params.Config.MaxQueueSize
	}
	s.queue = NewQueue(maxQueueSize)

	// Create HTTP sender
	httpConfig := DefaultHTTPSenderConfig(params.ServerURL)
	if params.Auth != nil {
		httpConfig.Auth = &BasicAuth{
			Username: params.Auth.Username,
			Password: params.Auth.Password,
		}
	}
	httpConfig.Headers = params.Headers
	s.sender = NewHTTPSender(httpConfig)

	// Create batcher
	batchConfig := DefaultBatchConfig()
	if params.Config != nil {
		if params.Config.MaxBatchSize > 0 {
			batchConfig.MaxBatchSize = params.Config.MaxBatchSize
		}
		if params.Config.MaxBatchBytes > 0 {
			batchConfig.MaxBatchBytes = params.Config.MaxBatchBytes
		}
		if params.Config.FlushIntervalMs > 0 {
			batchConfig.FlushInterval = time.Duration(params.Config.FlushIntervalMs) * time.Millisecond
		}
	}
	s.batcher = NewBatcher(batchConfig, s.queue, s.sender)

	// Start batcher
	s.batcher.Start()
	s.running = true

	result, _ := json.Marshal(map[string]bool{"ok": true})
	return Response{ID: req.ID, Result: result}
}

func (s *Server) handleEnqueue(req *Request) Response {
	var params EnqueueParams
	if err := json.Unmarshal(req.Params, &params); err != nil {
		return Response{
			ID:    req.ID,
			Error: &ErrorResponse{Code: -32602, Message: "Invalid params: " + err.Error()},
		}
	}

	s.mu.Lock()
	if !s.running {
		s.mu.Unlock()
		return Response{
			ID:    req.ID,
			Error: &ErrorResponse{Code: -32000, Message: "Not initialized"},
		}
	}
	queue := s.queue
	s.mu.Unlock()

	// Convert to queue entries
	entries := make([]QueueEntry, len(params.Items))
	now := time.Now().UnixNano()
	for i, item := range params.Items {
		entries[i] = QueueEntry{
			Type:      item.Type,
			Payload:   item.Payload,
			Timestamp: now,
		}
	}

	// Enqueue
	ids := queue.Enqueue(entries)

	result, _ := json.Marshal(map[string]interface{}{
		"ids": ids,
	})
	return Response{ID: req.ID, Result: result}
}

func (s *Server) handleFlush(req *Request) Response {
	s.mu.Lock()
	if !s.running {
		s.mu.Unlock()
		return Response{
			ID:    req.ID,
			Error: &ErrorResponse{Code: -32000, Message: "Not initialized"},
		}
	}
	batcher := s.batcher
	s.mu.Unlock()

	batcher.FlushAll()

	result, _ := json.Marshal(map[string]bool{"ok": true})
	return Response{ID: req.ID, Result: result}
}

func (s *Server) handleStats(req *Request) Response {
	s.mu.Lock()
	if !s.running {
		s.mu.Unlock()
		return Response{
			ID:    req.ID,
			Error: &ErrorResponse{Code: -32000, Message: "Not initialized"},
		}
	}
	batcher := s.batcher
	queue := s.queue
	s.mu.Unlock()

	sent, failed := batcher.Stats()
	queueLen := queue.Len()
	dropped := queue.DroppedCount()

	result, _ := json.Marshal(StatsResult{
		Sent:      sent,
		Failed:    failed,
		Pending:   uint64(queueLen),
		Dropped:   dropped,
		QueueSize: queueLen,
	})
	return Response{ID: req.ID, Result: result}
}

func (s *Server) handleShutdown(req *Request) Response {
	go func() {
		time.Sleep(100 * time.Millisecond) // Give time for response to be sent
		s.Shutdown()
	}()

	result, _ := json.Marshal(map[string]bool{"ok": true})
	return Response{ID: req.ID, Result: result}
}

// Shutdown gracefully shuts down the server
func (s *Server) Shutdown() {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.running {
		// Stop batcher (will flush)
		if s.batcher != nil {
			s.batcher.Stop()
		}
		s.running = false
	}

	// Close listener
	if s.listener != nil {
		s.listener.Close()
	}

	// Close all client connections
	s.clientsMu.Lock()
	for conn := range s.clients {
		conn.Close()
	}
	s.clientsMu.Unlock()

	// Remove socket file
	os.RemoveAll(s.socketPath)

	close(s.shutdown)
}

func (s *Server) sendError(encoder *json.Encoder, id int, code int, message string) {
	encoder.Encode(Response{
		ID:    id,
		Error: &ErrorResponse{Code: code, Message: message},
	})
}
