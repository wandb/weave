---
marp: true
# theme: gaia
# class: 
#   - lead
#   - invert
---

# Vibe Coding
_Prompted by Tim Sweeney_
_Written by Claude_
_Images by GPT_

<!-- IMG_GEN: {"prompt": "Modern developer sitting at a desk with holographic AI assistant, coding on multiple screens, futuristic tech workspace, blue and purple color scheme"} -->
![bg right:50%](images/hero-image.png)

<!-- 
Presenter Notes:
- Welcome everyone, introduce yourself
- Set expectation: this is about sharing practical experience
- Emphasize that this is preparation for when they get authorization
- Mention the mix of content and demos

Outline:

1. What is Vibe Coding? (5 mins)
   * Definition & Philosophy
   * Why it's different from traditional coding
   * The mindset shift

2. Impact - Will I Still Have a Job? (8 mins)
   * The abstraction layer progression
   * What changes, what stays the same
   * New opportunities and responsibilities

3. Common Tools Landscape (10 mins + demos)
    * Co-Pilot IDEs
        * Cursor
        * Windsurf
        * Zed
        * VSCode (GH Copilot)
    * Task-Oriented Tools
        * Claude Code
        * Cursor Background Agents
        * Devin
    * CI / Bug Detection Tools
        * CoderRabbit
        * Cursor BugBot
    * Terminals
        * Warp

4. Essential Workflow Elements (15 mins + workflow demos):
    * Shell Commands
    * Typeahead
    * Spot Requests
    * Ask Questions
    * Agent Mode

5. Advanced Tips and Tricks (10 mins + tips demos)
    * AGENTS.md (or equivalent)
    * PR.md
    * Context Summarization
    * Templating
    * Notes
    * PR Summarization
    * Using Staging & Commits as Checkpoints

6. Building your AI "Team" (10 mins)
    * Service Provider Options:
        * Anthropic Claude Family
        * OpenAI GPT Family
        * Google Gemini Family
        * X.ai Grok Family
    * Self Hosted Options:
        * Deepseek Family
        * Meta Llama Family

7. Q&A (10 mins)

--- BONUS CONTENT (if time permits) ---

8. Understanding Tools & MCP
9. Uncommon Use Cases
    * Notebooks
    * Markdown
    * Presentations
    * Diagrams
 -->

---

## What is Vibe Coding?

<!-- IMG_GEN: {"prompt": "Two developers collaborating - one human and one AI robot, sitting side by side at computers, friendly partnership, modern office setting, warm lighting"} -->
![bg right:50%](images/ai-pair-programming.png)

<!-- 
Presenter Notes:
- Start with relatable analogy - like having a brilliant colleague who never gets tired
- Emphasize the "pair programming" aspect - it's collaborative, not replacement
- Be clear this isn't just autocomplete or code generation
-->

---

### What is Vibe Coding? 🤔

**Vibe Coding** = Coding with an AI "copilot"

**Traditional:** Write → Test → Debug → Repeat  
**Vibe Coding:** Think → Discuss → Code → Iterate

**Key Shifts:**
* From "What code?" → "What goal?"
* From isolated solving → collaborative reasoning  
* From perfect drafts → rapid iteration
* From Stack Overflow → asking your AI pair

> *"Like having a senior dev who never gets tired, never judges, and has read every doc ever written."*

<!-- IMG_GEN: {"prompt": "Split-screen artistic comparison: left side shows isolated programmer in dark room with single screen, right side shows collaborative workspace with AI hologram, bright and connected, cyberpunk aesthetic"} -->
![bg right:35% 95%](images/workflow-comparison.png)

<!-- 
Presenter Notes:
- Emphasize the conversational aspect - this is about reasoning together, not just generating code
- You maintain control and decision-making authority
- Traditional coding is more isolated and sequential, vibe coding is collaborative and iterative
- Context sharing is KEY - AI remembers what you're working on
- This is the most important concept - the mindset shift is everything
- Moving from implementation details to high-level problem solving
-->

---

## Impact - Will I Still Have a Job?

<!-- IMG_GEN: {"prompt": "Layered pyramid diagram showing evolution of programming - assembly code at bottom, high-level languages in middle, AI assistance at top, upward arrows showing progression", "size": "1792x1024"} -->
![bg right:50%](images/abstraction-layers.png)

<!-- 
Presenter Notes:
- Address the elephant in the room head-on
- This is likely their biggest concern
- Use historical examples they'll relate to
- Be confident and reassuring but realistic
-->

---

### We've Been Here Before 📈

**Abstraction Evolution:**
* Assembly → High-Level Languages  
* Raw SQL → ORMs  
* Manual Memory → Garbage Collection

**Now:** Manual Coding → AI-Assisted Coding

**What Changes:** Speed, focus (syntax→architecture), AI debugging  
**What Stays Critical:** System design, code review, business requirements

<!-- IMG_GEN: {"prompt": "Abstract data visualization: skills as interconnected nodes, some nodes fading (manual coding) while others grow brighter (architecture, creative thinking), network effect visualization with pulsing energy, clean modern infographic style"} -->
![bg right:35% 75%](images/skills-evolution.png)

<!-- 
Presenter Notes:
- Each transition was feared but ultimately made us more productive
- We didn't stop being programmers when we moved from assembly to Python
- Same pattern applies here - Ask: "Did anyone become unemployed when we got IDEs with autocomplete?"
- Emphasize that the HARD parts of engineering remain
- AI doesn't understand business context like you do
- AI doesn't make architectural decisions or understand trade-offs in your specific domain
-->

---

### Your New Superpowers

**With AI:** Multiple, simultaneous workstreams

**You become:**
* 🎨 **Creative Director** - defining what to build
* 🏗️ **System Architect** - designing how it fits together  
* 🔧 **Technical Product Manager** - prioritizing and coordinating
* 🎯 **Quality Gatekeeper** - ensuring standards and best practices

**The demand for great engineers increases, not decreases**

<!-- IMG_GEN: {"prompt": "Epic superhero-style illustration: developer in flowing cape standing atop multiple floating project platforms, AI assistants as glowing orbs orbiting around them, dramatic lighting with city skyline background, comic book art style with dynamic action lines"} -->
![bg right:25% 90%](images/superpowers.png)

<!-- 
Presenter Notes:
- This is the key insight - you become MORE valuable, not less
- You can take on bigger, more complex challenges
- Companies will need fewer junior developers but more senior/staff engineers
- The work becomes more strategic and less tactical
-->

---

## Common Tools Landscape

<!-- IMG_GEN: {"prompt": "Futuristic tool workshop floating in space: various AI coding tools as crystalline floating workstations connected by energy bridges, holographic interfaces everywhere, space station aesthetic with cosmic background", "size": "1792x1024"} -->
![bg right:55%](images/tools-landscape.png)

<!-- 
Presenter Notes:
- Now we get into the practical stuff
- This is where you can show actual tools
- Have your demo environment ready
- Focus on 2-3 tools max in the demo
-->

---

### Co-Pilot IDEs 🖥️

**Cursor** - Multi-file editing, background agents  
**Windsurf** - Autonomous code changes across files  
**Zed** - Real-time collaboration, lightning-fast  
**VSCode + Copilot** - Most widely adopted

They all are starting to converge!

![bg right:35% 80%](images/ide-comparison.png)

<!-- 
Presenter Notes:
- Demo Cursor if possible - show the multi-file editing
- Mention that most people start with VSCode + Copilot
- Cursor is where the power users end up
- Show the different UX approaches
-->

--- 

### Cursor Demo

**Live Demo Agenda:**
* Shell Command (Shell cmd-k)
* Type-Ahead completion
* Editor Spot Fix (cmd-K)
* Codebase Questions (Ask mode)
* Feature Implementation (Agent Mode) 
* Context adding (URLs, files, etc.)
* PR generation

---

### Task-Oriented Tools 🎯

**Claude Code** - Deep reasoning, CLI-based  
**Cursor Background Agents** - Autonomous workers, cloud-based
**OpenAI Codex** - Code generation API, powers many tools
**Devin** - Full-stack development & deployment (integrates with Slack)

<!-- IMG_GEN: {"prompt": "Specialist AI entities as mystical beings: Claude as wise oracle with ancient scrolls of code, Cursor agents as busy worker sprites, Devin as powerful wizard orchestrating entire projects, fantasy art meets cyberpunk"} -->
![bg right:35% 85%](images/specialized-tools.png)

<!-- 
Presenter Notes:
- These are more advanced tools
- Show Claude Code if you have access
- Devin is still in early access but worth mentioning
- Background agents are where things get really powerful
-->

--- 

### OpenAI Codex Demo
* Implement a specific feature end-to-end

**Demo URL:** https://chatgpt.com/codex

---

### CI/Bug Detection Tools 🔍

**CodeRabbit** - Automated PR reviews & suggestions  
**Cursor BugBot** - Intelligent debugging & root cause analysis

<!-- IMG_GEN: {"prompt": "Security checkpoint scene: CodeRabbit as detective with magnifying glass examining code scrolls, BugBot as friendly robot medic healing broken code with rainbow laser beams, whimsical cartoon style with bright colors"} -->
![bg left:35% 75%](images/ci-tools.png)

<!-- 
Presenter Notes:
- These integrate into your existing workflow
- Show a CodeRabbit review if possible
- Emphasize that these enhance, not replace, human review
-->

---

### CodeRabbit Demo

**Live Example:** AI-powered PR review in action

**Demo URL:** https://github.com/wandb/weave/pull/3653

![bg right:50%](images/coderrabbit_1.png)

---

### AI-Enhanced Terminals ⚡

**Warp** - Natural language → shell commands, smart suggestions & AI assistant

<!-- IMG_GEN: {"prompt": "Magical command portal: terminal window as ancient stone archway with mystical runes, natural language floating in as glowing spells, transforming into command line incantations, magical realism art style", "size": "1792x1024"} -->
![bg right:55% 100%](images/warp.png)

<!-- 
Presenter Notes:
- Demo Warp if possible - show the natural language to command translation
- This is often the easiest entry point for people
- Show complex commands being generated from simple requests
-->

---

## Essential Workflow Elements

<!-- IMG_GEN: {"prompt": "Dynamic workflow symphony: five different work patterns as musical instruments in an orchestra, each element creating visual music notes in the air, conductor coordinating the harmony, art deco poster style", "size": "1792x1024"} -->
![bg left:50%](images/workflow-elements.png)

<!-- 
Presenter Notes:
- This is the meat of the presentation
- These are the patterns that separate beginners from experts
- Try to demo each workflow element
-->

---

### Shell Commands 🖥️

**Pattern:** Natural language → Shell command

* "Find all Python files modified in the last week"
* "Show me memory usage by process"  
* "Deploy this to staging with rollback capability"

<!-- IMG_GEN: {"prompt": "Translation machine concept: casual human speech bubbles on one side, complex shell commands emerging on the other, connected by swirling transformation gears and clockwork mechanisms, steampunk meets modern UI design"} -->
![bg right:35% 80%](images/shell-commands.png)

<!-- 
Presenter Notes:
- Demo this live if possible
- Show how complex commands are generated from simple requests
- Emphasize the time savings
-->

---

### Typeahead ⚡

**Beyond autocomplete:**
* Context-aware across multiple files  
* Learns your coding patterns & style
* Suggests entire function implementations
* Reduces cognitive load, speeds up boilerplate

<!-- IMG_GEN: {"prompt": "Intelligent completion visualization: developer typing with ghostly helpful hands appearing to complete the code, multiple timeline suggestions flowing like river branches, ethereal and flowing, impressionist painting style with digital elements"} -->
![bg left:35% 85%](images/typeahead.png)

<!-- 
Presenter Notes:
- Show how different this is from traditional autocomplete
- Demo multi-file context awareness
- Show how it learns your patterns
-->

---

### Spot Requests 🎯

**Use cases:**
* "Fix this bug" (highlight problematic code)
* "Add error handling to this function"  
* "Convert this to use async/await"
* "Add type hints to this module"

<!-- IMG_GEN: {"prompt": "Precision targeting concept: developer with laser-guided crosshairs selecting specific code sections, AI responding with surgical precision tools, medical operation meets sniper precision, clean vector illustration style"} -->
![bg right:35%](images/spot-requests.png)

<!-- 
Presenter Notes:
- This is about precision requests
- Show how you can highlight code and ask for specific changes
- Emphasize the speed of iteration
-->

---

### Ask Questions ❓

**Types of questions:**
* **Explanatory:** "What does this regex do?"
* **Architectural:** "Should I use a factory pattern here?"
* **Debugging:** "Why isn't this working as expected?"
* **Best practices:** "Is there a more Pythonic way to do this?"

<!-- IMG_GEN: {"prompt": "Socratic dialogue scene: developer and AI as ancient philosophers in a modern setting, thought bubbles containing code patterns and architectural diagrams, wisdom-sharing atmosphere, renaissance art style with modern coding elements"} -->
![bg left:35% 85%](images/ask-questions.png)

<!-- 
Presenter Notes:
- This is where the "pair programming" aspect really shines
- Show a conversation flow if possible
- Emphasize the learning aspect
-->

---

### Agent Mode 🤖

**When to use:**
* Large refactoring across multiple files
* Implementing new features end-to-end  
* Migrating between frameworks/libraries
* Setting up complex project structures

**AI handles:** Planning, multi-file changes, consistency, testing  
**Your role:** Guide, review, approve

<!-- IMG_GEN: {"prompt": "AI autopilot taking control: futuristic spacecraft cockpit with AI avatar piloting while developer sits back as mission commander, multiple screens showing autonomous code generation across files, space opera cinematic style", "size": "1792x1024"} -->
![bg right:35%](images/agent-mode.png)

<!-- 
Presenter Notes:
- This is the most advanced workflow
- Show an agent working across multiple files if possible
- Emphasize that YOU are still in control
-->

---

### Notebooks 📓
*AI-powered data science workflows*

**What AI can do:**
* Generate analysis code from natural language
* Explain complex data science concepts  
* Debug statistical models & create visualizations

**Example prompts:**
* "Create a correlation plot between X and Y"
* "Explain why this model is overfitting"
* "Clean this messy dataset"

<!-- IMG_GEN: {"prompt": "Data scientist working with AI in a modern jupyter notebook interface, multiple data visualizations and charts floating as holograms around the screen, AI assistant analyzing scatter plots and regression models, clean tech aesthetic with blue and green data streams"} -->
![bg right:40% 100%](images/notebooks.png)

<!-- 
Presenter Notes:
- Great for data scientists in the audience
- Show Jupyter + AI if possible
- Emphasize the analysis capabilities
-->

---

### Hex Demo

**Live Example:** AI-assisted data analysis and visualization

**Demo URL:** https://app.hex.tech/8ecc814e-8a34-46e1-b465-0c38bd16e93e/hex/0196da17-fbc7-788f-b371-4b0664107ffb/draft/logic

---

## Advanced Tips and Tricks

<!-- IMG_GEN: {"prompt": "Master craftsman's workshop: ancient scrolls transforming into digital interfaces, traditional tools morphing into AI assistants, blend of medieval craftsmanship and futuristic technology, golden hour lighting with mystical atmosphere", "size": "1792x1024"} -->
![bg left:50%](images/advanced-tips.png)

<!-- 
Presenter Notes:
- These are the "pro tips" that separate casual users from power users
- Focus on the most impactful ones
- Demo AGENTS.md setup if possible
-->

---

### AGENTS.md (or equivalent) 📋
*Your AI's instruction manual for your project*


```markdown
# Project Context
- Architecture overview & key patterns
- Coding standards & style guide

# AI Instructions  
- "Always use TypeScript strict mode"
- "Include comprehensive error handling"
```

**Benefits:** Consistent AI behavior, faster feature work, automatic quality

**Examples:**
* [Cursor Rules](https://github.com/tssweeney/agentikit/blob/main/.cursor/rules/general-project-rules.mdc)
* [AGENTS.md](https://github.com/wandb/weave/blob/master/AGENTS.md)

<!-- IMG_GEN: {"prompt": "Living instruction manual: AGENTS.md file as glowing tome with pages that float and rearrange themselves, AI reading and memorizing the patterns, library of knowledge with floating texts, magical realism meets technical documentation"} -->
![bg right:30% 75%](images/agents-md.png)

<!-- 
Presenter Notes:
- This is HUGE for consistency
- Show an example AGENTS.md file
- Explain how this saves time in every session
-->

---

### PRD.md 📝
*Useful for having a shared, collaborative state between you and the agent*

**Template structure:**
```markdown
## What changed
<!-- AI fills automatically -->

## Why this change  
<!-- AI explains reasoning -->

## Testing & Review notes
<!-- AI lists what to test & review -->
```

<!-- 
Presenter Notes:
- Show how AI can generate comprehensive PR descriptions
- This improves code review quality
- Saves significant time
-->

---

### Context Summarization 🧠
*Keeping AI focused on what matters*

**Key techniques:**
* **File summaries:** AI creates 2-3 line summaries of complex files
* **Session context:** Regularly summarize current work
* **Decision logs:** Track architectural decisions & rationale

**Magic phrase:** "Summarize our conversation and current state"

<!-- IMG_GEN: {"prompt": "Abstract concept of information synthesis: swirling constellation of code fragments, conversation bubbles, and file icons being compressed into a single glowing summary orb, AI brain organizing scattered information into coherent structure, minimalist infographic style with purple and teal colors"} -->
![bg right:30% 80%](images/context-summary.png)

<!-- 
Presenter Notes:
- Context management is crucial for long sessions
- Show how summarization keeps AI focused
- This prevents AI from "forgetting" what you're working on
-->

---

### PR Summarization 🔄
*AI writes your commit messages and PR descriptions*

**The process:**
1. Make changes with AI assistance → AI reviews diff
2. AI generates meaningful commit messages  
3. AI creates comprehensive PR descriptions
4. AI suggests review criteria

**Result:** Better docs, easier reviews, improved team communication

<!-- IMG_GEN: {"prompt": "Automated PR workflow visualization: AI assistant examining code diffs on multiple screens, generating commit messages and PR descriptions, conveyor belt of documents flowing from code changes to polished documentation, industrial automation meets software development, clean vector style"} -->
![bg right:40% 100%](images/git_diff.png)

<!-- 
Presenter Notes:
- Show the full workflow if possible
- Emphasize the quality improvement
- This helps with team collaboration
-->

---

### Using Staging & Commits as Checkpoints 🎯
*Version control as collaboration tool*

**The pattern:**
1. **Explore:** Let AI try different approaches  
2. **Checkpoint:** Stage incremental progress
3. **Commit:** Commit working solutions

<!-- IMG_GEN: {"prompt": "Git branching strategy as a tree of possibilities: multiple code branches growing from a central trunk, AI gardener tending to different experimental approaches, some branches merging back together, organic growth meets version control, botanical illustration style with tech elements"} -->
![bg right:30% 80%](images/git-workflow.png)

<!-- 
Presenter Notes:
- This is advanced version control with AI
- Show how AI can compare different approaches
- This enables rapid experimentation
-->

---

## Building your AI "Team"

<!-- IMG_GEN: {"prompt": "AI dream team assembly: diverse AI personalities as superhero squad, each with unique powers and visual design representing their capabilities, team lineup poster style with dramatic lighting and heroic poses", "size": "1792x1024"} -->
![bg right:55%](images/ai-team.png)

<!-- 
Presenter Notes:
- This is about strategy - choosing the right tools
- Emphasize that different models have different strengths
- Multi-model approach is often best
-->

---

### Service Provider Options ☁️

**Anthropic Claude Family** - Best for complex reasoning & architecture
 * Can be a bit of an over-achiever, but accepted as the best

**OpenAI GPT Family** - Well-rounded, wide knowledge base  
 * Can be a bit of a minimalist, but has the broadest knowledge

**Google Gemini Family** - Large context window, multi-modal  
**X.ai Grok Family** - Real-time information access

![bg right:25% 80%](images/service-providers.png)

<!-- 
Presenter Notes:
- Give brief overview of each family's strengths
- Mention pricing considerations
- Claude is great for code, GPT for general tasks, Gemini for large context
-->

---

### Self-Hosted Options 🏠

**DeepSeek Family** - Specialized for code generation 
**Meta Llama Family** - General-purpose with good coding abilities

**Benefits:** Privacy, cost control, offline capability

Can host on a private cloud or locally using Ollama.

<!-- IMG_GEN: {"prompt": "Private server fortress: secure data center with glowing AI models running locally, shields and locks protecting sensitive code, developer working with locally hosted AI models behind corporate firewall, cybersecurity meets AI infrastructure, fortress architecture with tech elements"} -->
![bg right:30% 80%](images/self-hosted.png)

<!-- 
Presenter Notes:
- Important for companies with strict data policies
- Mention the trade-offs: control vs. convenience
- Self-hosted requires more technical expertise
-->

---

### DeepSeek Local Demo

Many options here.

1. Get a model

```
> ollama run deepseek-r1:7b
```

2. Connect it: https://zed.dev/docs/ai/configuration#ollama

---

### Building Your Toolkit Strategy 🛠️

**The Multi-Model Approach:**
1. **Primary:** Main model for most work (GPT o3)
2. **Specialist:** Code-specific for complex algorithms (Claude 4.0 Sonnet)  
3. **Speed:** Fast model for simple tasks (GPT-4o Mini)

**Consider:** Cost vs. Capability, Privacy, Context window, Speed

<!-- IMG_GEN: {"prompt": "Strategic decision matrix visualization: multi-dimensional chess board with AI models as different chess pieces, each piece showing different strengths (speed, capability, cost, privacy), strategic mind evaluating trade-offs, tactical planning meets AI selection, 3D chess aesthetic with floating decision criteria"} -->
![bg right:30% 80%](images/strategy-matrix.png)

<!-- 
Presenter Notes:
- Emphasize that one size doesn't fit all
- Different models for different use cases
- Budget considerations are important
-->

---

## Q&A

<!-- 
Presenter Notes:
- Encourage questions throughout
- These are common questions you'll get
- Be prepared with specific examples
-->

### Common Questions:

**"How do I get started?"**
* Pick one AI-powered IDE (recommend Cursor for beginners)
* Start with simple requests and build confidence
* Practice the core workflows we covered

**"What about code quality?"**
* AI doesn't replace code review - you are ultimately responsible
* Use AI to catch common issues early
* Still need human judgment for architecture decisions

---

## Thank You! 🚀

**Next Steps:**
1. **Try Cursor** - Start with the most beginner-friendly AI IDE
2. **Practice workflows** - Focus on shell commands & spot requests  
3. **Build confidence** - Start with simple tasks, grow complexity

### Questions?

<!-- IMG_GEN: {"prompt": "Celebration of new coding era: developer and AI raising hands in victory together, confetti of code symbols falling like celebration, sunrise over a futuristic coding city, inspirational poster art style with vibrant colors"} -->
![bg right:50%](images/thank-you.png)

<!-- 
Presenter Notes:
- Thank the audience
- Encourage them to start experimenting
- Offer to help with questions later
- Emphasize that the best way to learn is by doing
-->

---

## Bonus Content
*If time permits*

![bg right:50%](images/bonus.png)

<!-- 
Presenter Notes:
- Only cover if you have extra time
- These are advanced topics
- Pick the most relevant for your audience
-->

---

### Understanding Tools & MCP 🔧
*The future of AI tool integration*

**Model Context Protocol (MCP)** - Standard way for AI to use external tools

**What it enables:**
* AI directly queries databases  
* AI reads/writes files across your system
* AI interacts with external APIs

**Why it matters:**
* Makes AI significantly more capable
* Standardized tool ecosystem emerging

![bg right:30% 80%](images/mcp-diagram.png)

<!-- 
Presenter Notes:
- This is cutting-edge stuff
- Show MCP in action if possible
- This is where AI coding is heading
-->

---

### Uncommon Use Cases
*AI coding beyond traditional software development*

![bg right:50%](images/uncommon-cases.png)

<!-- 
Presenter Notes:
- These show the versatility of AI coding
- Pick examples relevant to your audience
- Show how AI coding applies beyond just writing code
-->


---

### Markdown 📝
*AI as your writing and documentation partner*

**What AI creates:**
* Technical documentation & README files
* API documentation from code comments

**Example prompts:**
* "Convert these function signatures to API docs"
* "Write a README for this project"
* "Explain this algorithm in simple terms"

<!-- 
Presenter Notes:
- Documentation is often neglected - AI makes it easier
- Show documentation generation if possible
- This improves team communication
-->

---

### Presentations 🎯
*AI helps create and structure presentations*

**AI capabilities:**
* Generate slide content from bullet points
* Create presentation outlines & suggest visuals
* Format content for different audiences

**Meta moment:** This presentation was built with AI assistance!

![bg right:50%](images/me_building_this_deck.png)

<!-- 
Presenter Notes:
- Meta moment - this presentation is an example
- Show how AI can help with non-coding tasks
- Useful for technical talks and documentation
-->

---

### Diagrams 📊
*AI creates visual system representations*

**What AI generates:**
* Architecture & database diagrams
* Flow charts & UML diagrams  
* Network topology & sequence diagrams

**Format options:**
* Mermaid (widely supported)
* PlantUML & ASCII art
* SVG code generation

![bg right:50%](images/llm_diagram.png)

<!-- 
Presenter Notes:
- Visual communication is crucial in engineering
- Show diagram generation if possible
- This helps with system design and communication
-->
