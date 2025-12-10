package main

import (
	"flag"
	"log"
	"os"
	"path/filepath"
)

func main() {
	// Set up logging to stderr
	log.SetOutput(os.Stderr)
	log.SetFlags(log.Ltime | log.Lmicroseconds | log.Lshortfile)

	// Parse flags
	socketPath := flag.String("socket", "", "Path to Unix domain socket (default: /tmp/weave-sender-<uid>.sock)")
	flag.Parse()

	// Default socket path includes UID for per-user isolation
	if *socketPath == "" {
		*socketPath = filepath.Join(os.TempDir(), "weave-sender.sock")
	}

	log.Printf("Starting weave-sender on socket: %s", *socketPath)

	server := NewServer(*socketPath)
	if err := server.Run(); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
