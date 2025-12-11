"""Test script for set_view with widgets and lists."""

import io
import os
import sys

# Block IPython to avoid circular import issues with matplotlib
sys.modules["IPython"] = None  # type: ignore
# Set matplotlib backend before any imports
os.environ["MPLBACKEND"] = "Agg"
import numpy as np
from PIL import Image

import weave
from weave import (
    ChildPredictionsWidget,
    Content,
    EvaluationLogger,
    ScoreSummaryWidget,
    Table,
)


def create_test_image(color: tuple[int, int, int], text: str) -> Content:
    """Create a simple colored test image with text."""
    img = Image.new("RGB", (200, 150), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Content.from_bytes(buf.read(), extension="png")


def create_crazy_plot() -> Content:
    """Create a wild visualization with multiple subplots."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(12, 10))
    canvas = FigureCanvasAgg(fig)
    axes = fig.subplots(2, 2)
    fig.suptitle("Wild Data Visualization Dashboard", fontsize=16, fontweight="bold")

    # Plot 1: Spiral with color gradient
    theta = np.linspace(0, 8 * np.pi, 1000)
    r = theta**2
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    axes[0, 0].scatter(x, y, c=theta, cmap="rainbow", s=1, alpha=0.6)
    axes[0, 0].set_title("Logarithmic Spiral", fontweight="bold")
    axes[0, 0].set_aspect("equal")

    # Plot 2: 3D-looking surface
    x = np.linspace(-5, 5, 100)
    y = np.linspace(-5, 5, 100)
    x_grid, y_grid = np.meshgrid(x, y)
    z_grid = np.sin(np.sqrt(x_grid**2 + y_grid**2))
    contour = axes[0, 1].contourf(x_grid, y_grid, z_grid, levels=20, cmap="viridis")
    axes[0, 1].set_title("Ripple Pattern", fontweight="bold")
    fig.colorbar(contour, ax=axes[0, 1])

    # Plot 3: Multiple sine waves
    x = np.linspace(0, 10, 500)
    for freq in [1, 2, 3, 5, 8]:
        y = np.sin(freq * x) / freq
        axes[1, 0].plot(x, y, label=f"freq={freq}", linewidth=2, alpha=0.7)
    axes[1, 0].set_title("Harmonic Series", fontweight="bold")
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)

    # Plot 4: Random walk with trend
    steps = 1000
    walk = np.cumsum(np.random.randn(steps)) + np.linspace(0, 50, steps)
    axes[1, 1].plot(walk, linewidth=2, color="purple", alpha=0.7)
    axes[1, 1].fill_between(
        range(steps), walk, alpha=0.3, color="purple", label="Random Walk"
    )
    axes[1, 1].set_title("Random Walk with Trend", fontweight="bold")
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    fig.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)

    return Content.from_bytes(buf.read(), extension="png")


def main():
    # Initialize weave
    client = weave.init("test-views-widgets")

    # Create an evaluation logger
    ev = EvaluationLogger(
        name="view-widget-test",
        model="test-model",
        dataset="test-dataset",
        scorers=["accuracy", "relevance"],
    )

    # Log some example predictions
    for i in range(5):
        pred = ev.log_prediction(
            inputs={"question": f"What is {i} + {i}?"},
            output=f"The answer is {i * 2}",
        )
        pred.log_score("accuracy", 1.0 if i % 2 == 0 else 0.5)
        pred.log_score("relevance", 0.8 + i * 0.05)
        pred.finish()

    # Create test images for the table
    print("Creating sample images...")
    image_contents = [
        create_test_image((255, 100, 100), "Image 1"),  # Red
        create_test_image((100, 255, 100), "Image 2"),  # Green
        create_test_image((100, 100, 255), "Image 3"),  # Blue
    ]
    print(f"  Created {len(image_contents)} test images")

    # Create a crazy visualization
    print("Creating visualization...")
    plot_content = create_crazy_plot()
    print("  Visualization created")

    # Create a table with rich media (images)
    image_table = Table(
        [
            {
                "id": i + 1,
                "image": image_contents[i],
                "description": f"Sample image {i + 1}",
                "score": round(0.8 + (i * 0.05), 2),
            }
            for i in range(len(image_contents))
        ]
    )

    # Set a single comprehensive view with markdown, widgets, table, and plot
    ev.set_view(
        "evaluation_report",
        [
            Content.from_text(
                "# Evaluation Report\n\n"
                "This comprehensive view demonstrates all the custom view capabilities.\n\n"
                "## Data Visualization\n\n"
                "Below is a wild multi-panel visualization:",
                extension="md",
            ),
            plot_content,
            Content.from_text(
                "## Score Summary\n\nBelow is the score summary from this evaluation:",
                extension="md",
            ),
            ScoreSummaryWidget(),
            Content.from_text(
                "## Predictions\n\nHere are the child predictions from the evaluation:",
                extension="md",
            ),
            ChildPredictionsWidget(),
            Content.from_text(
                "## Results Table\n\n"
                "This table contains images as Content objects, demonstrating rich media support:",
                extension="md",
            ),
            image_table,
        ],
    )

    # Finish the evaluation
    ev.log_summary({"test_summary": "completed"})

    print(f"Evaluation UI URL: {ev.ui_url}")
    print("Done! Check the Weave UI for the evaluation with custom views.")


if __name__ == "__main__":
    main()
