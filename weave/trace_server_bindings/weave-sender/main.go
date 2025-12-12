package main

import (
	"flag"
	"log"
	"os"
	"path/filepath"
)

// Verbose controls debug logging
var Verbose bool

func main() {
	// Set up logging to stderr
	log.SetOutput(os.Stderr)
	log.SetFlags(log.Ltime | log.Lmicroseconds | log.Lshortfile)

	// Parse flags
	socketPath := flag.String("socket", "", "Path to Unix domain socket (default: /tmp/weave-sender.sock)")
	verbose := flag.Bool("verbose", false, "Enable verbose debug logging")
	flag.Parse()

	Verbose = *verbose

	// Default socket path includes UID for per-user isolation
	if *socketPath == "" {
		*socketPath = filepath.Join(os.TempDir(), "weave-sender.sock")
	}

	log.Printf("Starting weave-sender on socket: %s (verbose=%v)", *socketPath, Verbose)

	server := NewServer(*socketPath)
	if err := server.Run(); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
