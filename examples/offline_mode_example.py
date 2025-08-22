"""Example demonstrating Weave offline mode functionality.

This example shows how to:
1. Initialize Weave in offline mode to save traces locally
2. Run operations that generate traces
3. Sync the offline data to the server when online
"""

import weave
import time
import random


def simulate_network_offline():
    """Simulate being offline - in real usage this would be actual network unavailability."""
    print("\n🔌 Simulating offline environment...")
    print("All traces will be saved locally.\n")


def simulate_network_online():
    """Simulate being back online."""
    print("\n🌐 Simulating online environment...")
    print("Ready to sync offline data.\n")


def main():
    # Step 1: Initialize Weave in offline mode
    # This will save all traces to local files instead of sending to server
    print("=== Initializing Weave in Offline Mode ===")
    client = weave.init(
        project_name="my_team/offline_demo",
        offline=True,
        offline_dir="./weave_offline_data"  # Optional: specify custom directory
    )
    
    simulate_network_offline()
    
    # Step 2: Define and use operations as normal
    @weave.op
    def process_data(data: list[int]) -> dict:
        """Process a list of numbers and return statistics."""
        time.sleep(0.1)  # Simulate processing time
        return {
            "count": len(data),
            "sum": sum(data),
            "mean": sum(data) / len(data) if data else 0,
            "max": max(data) if data else None,
            "min": min(data) if data else None,
        }
    
    @weave.op
    def generate_report(stats: dict, name: str) -> str:
        """Generate a text report from statistics."""
        report = f"Report: {name}\n"
        report += f"  Count: {stats['count']}\n"
        report += f"  Sum: {stats['sum']}\n"
        report += f"  Mean: {stats['mean']:.2f}\n"
        report += f"  Range: {stats['min']} to {stats['max']}\n"
        return report
    
    @weave.op
    def pipeline(dataset_name: str, size: int) -> str:
        """Full pipeline that generates data, processes it, and creates a report."""
        # Generate random data
        data = [random.randint(1, 100) for _ in range(size)]
        
        # Process the data
        stats = process_data(data)
        
        # Generate report
        report = generate_report(stats, dataset_name)
        
        return report
    
    # Step 3: Run operations while offline
    print("=== Running Operations in Offline Mode ===")
    
    # Run multiple operations to generate traces
    for i in range(3):
        dataset_name = f"Dataset_{i+1}"
        print(f"Processing {dataset_name}...")
        result = pipeline(dataset_name, size=10 + i*5)
        print(f"  ✓ Completed (data saved locally)")
    
    # Also test error handling
    @weave.op
    def risky_operation(value: int) -> int:
        if value < 0:
            raise ValueError("Value must be positive")
        return value * 2
    
    try:
        risky_operation(-1)
    except ValueError:
        print("  ✓ Error trace saved locally")
    
    # Step 4: Finish the client to ensure all data is written
    weave.finish()
    print("\n✅ All offline operations completed and saved locally")
    print(f"📁 Data saved to: ./weave_offline_data")
    
    # Step 5: Later, when back online, sync the data
    simulate_network_online()
    
    print("=== Syncing Offline Data to Server ===")
    print("To sync your offline data, run:")
    print("  weave.sync_offline_data(offline_dir='./weave_offline_data')")
    print("\nOr sync a specific project:")
    print("  weave.sync_offline_data(offline_dir='./weave_offline_data', project_name='my_team/offline_demo')")
    
    # In a real scenario, you would authenticate first, then sync:
    # weave.init("my_team/offline_demo")  # Initialize normally (online)
    # results = weave.sync_offline_data(offline_dir="./weave_offline_data")
    # print(f"Sync results: {results}")


if __name__ == "__main__":
    main()
    
    print("\n" + "="*50)
    print("Offline Mode Demo Complete!")
    print("="*50)
    print("\nKey Features Demonstrated:")
    print("✓ Initialize Weave in offline mode")
    print("✓ Run operations and generate traces locally")
    print("✓ Save traces to compressed JSON files")
    print("✓ Prepare for syncing when back online")
    print("\nOffline data structure:")
    print("  ./weave_offline_data/")
    print("    └── my_team/")
    print("        └── offline_demo/")
    print("            ├── calls/       # Operation traces")
    print("            ├── objects/     # Saved objects")
    print("            └── metadata/    # Project metadata")