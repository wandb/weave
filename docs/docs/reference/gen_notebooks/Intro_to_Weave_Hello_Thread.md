

:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/notebooks/Intro_to_Weave_Hello_Thread.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/notebooks/Intro_to_Weave_Hello_Thread.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::


# Introduction to Threads

<img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />

Weave is a toolkit for developing AI-powered applications.

_Threads_ in Weave group related traces into conversations, making it easy to track multi-turn interactions with LLMs.

While individual traces capture single function calls, threads automatically organize these traces into coherent sequences—perfect for debugging chat sessions, multi-step workflows, or any scenario where context builds across multiple operations.

Simply use the same thread ID across related `@weave.op` decorated functions, and Weave will link them together, giving you a complete view of how your application handles extended conversations or complex workflows.


## 🔑 Prerequisites (using W&B Inference)

This guide uses the [W&B Inference service](https://weave-docs.wandb.ai/guides/integrations/inference) to provide hosted model inference.

Before you can use the guide, you must complete the [W&B Inference service prerequisites](https://weave-docs.wandb.ai/guides/integrations/inference#prerequisites). 


> **Tip** 
>
> Familiarize yourself with [W&B Inference usage information and limits](https://weave-docs.wandb.ai/guides/integrations/inference#usage-information-and-limits).


```python
# Install dependancies and imports
!pip install wandb weave openai -q

import os
import json
import weave
from getpass import getpass

# 🔑 Setup your API keys
# Running this cell will prompt you for your API key with `getpass` and will not echo to the terminal.
#####
print("---")
print("Find your Weights & Biases API key here: https://wandb.ai/authorize")
os.environ["WANDB_API_KEY"] = getpass("Enter your Weights & Biases API key: ")
print("---")
os.environ["WANDB_TEAM"] = input("Enter your Weights & Biases entity/team name [my_great_team]: ")
os.environ["WANDB_PROJECT"] = input("Enter your Weights & Biases project name [my_super_project]: ")
print("---")
#####

# 🏠 Enter your W&B project name
weave_client = weave.init(f"{os.environ['WANDB_TEAM']}/{os.environ['WANDB_PROJECT']}") # Initialize as: `team_name/project_name`
```

## 🐝 Create your first threads

The following code sample demonstrates how to capture and visualize a capture Traces and Threads.\
Specifically, you create a thread context, which helps you to create, resume, and trace threads in W&B Weave.


```python
# Create customer service bot
import json
from pydantic import BaseModel
from datetime import datetime
from openai import OpenAI

class CustomerProfile(BaseModel):
    customer_id: str
    name: str
    account_type: str
    order_history: list[str]
    open_issues: list[str]

class TicketStatus(BaseModel):
    ticket_id: str
    status: str  # "open", "in_progress", "resolved"
    priority: str  # "low", "medium", "high"
    created_at: datetime
    resolved_at: datetime | None = None

class CustomerServiceBot:
    def __init__(self):
        self.client = OpenAI(
          base_url='https://api.inference.wandb.ai/v1',
          api_key=os.environ["WANDB_API_KEY"],
          project=f"{os.environ['WANDB_TEAM']}/{os.environ['WANDB_PROJECT']}", # Project name as: `team_name/project_name`
        )
        # Mock database of customer profiles
        self.customer_db = {
            "CUST-12345": {
                "name": "Alice Johnson",
                "account_type": "Premium",
                "order_history": ["ORD-001", "ORD-002", "ORD-003"],
                "open_issues": ["Missing package for ORD-003"]
            }
        }
        # Store ticket information
        self.tickets = {}

    @weave.op
    def retrieve_customer_profile(self, customer_id: str) -> CustomerProfile:
        """TURN-LEVEL: Retrieve customer information from database."""
        profile_data = self.customer_db.get(customer_id, {})
        if not profile_data:
            return CustomerProfile(
                customer_id=customer_id,
                name="Unknown",
                account_type="None",
                order_history=[],
                open_issues=[]
            )
        return CustomerProfile(
            customer_id=customer_id,
            **profile_data
        )

    @weave.op
    def create_support_ticket(self, customer_id: str, issue: str) -> str:
        """TURN-LEVEL: Create a new support ticket for the customer."""
        ticket_id = f"TKT-{len(self.tickets) + 1001}"
        self.tickets[ticket_id] = TicketStatus(
            ticket_id=ticket_id,
            status="open",
            priority="medium",
            created_at=datetime.now()
        )
        return ticket_id

    @weave.op
    def generate_response(self, customer_profile: CustomerProfile, message: str, context: list[dict]) -> str:
        """TURN-LEVEL: Generate AI response based on customer message and context."""
        system_prompt = f"""You are a helpful customer service representative.
Customer Info:
- Name: {customer_profile.name}
- Account Type: {customer_profile.account_type}
- Open Issues: {', '.join(customer_profile.open_issues) if customer_profile.open_issues else 'None'}

Be professional, empathetic, and solution-oriented."""

        messages = [{"role": "system", "content": system_prompt}] + context + [{"role": "user", "content": message}]

        response = self.client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content

    @weave.op
    def check_order_status(self, order_id: str) -> dict:
        """TURN-LEVEL: Check the status of a specific order."""
        # Mock order status lookup
        order_statuses = {
            "ORD-001": {"status": "delivered", "date": "2024-01-15"},
            "ORD-002": {"status": "delivered", "date": "2024-01-20"},
            "ORD-003": {"status": "in_transit", "expected": "2024-01-28"}
        }
        return order_statuses.get(order_id, {"status": "not_found"})

    @weave.op
    def mark_ticket_resolved(self, ticket_id: str) -> bool:
        """TURN-LEVEL: Mark a support ticket as resolved."""
        if ticket_id in self.tickets:
            self.tickets[ticket_id].status = "resolved"
            self.tickets[ticket_id].resolved_at = datetime.now()
            return True
        return False
```


```python
# Example: Customer service conversation with async interactions
bot = CustomerServiceBot()
service_id = "30JpiK8wERBiv0NxzlqTKn4LWcj"
customer_id = "CUST-12345"
thread_id = f"support_thread_{service_id}"

# Store conversation state that persists between sessions
conversation_state = {
    "context": [],
    "ticket_id": None,
    "status": "active"
}

# ---

# SESSION 1: Customer initiates conversation
print("=== SESSION 1: Customer initiates support request ===")
with weave.thread(thread_id) as thread_ctx:
    print(f"Thread ID: {thread_ctx.thread_id}\n")

    # Turn 1: Customer initiates contact
    print("Customer: Hi, I'm having issues with my recent order")

    # Retrieve customer profile (non-LLM operation)
    profile = bot.retrieve_customer_profile(customer_id)
    print(f"[System: Retrieved profile for {profile.name}]")

    # Generate initial response
    response = bot.generate_response(
        profile,
        "Hi, I'm having issues with my recent order",
        conversation_state["context"]
    )
    print(f"Bot: {response}\n")

    # Update conversation state
    conversation_state["context"].extend([
        {"role": "user", "content": "Hi, I'm having issues with my recent order"},
        {"role": "assistant", "content": response}
    ])

    print("[Customer leaves to check order details...]")
```


```python
# SESSION 2: Customer returns with more information
print("\n⏰ Time passes... Customer returns 2 hours later\n")
print("=== SESSION 2: Customer provides order details ===")
with weave.thread(thread_id) as thread_ctx:
    print(f"Resuming thread: {thread_ctx.thread_id}\n")

    # Retrieve saved conversation context
    print(f"[System: Found {len(conversation_state['context'])//2} previous turns in conversation]")

    # Turn 2: Customer provides more details
    print("Customer: My order ORD-003 should have arrived yesterday but I haven't received it")

    # Retrieve customer profile again
    profile = bot.retrieve_customer_profile(customer_id)

    # Check order status (non-LLM operation)
    order_status = bot.check_order_status("ORD-003")
    print(f"[System: Order status - {order_status}]")

    # Generate response with order information
    response = bot.generate_response(
        profile,
        "My order ORD-003 should have arrived yesterday but I haven't received it",
        conversation_state["context"]
    )
    print(f"Bot: {response}\n")

    # Update conversation state
    conversation_state["context"].extend([
        {"role": "user", "content": "My order ORD-003 should have arrived yesterday but I haven't received it"},
        {"role": "assistant", "content": response}
    ])

    # Create support ticket
    ticket_id = bot.create_support_ticket(customer_id, "Missing package for ORD-003")
    conversation_state["ticket_id"] = ticket_id
    print(f"[System: Created support ticket {ticket_id}]")

    print("[Customer needs to leave for a meeting...]")
```


```python
# SESSION 3: Customer follows up
print("\n⏰ Time passes... Customer returns next day\n")
print("=== SESSION 3: Customer checks on ticket status ===")
with weave.thread(thread_id) as thread_ctx:
    print(f"Resuming thread: {thread_ctx.thread_id}\n")

    # Retrieve saved state
    print(f"[System: Found {len(conversation_state['context'])//2} previous turns]")
    print(f"[System: Active ticket: {conversation_state['ticket_id']}]")

    # Retrieve customer profile
    profile = bot.retrieve_customer_profile(customer_id)

    # Turn 3: Customer asks for update
    print("Customer: Hi, I'm back. Any update on my missing package?")

    response = bot.generate_response(
        profile,
        "Hi, I'm back. Any update on my missing package?",
        conversation_state["context"]
    )
    print(f"Bot: {response}\n")

    # Update conversation state
    conversation_state["context"].extend([
        {"role": "user", "content": "Hi, I'm back. Any update on my missing package?"},
        {"role": "assistant", "content": response}
    ])

    # Turn 4: Resolution
    print("Customer: Great, thanks for resolving this!")

    # Mark ticket as resolved (non-LLM operation)
    resolved = bot.mark_ticket_resolved(conversation_state["ticket_id"])
    print(f"[System: Ticket {conversation_state['ticket_id']} marked as resolved: {resolved}]")

    # Final response
    response = bot.generate_response(
        profile,
        "Great, thanks for resolving this!",
        conversation_state["context"]
    )
    print(f"Bot: {response}")

    conversation_state["status"] = "resolved"
    print(f"\n[Thread {thread_ctx.thread_id} completed with {len(conversation_state['context'])//2} total turns across 3 sessions]")
```

## 🚀 Looking for more examples?
- Check out the [Quickstart guide](https://weave-docs.wandb.ai/quickstart).
- Learn more about [advanced tracing topics](https://weave-docs.wandb.ai/tutorial-tracing_2).
- Learn more about [tracing in Weave](https://weave-docs.wandb.ai/guides/tracking/tracing)
- Learn more about the [inference service](https://weave-docs.wandb.ai/guides/integrations/inference).

