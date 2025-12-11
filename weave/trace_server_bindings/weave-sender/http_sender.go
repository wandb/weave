package main

import (
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"
)

// Pool of gzip writers to reduce allocations
var gzipWriterPool = sync.Pool{
	New: func() interface{} {
		return gzip.NewWriter(nil)
	},
}

// HTTPSender handles sending batches to the Weave server
type HTTPSender struct {
	client      *http.Client
	baseURL     string
	auth        *BasicAuth
	headers     map[string]string
}

// BasicAuth holds HTTP basic auth credentials
type BasicAuth struct {
	Username string
	Password string
}

// HTTPSenderConfig configures the HTTP sender
type HTTPSenderConfig struct {
	BaseURL        string
	Auth           *BasicAuth
	Headers        map[string]string
	Timeout        time.Duration
	MaxConnections int
}

// DefaultHTTPSenderConfig returns sensible defaults
func DefaultHTTPSenderConfig(baseURL string) HTTPSenderConfig {
	return HTTPSenderConfig{
		BaseURL:        baseURL,
		Timeout:        30 * time.Second,
		MaxConnections: 16, // Match concurrent sends capacity
	}
}

// NewHTTPSender creates a new HTTP sender
func NewHTTPSender(config HTTPSenderConfig) *HTTPSender {
	transport := &http.Transport{
		MaxIdleConns:        config.MaxConnections,
		MaxIdleConnsPerHost: config.MaxConnections,
		IdleConnTimeout:     90 * time.Second,
	}

	client := &http.Client{
		Transport: transport,
		Timeout:   config.Timeout,
	}

	return &HTTPSender{
		client:  client,
		baseURL: config.BaseURL,
		auth:    config.Auth,
		headers: config.Headers,
	}
}

// SetAuth sets the authentication credentials
func (s *HTTPSender) SetAuth(username, password string) {
	s.auth = &BasicAuth{Username: username, Password: password}
}

// SetHeaders sets additional headers
func (s *HTTPSender) SetHeaders(headers map[string]string) {
	s.headers = headers
}

// ServerBatchRequest is the format expected by /call/upsert_batch
type ServerBatchRequest struct {
	Batch []ServerBatchItem `json:"batch"`
}

// ServerBatchItem represents a single item in the batch
type ServerBatchItem struct {
	Mode string          `json:"mode"` // "start" or "end"
	Req  json.RawMessage `json:"req"`
}

// SendBatch sends a batch of items to the server
func (s *HTTPSender) SendBatch(ctx context.Context, batch Batch) error {
	if len(batch.Items) == 0 {
		return nil
	}

	// Convert to server format
	serverBatch := ServerBatchRequest{
		Batch: make([]ServerBatchItem, len(batch.Items)),
	}

	for i, item := range batch.Items {
		serverBatch.Batch[i] = ServerBatchItem{
			Mode: item.Type,
			Req:  item.Payload,
		}
	}

	body, err := json.Marshal(serverBatch)
	if err != nil {
		return fmt.Errorf("failed to marshal batch: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", s.baseURL+"/call/upsert_batch", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	// Add auth
	if s.auth != nil {
		req.SetBasicAuth(s.auth.Username, s.auth.Password)
	}

	// Add custom headers
	for k, v := range s.headers {
		req.Header.Set(k, v)
	}

	resp, err := s.client.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return &HTTPError{
			StatusCode: resp.StatusCode,
			Body:       string(body),
		}
	}

	return nil
}

// HTTPError represents an HTTP error response
type HTTPError struct {
	StatusCode int
	Body       string
}

func (e *HTTPError) Error() string {
	return fmt.Sprintf("HTTP %d: %s", e.StatusCode, e.Body)
}

// IsRetryable returns true if the error is retryable
func (e *HTTPError) IsRetryable() bool {
	// Retry server errors (5xx) and rate limits (429)
	return e.StatusCode >= 500 || e.StatusCode == 429
}
