# %% [markdown]
# # Part 3: Production Monitoring with Weave
#
# <img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />
#
# Learn how to monitor LLM applications in production using Weave's scorer system for real-time guardrails and quality monitoring.
#
# **In this section:**
# - 🛡️ **Guardrails**: Block or modify responses with content moderation
# - 📊 **Quality Monitoring**: Track extraction quality and completeness
# - ⚡ **Performance Tracking**: Monitor response times and SLA compliance
# - 🔄 **Real-time Scoring**: Apply scorers to live production calls
# - 👥 **Human Feedback**: Collect feedback and build datasets from production
# - 📈 **Continuous Improvement**: Use production data to improve models

# %% [markdown]
# ## Setup
#
# Install dependencies and configure API keys.
#
# OpenAI API key can be found at https://platform.openai.com/api-keys

# %%
# Install dependencies
# %pip install wandb weave openai pydantic nest_asyncio ipywidgets set-env-colab-kaggle-dotenv -qqq

import asyncio
import os
import random
from datetime import datetime
from typing import Any, Optional

# For notebooks, use nest_asyncio to handle async properly
import nest_asyncio
from openai import OpenAI
from pydantic import BaseModel, Field
from set_env import set_env

import weave
from weave import Scorer

nest_asyncio.apply()

# Setup API keys
os.environ["OPENAI_API_KEY"] = set_env("OPENAI_API_KEY")

# Initialize Weave
weave_client = weave.init("weave-product-tour")

# %% [markdown]
# ## 🎯 Part 3: Production Monitoring
#
# Use Weave's scorer system for real-time guardrails and quality monitoring.
# This demonstrates the apply_scorer pattern for production use.
#
# **Key Concepts**:
# - **Guardrails**: Block or modify responses (e.g., toxicity filter)
# - **Monitors**: Track quality metrics without blocking


# %%
# Define our data structure
class CustomerEmail(BaseModel):
    customer_name: str
    product: str
    issue: str
    sentiment: str = Field(description="positive, neutral, or negative")


# 🎯 Track functions with @weave.op
@weave.op
def analyze_customer_email(email: str) -> CustomerEmail:
    """Analyze a customer support email and extract key information."""
    client = OpenAI()

    # 🔥 OpenAI calls are automatically traced by Weave!
    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",  # Using mini model for cost efficiency
        messages=[
            {
                "role": "system",
                "content": "Extract customer name, product, issue, and sentiment.",
            },
            {
                "role": "user",
                "content": email,
            },
        ],
        response_format=CustomerEmail,
    )

    return response.choices[0].message.parsed


@weave.op
def classify_urgency(email: str, sentiment: str) -> str:
    """Determine urgency level based on content and sentiment."""
    urgent_keywords = [
        "urgent",
        "asap",
        "immediately",
        "frustrated",
        "broken",
        "stopped working",
    ]

    # Check for urgent keywords
    email_lower = email.lower()
    has_urgent_keywords = any(keyword in email_lower for keyword in urgent_keywords)

    # Combine sentiment and keywords to determine urgency
    if sentiment == "negative" and has_urgent_keywords:
        return "high"
    elif sentiment == "negative" or has_urgent_keywords:
        return "medium"
    else:
        return "low"


# %% [markdown]
# #### 🛡️ Content Moderation Scorer


# %%
# 🛡️ Define production scorers
class ContentModerationScorer(Scorer):
    """Production-ready content moderation scorer."""

    @weave.op
    def score(self, output: dict) -> dict:
        """Check for inappropriate content using multiple signals."""
        # Handle both success and error cases
        if output.get("status") != "success":
            return {"flagged": False, "flags": [], "severity": "none", "action": "pass"}

        analysis = output.get("analysis", {})
        issue_text = analysis.get("issue", "").lower()
        sentiment = analysis.get("sentiment", "neutral")

        # Check for various inappropriate content patterns
        profanity_patterns = [
            "stupid",
            "idiotic",
            "garbage",
            "trash",
            "sucks",
            "terrible",
            "awful",
            "worst",
        ]
        threat_patterns = ["sue", "lawyer", "legal action", "court", "lawsuit"]

        flags = []
        severity = "none"

        # Check profanity
        profanity_found = []
        for word in profanity_patterns:
            if word in issue_text:
                profanity_found.append(word)

        if profanity_found:
            flags.append(f"Profanity detected: {', '.join(profanity_found)}")
            severity = "medium"

        # Check threats
        threats_found = []
        for pattern in threat_patterns:
            if pattern in issue_text:
                threats_found.append(pattern)

        if threats_found:
            flags.append(f"Legal threat: {', '.join(threats_found)}")
            severity = "high"

        # Check extreme sentiment with profanity
        if sentiment == "negative" and profanity_found:
            severity = "high"
            flags.append("Negative sentiment with profanity")

        return {
            "flagged": len(flags) > 0,
            "flags": flags,
            "severity": severity,
            "action": "block"
            if severity == "high"
            else ("review" if severity == "medium" else "pass"),
        }


# %% [markdown]
# #### 📊 Quality Assessment Scorer


# %%
class ExtractionQualityScorer(Scorer):
    """Monitor extraction quality and completeness."""

    @weave.op
    def score(self, output: dict, email: str) -> dict:
        """Comprehensive quality assessment."""
        if output.get("status") != "success":
            return {
                "quality_score": 0.0,
                "passed": False,
                "issues": ["Failed to process email"],
                "recommendations": [],
                "extraction_grade": "F",
            }

        analysis = output.get("analysis", {})
        quality_metrics = {
            "completeness": 0.0,
            "specificity": 0.0,
            "accuracy": 0.0,
            "consistency": 0.0,
        }
        issues = []
        recommendations = []

        # 1. Completeness checks (40% weight)
        if analysis.get("customer_name") and analysis["customer_name"] not in [
            "Unknown",
            "",
            None,
        ]:
            quality_metrics["completeness"] += 0.15
        else:
            issues.append("Missing customer name")
            recommendations.append("Check email signatures and greetings for names")

        if analysis.get("product") and analysis["product"] not in ["Unknown", "", None]:
            quality_metrics["completeness"] += 0.15
        else:
            issues.append("Missing product identification")
            recommendations.append("Look for product names mentioned in the email")

        if analysis.get("issue") and len(analysis["issue"]) > 10:
            quality_metrics["completeness"] += 0.10
        else:
            issues.append("Issue description too brief or missing")
            recommendations.append("Extract a more detailed problem description")

        # 2. Specificity checks (30% weight)
        product_name = analysis.get("product", "")
        if product_name and any(char.isdigit() for char in str(product_name)):
            # Product includes version/model number
            quality_metrics["specificity"] += 0.15
        elif product_name:
            recommendations.append(
                "Extract product version/model numbers when available"
            )

        issue_desc = analysis.get("issue", "")
        if issue_desc and len(str(issue_desc)) > 30:
            quality_metrics["specificity"] += 0.15
        elif issue_desc:
            recommendations.append("Provide more specific issue details")

        # 3. Accuracy checks (20% weight)
        # Check if extracted content actually appears in email
        email_lower = email.lower()
        customer_name = analysis.get("customer_name", "")
        if customer_name and customer_name != "Unknown":
            name_parts = customer_name.lower().split()
            # Check if at least part of the name appears in email
            if any(part in email_lower for part in name_parts if len(part) > 2):
                quality_metrics["accuracy"] += 0.10
            else:
                issues.append("Extracted name not found in original email")

        product_mentioned = analysis.get("product", "")
        if product_mentioned and product_mentioned != "Unknown":
            # Check for partial matches (product names might be extracted differently)
            product_words = product_mentioned.lower().split()
            if any(word in email_lower for word in product_words if len(word) > 3):
                quality_metrics["accuracy"] += 0.10
            else:
                issues.append("Extracted product not clearly mentioned in email")

        # 4. Consistency checks (10% weight)
        sentiment = analysis.get("sentiment", "neutral")
        urgency = output.get("urgency", "low")

        # Check sentiment/urgency consistency
        consistency_ok = True
        if sentiment == "negative" and urgency == "low":
            if not any(
                word in issue_desc.lower() for word in ["minor", "small", "slight"]
            ):
                consistency_ok = False
                issues.append(
                    "Negative sentiment but low urgency - might be inconsistent"
                )
        elif sentiment == "positive" and urgency == "high":
            consistency_ok = False
            issues.append("Positive sentiment with high urgency is unusual")

        if consistency_ok:
            quality_metrics["consistency"] += 0.10

        # Calculate overall score
        total_score = sum(quality_metrics.values())

        return {
            "quality_score": total_score,
            "quality_metrics": quality_metrics,
            "passed": total_score >= 0.6,  # Lowered threshold for demo
            "issues": issues,
            "recommendations": recommendations,
            "extraction_grade": "A"
            if total_score >= 0.9
            else (
                "B"
                if total_score >= 0.8
                else (
                    "C" if total_score >= 0.6 else ("D" if total_score >= 0.4 else "F")
                )
            ),
        }


# %% [markdown]
# #### 🏭 Production Email Handler


# %%
@weave.op
def production_email_handler(
    email: str, request_id: Optional[str] = None
) -> dict[str, Any]:
    """Production-ready email handler that returns structured analysis results."""
    # Generate request ID if not provided
    if not request_id:
        request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"

    try:
        # Process the email using our existing analyzer
        analysis = analyze_customer_email(email)

        # Calculate urgency based on the analysis
        urgency = classify_urgency(email, analysis.sentiment)

        # Return structured result that scorers expect
        return {
            "request_id": request_id,
            "status": "success",
            "analysis": {
                "customer_name": analysis.customer_name,
                "product": analysis.product,
                "issue": analysis.issue,
                "sentiment": analysis.sentiment,
            },
            "urgency": urgency,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        # Log error and return error response
        return {
            "request_id": request_id,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


# %% [markdown]
# #### 🔧 Initialize Scorers and Monitoring Function

# %%
# Initialize scorers
content_moderation_scorer = ContentModerationScorer()
quality_scorer = ExtractionQualityScorer()


# %%
async def handle_email_with_monitoring(email: str) -> dict[str, Any]:
    """Handle email with production monitoring and guardrails."""
    # Process the email and get the Call object
    result, call = production_email_handler.call(email)

    if result["status"] == "success":
        # Apply content moderation (guardrail)
        moderation_check = await call.apply_scorer(content_moderation_scorer)

        # Apply quality monitoring
        quality_check = await call.apply_scorer(
            quality_scorer, additional_scorer_kwargs={"email": email}
        )

        # Handle moderation results
        if moderation_check.result["flagged"]:
            action = moderation_check.result["action"]
            if action == "block":
                print(f"🚫 Content BLOCKED: {moderation_check.result['flags']}")
                result["blocked"] = True
                result["block_reason"] = moderation_check.result["flags"]
            elif action == "review":
                print(
                    f"⚠️ Content flagged for review: {moderation_check.result['flags']}"
                )
                result["needs_review"] = True
                result["review_reason"] = moderation_check.result["flags"]

        # Add quality metrics
        result["quality_metrics"] = {
            "grade": quality_check.result["extraction_grade"],
            "score": quality_check.result["quality_score"],
            "passed": quality_check.result["passed"],
        }

        # Show quality issues and recommendations
        if quality_check.result["issues"]:
            print(f"📊 Quality issues: {quality_check.result['issues']}")

        if quality_check.result["recommendations"]:
            print(f"💡 Recommendations: {quality_check.result['recommendations']}")

    return result


# %% [markdown]
# #### 🧪 Test Production Monitoring

# %%
# 🧪 Test production monitoring with realistic scenarios
print("🏭 Testing production monitoring with realistic scenarios...")
print("=" * 70)

production_test_emails = [
    # Good quality extraction - should pass all checks
    {
        "email": "Hello Support Team,\n\nI'm Sarah Mitchell from Acme Corp. Our CloudSync Enterprise v3.2.1 stopped syncing files yesterday at 2pm. The error message says 'Authentication failed'. This is really frustrating and affecting our entire team.\n\nBest regards,\nSarah Mitchell\nIT Manager, Acme Corp",
        "expected": "✅ High quality extraction with version numbers",
    },
    # Profanity with legal threat - should be blocked
    {
        "email": "This stupid software is absolute garbage! I'm John Davis and your DataSync Pro is the worst trash I've ever used. My lawyer will be contacting you about this terrible product that lost our data!",
        "expected": "🚫 Should be blocked - profanity + legal threat",
    },
    # Poor quality but processable - low score but not blocked
    {
        "email": "Hi support, product broken. Fix please. - Tom",
        "expected": "📊 Low quality - minimal details but processable",
    },
    # Good extraction with negative sentiment - quality pass
    {
        "email": "Dear Support,\n\nI'm Mary Johnson, CTO at TechStart Inc. Our DataVault Pro v2.5 backup failed last night with error code 'E501: connection timeout'. This is concerning as we rely on nightly backups for compliance.\n\nMary Johnson\nCTO, TechStart Inc",
        "expected": "✅ Good quality despite negative sentiment",
    },
    # Needs review - mild profanity - should flag for review
    {
        "email": "Mike Wilson here. Your EmailPro system really sucks compared to what was promised, but I guess it's still better than the competition. Can you help me configure the spam filter? It's blocking legitimate emails.",
        "expected": "⚠️ Should flag for review - mild profanity",
    },
]

# %%
# Run a "production" simulation
for i, test_case in enumerate(production_test_emails):
    print(f"\n{'='*60}")
    print(f"📧 Test {i+1}/5: {test_case['expected']}")
    print(f"{'='*60}")

    # Show email preview
    email_lines = test_case["email"].split("\n")
    print("📝 Email Content:")
    for line in email_lines[:3]:  # Show first 3 lines
        if line.strip():
            print(f"   {line[:70]}{'...' if len(line) > 70 else ''}")
    if len(email_lines) > 3:
        print(f"   ... ({len(email_lines)-3} more lines)")

    # Process with monitoring
    result = asyncio.run(handle_email_with_monitoring(test_case["email"]))

    # Show extraction results
    print("\n🔍 Extraction Results:")
    if result["status"] == "success":
        analysis = result["analysis"]
        print(f"   Customer: {analysis.get('customer_name', 'Unknown')}")
        print(f"   Product: {analysis.get('product', 'Unknown')}")
        print(
            f"   Issue: {analysis.get('issue', 'Unknown')[:50]}{'...' if len(analysis.get('issue', '')) > 50 else ''}"
        )
        print(f"   Sentiment: {analysis.get('sentiment', 'Unknown')}")
        print(f"   Urgency: {result.get('urgency', 'Unknown')}")
    else:
        print(f"   ❌ Error: {result.get('error', 'Unknown error')}")

    # Show scorer results
    print("\n📊 Scorer Results:")

    # Content Moderation
    if result["status"] == "success":
        if result.get("blocked"):
            print("   🚫 Content Moderation: BLOCKED")
            print(f"      Reason: {result['block_reason']}")
        elif result.get("needs_review"):
            print("   ⚠️ Content Moderation: REVIEW NEEDED")
            print(f"      Flags: {result['review_reason']}")
        else:
            print("   ✅ Content Moderation: PASSED")

    # Quality Assessment
    if result["status"] == "success":
        quality = result.get("quality_metrics", {})
        print(
            f"   📏 Quality Assessment: Grade {quality.get('grade', 'F')} (Score: {quality.get('score', 0):.2f})"
        )

        # Show what contributed to the score
        if quality.get("score", 0) < 0.6:
            print(
                f"      Status: {'⚠️ Below threshold' if quality.get('passed', False) else '❌ Failed'}"
            )

# %% [markdown]
# ## 3.1: Human Feedback & Data Collection
#
# Learn how to collect human feedback and build datasets from production data.
# This creates a feedback loop for continuous model improvement.

# %%
import uuid

import ipywidgets as widgets
from IPython.display import clear_output, display

# %% [markdown]
# #### 🔄 Interactive Feedback Collection App


# %%
# Create an interactive feedback collection interface
class EmailAnalyzerFeedbackApp:
    def __init__(self):
        self.current_call = None
        self.setup_ui()
        # Generate initial challenging email
        self.generate_challenging_email()

    def setup_ui(self):
        """Create the interactive UI components."""
        # Input area
        self.email_input = widgets.Textarea(
            value="",  # Will be populated by generate_challenging_email()
            placeholder="Enter a customer email to analyze...",
            description="Email:",
            layout=widgets.Layout(width="100%", height="120px"),
        )

        # Action buttons
        self.analyze_button = widgets.Button(
            description="Analyze Email",
            button_style="primary",
            layout=widgets.Layout(width="150px"),
        )
        self.analyze_button.on_click(self.analyze_email)

        self.generate_button = widgets.Button(
            description="Generate New Email",
            button_style="info",
            layout=widgets.Layout(width="150px"),
        )
        self.generate_button.on_click(self.on_generate_email)

        # Output area
        self.output_area = widgets.Output()

        # Feedback buttons (initially hidden)
        self.feedback_area = widgets.VBox([])

        # Main layout
        self.app = widgets.VBox(
            [
                widgets.HTML("<h3>🔄 Interactive Email Analyzer with Feedback</h3>"),
                widgets.HTML(
                    "<p>Analyze challenging emails and provide feedback to improve the model:</p>"
                ),
                self.email_input,
                widgets.HBox(
                    [self.analyze_button, self.generate_button],
                    layout=widgets.Layout(margin="10px 0"),
                ),
                self.output_area,
                self.feedback_area,
            ]
        )

    def analyze_email(self, button):
        """Analyze the email and show results."""
        with self.output_area:
            clear_output()
            print("🔄 Analyzing email...")

        try:
            # Use the .call() method to get both result and call object
            email_text = self.email_input.value.strip()
            if not email_text:
                with self.output_area:
                    clear_output()
                    print("❌ Please enter an email to analyze.")
                return

            # Add session attributes for tracking
            with weave.attributes(
                {"session": str(uuid.uuid4()), "env": "workshop_demo"}
            ):
                result, call = production_email_handler.call(email_text)

            self.current_call = call

            # Display results
            with self.output_area:
                clear_output()
                if result["status"] == "success":
                    analysis = result["analysis"]
                    print("✅ Analysis Complete!")
                    print(f"📧 Customer: {analysis['customer_name']}")
                    print(f"🏷️ Product: {analysis['product']}")
                    print(f"📝 Issue: {analysis['issue']}")
                    print(f"😊 Sentiment: {analysis['sentiment']}")
                    print(f"⚡ Urgency: {result['urgency']}")
                else:
                    print(f"❌ Error: {result.get('error', 'Unknown error')}")

            # Show feedback buttons
            self.show_feedback_buttons()

        except Exception as e:
            with self.output_area:
                clear_output()
                print(f"❌ Error analyzing email: {str(e)}")

    def on_generate_email(self, button):
        """Generate a new challenging email example."""
        self.generate_challenging_email()
        # Clear any previous analysis and feedback
        with self.output_area:
            clear_output()
            print(
                "🎲 New challenging email generated! Click 'Analyze Email' to test it."
            )
        self.feedback_area.children = []

    def show_feedback_buttons(self):
        """Display feedback buttons after analysis."""
        if not self.current_call:
            return

        # Rating slider (0-5)
        self.rating_slider = widgets.IntSlider(
            value=3,
            min=0,
            max=5,
            step=1,
            description="Rating:",
            style={"description_width": "initial"},
            layout=widgets.Layout(width="300px"),
        )

        # Text feedback
        self.feedback_text = widgets.Textarea(
            placeholder="Optional comments about this analysis...",
            description="Comments:",
            layout=widgets.Layout(width="100%", height="80px"),
        )

        # Action buttons
        submit_feedback = widgets.Button(
            description="Submit Feedback",
            button_style="primary",
            layout=widgets.Layout(width="150px"),
        )

        clear_feedback = widgets.Button(
            description="Clear",
            button_style="",
            layout=widgets.Layout(width="100px"),
        )

        # Feedback status
        self.feedback_status = widgets.Output()

        # Event handlers
        def on_submit_feedback(button):
            self.submit_rating_feedback()

        def on_clear_feedback(button):
            self.clear_feedback_form()

        submit_feedback.on_click(on_submit_feedback)
        clear_feedback.on_click(on_clear_feedback)

        # Layout feedback area
        self.feedback_area.children = [
            widgets.HTML("<hr><h4>📝 Provide Feedback</h4>"),
            self.rating_slider,
            self.feedback_text,
            widgets.HBox(
                [submit_feedback, clear_feedback],
                layout=widgets.Layout(margin="10px 0"),
            ),
            self.feedback_status,
        ]

    def submit_rating_feedback(self):
        """Submit rating and comment feedback using the lower-level add method."""
        if not self.current_call:
            with self.feedback_status:
                clear_output()
                print("❌ No call to add feedback to.")
            return

        try:
            rating = self.rating_slider.value
            comment = self.feedback_text.value.strip()

            # Use the lower-level add method for custom feedback type
            feedback_payload = {"rating": rating}
            if comment:
                feedback_payload["comment"] = comment

            self.current_call.feedback.add(
                feedback_type="user_rating",
                payload=feedback_payload,
            )

            # Little hack to submit a score that can be operated on - will
            # not need this in the future.
            @weave.op()
            def user_rating(output):
                return feedback_payload

            asyncio.run(self.current_call.apply_scorer(user_rating))

            with self.feedback_status:
                clear_output()
                feedback_desc = f"rating ({rating}/5)"
                if comment:
                    feedback_desc += " with comment"
                print(f"✅ Feedback submitted: {feedback_desc}")

        except Exception as e:
            with self.feedback_status:
                clear_output()
                print(f"❌ Error submitting feedback: {str(e)}")

    def generate_challenging_email(self):
        """Generate a challenging customer email using LLM."""
        try:
            client = OpenAI()

            # Generate a challenging email scenario
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Generate a realistic but challenging customer support email that tests edge cases for extraction:

REQUIREMENTS:
- Include a clear customer name (but maybe in an unusual place like signature)
- Mention a specific product with version/model if possible
- Have a clear issue description
- Include sentiment (positive/negative/neutral)
- Make it challenging by including:
  * Multiple people mentioned (but only one is the actual sender)
  * Multiple products mentioned (but focus on one with issues)
  * Names that could be confused with products or vice versa
  * Sarcasm, mixed emotions, or subtle sentiment
  * Professional signatures, forwarded emails, or unusual formatting

Keep it realistic and professional. Length: 2-4 sentences plus signature.""",
                    },
                    {
                        "role": "user",
                        "content": "Generate a challenging customer support email:",
                    },
                ],
                temperature=0.8,  # Higher temperature for variety
                max_tokens=200,
            )

            generated_email = response.choices[0].message.content.strip()
            self.email_input.value = generated_email

        except Exception as e:
            # Fallback to a predefined challenging example if LLM fails
            fallback_emails = [
                "Hi Support,\n\nSpoke with Jennifer about the CloudSync issue. Still having problems with WorkflowMax Pro v2.1 crashing during exports. Very frustrating!\n\nMike O'Brien\nCEO, TechStart Inc",
                "RE: Ticket #5678\n\nCustomer María García called about DataVault. She says the backup feature in ArchiveMax Enterprise is working great now, but I'm still having sync issues.\n\nBest regards,\nDr. Rajesh Patel",
                "Johnson recommended your software. Smith loves CloudProcessor. But I'm having terrible issues with it constantly freezing.\n\n—James Wilson\nSenior Developer",
                "Great product overall! Though the InvoiceGen module crashes sometimes when processing large files. Still recommend it to others.\n\nAnna Larsson\nStockholm Office",
            ]
            import random

            self.email_input.value = random.choice(fallback_emails)

    def clear_feedback_form(self):
        """Clear the feedback form and reset to defaults."""
        self.rating_slider.value = 3
        self.feedback_text.value = ""
        # Also clear the email input and generate a new challenging example
        self.generate_challenging_email()
        with self.feedback_status:
            clear_output()
            print("🔄 Form cleared and new example generated")

    def display(self):
        """Display the app."""
        display(self.app)


# %% [markdown]
# #### 🚀 Launch the Feedback App

# %%
# Create and display the feedback app
print("🚀 Starting Interactive Email Analyzer with Feedback Collection...")
feedback_app = EmailAnalyzerFeedbackApp()
feedback_app.display()

# %% [markdown]
# ## Summary
#
# You've learned how to monitor LLM applications in production:
#
# - ✅ **Guardrails**: Implemented content moderation to block inappropriate responses
# - ✅ **Quality Monitoring**: Built comprehensive quality assessment scorers
# - ✅ **Real-time Scoring**: Applied scorers to production calls with `call.apply_scorer()`
# - ✅ **Production Patterns**: Handled errors, edge cases, and performance monitoring
# - ✅ **Human Feedback**: Created interactive feedback collection systems
#
# **Next Steps:**
# - Deploy these patterns in your real applications
# - Set up automated feedback collection in production
# - Build custom scorers for domain-specific quality checks
# - Monitor quality metrics over time in the Weave UI
#
# **Key Takeaways:**
# - Production monitoring requires both guardrails (blocking) and monitors (tracking)
# - Scorers can be applied in real-time to any Weave-traced function call
# - Quality assessment should be comprehensive: completeness, accuracy, consistency
# - Human feedback creates a continuous improvement loop for model development
# - All scorer results and feedback are automatically tracked and visualized in Weave
