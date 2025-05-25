# %% [markdown]
# # 🐝 Weave Workshop: Build, Track, and Evaluate LLM Applications
#
# <img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />
#
# Welcome to the Weave workshop! In this hands-on session, you'll learn how to use Weave to develop, debug, and evaluate AI-powered applications.
#
# **What you'll learn:**
# - 🔍 **Trace & Debug**: Track every LLM call, see inputs/outputs, and debug issues
# - 📊 **Evaluate**: Build rigorous evaluations with multiple scoring functions
# - 🏃 **Compare**: Run A/B tests and compare different approaches
# - 📈 **Monitor**: Track costs, latency, and performance metrics
# - 🎯 **Iterate**: Use data-driven insights to improve your application

# %% [markdown]
# ## 🔑 Prerequisites
#
# Before we begin, let's set up your environment.

# %%
# Install dependencies
# %pip install wandb weave openai pydantic nest_asyncio -qqq

import asyncio
import os
import random
from datetime import datetime
from getpass import getpass
from typing import Any, Optional

import weave
from weave import Scorer

# 🔑 Setup your API keys
print("📝 Setting up API keys...")

# Weights & Biases will automatically prompt if needed
# It checks: 1) WANDB_API_KEY env var, 2) ~/.netrc, 3) prompts user
print("✅ W&B authentication will be handled automatically by Weave")
print("   (Optional: You can set WANDB_API_KEY env variable if you prefer)")

# OpenAI requires manual setup
print("\n🤖 OpenAI Setup:")
if not os.environ.get("OPENAI_API_KEY"):
    print(
        "You can generate your OpenAI API key here: https://platform.openai.com/api-keys"
    )
    os.environ["OPENAI_API_KEY"] = getpass("Enter your OpenAI API key: ")
else:
    print("✅ OpenAI API key found in environment")

print("\n---")

# 🏠 Initialize your W&B project
print("🐝 Initializing Weave...")
weave_client = weave.init("weave-workshop")  # 🐝 Your W&B project name


# %% [markdown]
# ## 🎯 Part 3: Production Monitoring with Scorers
#
# Use Weave's scorer system for real-time guardrails and quality monitoring.
# This demonstrates the apply_scorer pattern for production use.
#
# **Key Concepts**:
# - **Guardrails**: Block or modify responses (e.g., toxicity filter)
# - **Monitors**: Track quality metrics without blocking

# %%
from datetime import datetime


# Define more realistic production scorers
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


@weave.op
def production_email_handler(
    email: str, request_id: Optional[str] = None
) -> dict[str, Any]:
    """Production-ready email handler that returns structured analysis results."""
    start_time = datetime.now()

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


# Initialize scorers
content_moderation_scorer = ContentModerationScorer()
quality_scorer = ExtractionQualityScorer()


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

        if quality_check.result["issues"]:
            print(f"📊 Quality issues: {quality_check.result['issues']}")

        if quality_check.result["recommendations"]:
            print(f"💡 Recommendations: {quality_check.result['recommendations']}")

    return result


# Test with varied examples showing both success and failure cases
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
    # Excellent quality - should get high scores
    {
        "email": "Hi there,\n\nI'm Lisa Chen from GlobalTech Solutions. I wanted to thank you for the excellent support on our CloudBackup Enterprise v4.2 deployment. Everything is working perfectly and the performance improvements are fantastic!\n\nBest,\nLisa Chen\nVP of Engineering",
        "expected": "✅ Excellent quality with positive sentiment",
    },
    # Missing critical info - should fail quality check
    {
        "email": "Your system crashed and we lost everything! This is unacceptable! Fix this immediately!!!",
        "expected": "❌ Should fail quality - missing customer/product info",
    },
    # Edge case - urgent but positive
    {
        "email": "Urgent: I'm Alex Kumar and I love your RapidDeploy tool! Need to purchase 50 more licenses ASAP for our new team starting Monday. Please expedite!\n\nAlex Kumar\nProcurement Manager",
        "expected": "📊 Unusual case - urgent but positive sentiment",
    },
]

for i, test_case in enumerate(production_test_emails):
    print(f"\n{'='*60}")
    print(f"📧 Test {i+1}/8: {test_case['expected']}")
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

    # 1. Performance
    perf = result.get("performance", {})
    print(
        f"   ⏱️  Response Time: {perf.get('grade', 'unknown')} ({result.get('processing_time_ms', 0):.0f}ms)"
    )
    print(
        f"      SLA Status: {'✅ Met' if perf.get('sla_met', False) else '❌ Exceeded'}"
    )

    # 2. Content Moderation
    if result["status"] == "success":
        if result.get("blocked"):
            print("   🚫 Content Moderation: BLOCKED")
            print(f"      Reason: {result['block_reason']}")
        elif result.get("needs_review"):
            print("   ⚠️  Content Moderation: REVIEW NEEDED")
            print(f"      Flags: {result['review_reason']}")
        else:
            print("   ✅ Content Moderation: PASSED")

    # 3. Quality Assessment
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
            # The actual issues are logged by the scorers and visible in Weave UI

print("\n" + "=" * 70)
print("\n🎯 Summary of Production Monitoring Demonstration:")
print("\n1. **Successful Cases** (Tests 1, 4, 6):")
print("   - High-quality extractions with version numbers")
print("   - All required fields present and accurate")
print("   - Fast response times meeting SLA")

print("\n2. **Blocked Content** (Test 2):")
print("   - Multiple profanity words + legal threats = automatic block")
print("   - Protects support agents from abusive content")

print("\n3. **Review Required** (Test 5):")
print("   - Mild profanity triggers review flag")
print("   - Human can decide if response is appropriate")

print("\n4. **Quality Issues** (Tests 3, 7):")
print("   - Missing customer name or product details")
print("   - Too brief to be actionable")
print("   - Would need human intervention")

print("\n5. **Edge Cases** (Test 8):")
print("   - Urgent + positive sentiment (unusual combination)")
print("   - System handles it correctly")

print("\n💡 Key Insights:")
print("   - Different scorers serve different purposes")
print("   - Guardrails (block/review) vs Monitors (quality/performance)")
print("   - All scorer results are tracked in Weave for analysis")
print("\n✅ Check the Weave UI to see detailed scorer results and traces!")


# %% [markdown]
# ### 👥 Part 3.1: Human Feedback & Dataset Building
#
# Learn how to collect human feedback and build datasets from production data.
# This creates a feedback loop for continuous model improvement.
# TODO: New Cell: Here, we are going to make an interactive "app" that renders in the cell so that the user can directly interact with the model. This will then generate calls in the UI and we can see calls coming into the application. From there we can setup a human feedback column interactively, collect examples, narrow down to the hard cases, and add to a dataset, which can then be used for the next round of evaluations:
#   1. Create an interactive output that allows for form-fill-style querying of the model
#   2. Add feedback so that the user can mark the reponse as good or bad (use the API to send this feedback)
#       * (Show in the UI that you can configure custom columns and form fill directly in the app if you have experts on your side)
#   3. (UI) Query for the bad results in the UI
#   4. (UI) Add the bad results to a dataset
#   5. (Optional) Next cell: create a new evaluation using the new dataset - presumably the models have a harder time... or just say that it is possible
