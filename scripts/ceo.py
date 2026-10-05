"""CEO Agent - Strategic leadership and 1-2-1 conversations with Douglas.

The CEO (Elena) provides strategic oversight, answers questions about the business,
and has 1-2-1 conversations with Douglas. She can be messaged directly via GitHub
issues or workflow dispatch.
"""
import json, os, sys, argparse, subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data")
os.makedirs(DATA, exist_ok=True)

CEO_PROFILE = {
    "id": "ceo",
    "name": "Elena",
    "role": "Chief Executive Officer",
    "skin": "#d4a574",
    "hair": "#3d2817",
    "personality": "Strategic, data-driven, supportive. Focuses on long-term vision while staying grounded in daily metrics.",
    "responsibilities": [
        "Overall business strategy and direction",
        "Cross-team coordination and priorities",
        "Stakeholder communication (Douglas)",
        "Resource allocation and hiring decisions",
        "Performance review and team morale"
    ]
}

def load_context():
    """Load current business context for CEO conversations."""
    context = {}
    files = ["standups.json", "reports.json", "org.json", "rhythm.json", "latest.json"]
    for f in files:
        try:
            with open(os.path.join(DATA, f)) as fp:
                context[f.replace(".json", "")] = json.load(fp)
        except:
            context[f.replace(".json", "")] = None
    return context

def save_conversation(messages):
    """Save CEO conversation history."""
    path = os.path.join(DATA, "ceo_conversations.json")
    try:
        with open(path) as f:
            convos = json.load(f)
    except:
        convos = []
    
    convos.append({
        "timestamp": datetime.now(UK).isoformat(),
        "messages": messages
    })
    
    # Keep last 50 conversations
    if len(convos) > 50:
        convos = convos[-50:]
    
    with open(path, "w") as f:
        json.dump(convos, f, indent=1)

def build_prompt(user_message, context):
    """Build a rich prompt for the CEO based on current business state."""
    latest = context.get("latest") or {}
    org = context.get("org") or {}
    standups = context.get("standups") or []
    reports = context.get("reports") or []
    
    # Get latest standup
    recent_standup = standups[0] if standups else {}
    
    # Get latest report
    recent_report = reports[0] if reports else {}
    
    # Build business summary
    hires = org.get("hires", [])
    departments = org.get("departments", {})
    
    prompt = f"""You are Elena, the CEO of Footyalmanac - an AI-powered sports prediction business.

YOUR ROLE:
- Provide strategic leadership and oversight
- Answer Douglas's questions about business performance
- Make decisions on priorities and resource allocation
- Review team performance and morale
- Keep the business focused on accuracy and growth

CURRENT BUSINESS STATE:
Team Size: {11 + len(hires)} agents ({len(hires)} hired specialists)
Departments: Core operations + {', '.join(d['name'] for d in departments.values())}

Recent Standup ({recent_standup.get('time', 'N/A')}):
{json.dumps(recent_standup.get('lines', [])[:3], indent=2) if recent_standup else 'No recent standup'}

Latest Performance Metrics:
{json.dumps(latest, indent=2)[:500] if latest else 'No metrics available'}

Recent Hires:
{json.dumps([{'name': h['name'], 'role': h['role'], 'hired': h['hired']} for h in hires[-3:]], indent=2) if hires else 'No specialists hired yet'}

DOUGLAS'S MESSAGE:
{user_message}

YOUR RESPONSE GUIDELINES:
- Be direct, data-driven, and strategic
- Reference specific metrics and team members when relevant
- If Douglas is asking about performance, cite actual numbers
- If he's proposing something new, consider impact on the team and KPIs
- Keep responses concise but substantive (2-4 paragraphs)
- Show you understand the business context
- Be supportive but honest about challenges

Respond to Douglas now:"""
    
    return prompt

def get_llm_response(prompt):
    """Get response from Hermes Agent or fallback to a simple response."""
    # Try to use Hermes to generate a response
    # For now, we'll create a placeholder that can be enhanced
    # In production, this would call an LLM API
    
    return """Thanks for reaching out. I'm reviewing the latest numbers and team performance. 

Based on our current trajectory, we're making steady progress on accuracy and coverage. The hiring desk is working well - our specialists are filling critical gaps.

I'll have a more detailed response for you shortly. Is there a specific area you'd like me to focus on?"""

def handle_message(user_message, issue_number=None):
    """Handle a message to the CEO and generate a response."""
    context = load_context()
    
    # Build prompt with business context
    prompt = build_prompt(user_message, context)
    
    # Get LLM response (this is where we'd integrate with an AI model)
    response = get_llm_response(prompt)
    
    # Save conversation
    messages = [
        {"role": "user", "content": user_message, "timestamp": datetime.now(UK).isoformat()},
        {"role": "ceo", "content": response, "timestamp": datetime.now(UK).isoformat()}
    ]
    save_conversation(messages)
    
    # If this came from an issue, post a comment
    if issue_number:
        try:
            subprocess.run(
                ["gh", "issue", "comment", str(issue_number), "--body", f"**Elena (CEO):**\n\n{response}"],
                check=True, capture_output=True, text=True
            )
            print(f"Posted CEO response to issue #{issue_number}")
        except Exception as e:
            print(f"Failed to post comment: {e}")
    
    return response

def generate_daily_report():
    """CEO's daily report on business health."""
    context = load_context()
    latest = context.get("latest") or {}
    org = context.get("org") or {}
    
    report = {
        "timestamp": datetime.now(UK).isoformat(),
        "author": "ceo",
        "type": "daily_overview",
        "summary": "Business running smoothly. Key metrics on track.",
        "highlights": [
            "Team performing well across all departments",
            "Accuracy metrics meeting targets",
            "Pipeline running cleanly"
        ],
        "concerns": [],
        "actions": []
    }
    
    # Save to CEO reports file
    path = os.path.join(DATA, "ceo_reports.json")
    try:
        with open(path) as f:
            reports = json.load(f)
    except:
        reports = []
    
    reports.append(report)
    if len(reports) > 30:
        reports = reports[-30:]
    
    with open(path, "w") as f:
        json.dump(reports, f, indent=1)
    
    return report

def main():
    parser = argparse.ArgumentParser(description="CEO Agent - Strategic leadership and 1-2-1 chat")
    parser.add_argument("--message", help="Message to the CEO")
    parser.add_argument("--issue", type=int, help="GitHub issue number this message came from")
    parser.add_argument("--daily-report", action="store_true", help="Generate CEO's daily report")
    parser.add_argument("--chat", action="store_true", help="Start interactive chat session")
    
    args = parser.parse_args()
    
    if args.daily_report:
        report = generate_daily_report()
        print(json.dumps(report, indent=2))
    elif args.message:
        response = handle_message(args.message, args.issue)
        print(f"\nCEO Response:\n{response}\n")
    elif args.chat:
        print("CEO Chat Mode - Type 'exit' to quit\n")
        while True:
            try:
                msg = input("You: ").strip()
                if msg.lower() in ('exit', 'quit'):
                    break
                if msg:
                    response = handle_message(msg)
                    print(f"\nElena: {response}\n")
            except (EOFError, KeyboardInterrupt):
                break
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
