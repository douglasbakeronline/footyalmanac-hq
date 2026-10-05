# Footyalmanac HQ - Development Guide

## Architecture Overview

Footyalmanac HQ is an AI agent office that runs a sports prediction business. The system consists of:

### Core Components

1. **Office Engine** (`scripts/office.py`)
   - Orchestrates all agent activities
   - Gathers data from the main footyalmanac repo
   - Generates stand-ups, reports, and water cooler chats
   - Runs on UK timezone schedule via GitHub Actions

2. **Organization Management** (`scripts/org.py`)
   - Luke's hiring desk - automatically hires specialists
   - Manages up to 6 hired agents with specific KPIs
   - Creates new departments as needed
   - Zero AI tokens - pure rule-based logic

3. **CEO Agent** (`scripts/ceo.py`) ⭐ NEW
   - Elena provides strategic leadership
   - 1-2-1 conversations with Douglas
   - Daily business oversight reports
   - Answers questions about performance and strategy

4. **Markets & Groupings** (`scripts/markets.py`)
   - Oscar: Prices legs with bookmaker odds
   - Jade: Creates accumulator groups (Steady/Balanced/Stretch)
   - Manages odds from football-data.co.uk and the-odds-api

5. **Saturday Picks** (`scripts/saturday.py`)
   - Weekly preview (Friday), final (Saturday), review (Sunday)
   - Posted as GitHub issues

6. **Slip Management** (`scripts/slip.py`)
   - Track Douglas's personal betting slips
   - Auto-settle from graded results

### Agent Roster

**Core Team (11 agents):**
- Chief (Luke): Chief of Staff, overall strategy
- Scout (Maya): Fixture gathering
- Quality (Amir): Data validation
- Source (Nia): API reliability
- Ratings (Ethan): Match probability engine
- Experiment (Mia): A/B testing and tuning
- Sports (Carlos): Multi-sport coverage
- Auditor (Susie): Results grading
- Calib (Ravi): Calibration monitoring
- Curator (Ivy): Daily List curation
- Engineer (Allan): Build pipeline

**CEO:**
- Elena: Strategic oversight and 1-2-1 chats

**Expansion Wing (up to 6 hired specialists):**
- Automatically hired by Luke based on business needs
- Examples: League specialists, Draw Risk Analyst, Reliability Engineer
- Each gets one KPI and reports at stand-ups

## Data Flow

```
GitHub Actions Schedule (UK time)
    ↓
office.py gathers data from footyalmanac repo
    ↓
Agents generate stand-ups, reports, chats
    ↓
org.py reviews hiring needs
    ↓
Data written to docs/data/*.json
    ↓
Git commit & push
    ↓
docs/index.html reads JSON and renders 3D office
```

## Development Setup

### Prerequisites

```bash
python3 (3.10+)
gh CLI (for GitHub API access)
git
```

### Local Testing

```bash
# Clone the repo
git clone https://github.com/douglasbakeronline/footyalmanac-hq.git
cd footyalmanac-hq

# Run tests
python3 tests/test_office.py

# Test CEO chat locally
python3 scripts/ceo.py --chat

# Generate a standup locally (requires gh auth)
python3 scripts/office.py --slot standup

# Preview the office UI
python3 -m http.server -d docs 8080
# Visit http://localhost:8080
```

### Running Individual Components

```bash
# CEO commands
python3 scripts/ceo.py --message "What's our accuracy this week?"
python3 scripts/ceo.py --daily-report
python3 scripts/ceo.py --chat  # Interactive mode

# Office commands
python3 scripts/office.py --slot standup
python3 scripts/office.py --slot report --period week
python3 scripts/office.py --slot work

# Saturday picks
python3 scripts/saturday.py preview
python3 scripts/saturday.py final
python3 scripts/saturday.py review

# Markets
python3 scripts/markets.py refresh
python3 scripts/markets.py grade

# Slip management
python3 scripts/slip.py add --text "Arsenal to win, Liverpool to win"
python3 scripts/slip.py grade
```

## Testing

### Unit Tests

```bash
# Run all tests
python3 tests/test_office.py

# Run specific test class
python3 tests/test_office.py TestOrgFunctions

# Run specific test
python3 tests/test_office.py TestOrgFunctions.test_candidates_weak_league
```

### Test Coverage

Current coverage:
- ✅ Org hiring logic
- ✅ Metric calculations
- ✅ CEO profile and context
- ✅ Data structure validation
- 🔄 Office data gathering (mocked)
- 🔄 Markets pricing (integration test needed)

## Data Files

All agent-generated data lives in `docs/data/`:

| File | Purpose | Updated By |
|------|---------|------------|
| `standups.json` | All stand-up meetings | office.py |
| `reports.json` | Daily/weekly playbacks | office.py |
| `chats.json` | Water cooler conversations | office.py |
| `events.json` | Office events timeline | office.py |
| `org.json` | Hires, departments, hiring log | org.py |
| `rhythm.json` | Current day's schedule | office.py |
| `latest.json` | Most recent business snapshot | office.py |
| `picks.json` | Today's predictions | office.py |
| `groups.json` | Accumulator groups | markets.py |
| `saturday.json` | Saturday picks state | saturday.py |
| `slips.json` | Douglas's betting slips | slip.py |
| `ceo_conversations.json` | CEO chat history | ceo.py ⭐ |
| `ceo_reports.json` | CEO daily reports | ceo.py ⭐ |

## Adding New Features

### Adding a New Agent

1. Define the agent in `office.py` RHYTHM or add to agent roster
2. Add their logic in `_build()` function
3. Give them stand-up lines (yesterday/today/blockers)
4. Optionally: add objectives they own
5. Add their sprite/avatar in the 3D office UI

### Adding a New KPI Type

1. Add KPI definition in `org.py` candidates()
2. Implement metric calculation in `org.py` metric()
3. Add "next steps" text in `org.py` NEXT dictionary
4. Add objective label in `org.py` lines_and_objectives()

### Adding a New Rhythm Slot

1. Add entry to RHYTHM list in `office.py`
2. Add cron schedule in `.github/workflows/office.yml`
3. Handle the slot in office.py main logic
4. Test with `--slot your_new_slot`

## Performance Optimization

### Current Bottlenecks

1. **GitHub API calls**: Each run makes ~10 API calls
   - Cached with CACHE dict and 5-minute TTL
   - Consider: Redis/file cache for local dev

2. **Data gathering**: Sequential API calls
   - Could parallelize with threading/asyncio

3. **JSON file I/O**: Atomic writes with .tmp files
   - Good for reliability, minor overhead

### Optimization Tips

```python
# Use the cache for repeated runs
d = gather()  # Uses cache if recent

# Batch GitHub API calls
# Current: Multiple serial gh api calls
# Better: Use GraphQL for one round-trip

# Minimize data written
# Only write changed data files
```

## Debugging

### Common Issues

**Issue**: `gh: command not found`
- Install: `brew install gh` or `apt install gh`
- Auth: `gh auth login`

**Issue**: Standup data incomplete
- Office falls back to cached data automatically
- Check GitHub API rate limits

**Issue**: Tests fail on metric calculation
- Ensure test data matches expected structure
- Check org.py for recent KPI changes

### Debug Mode

Add debug prints:
```python
print(f"DEBUG: {variable}", flush=True)
```

Check GitHub Actions logs for any scheduled run.

## Contributing

1. Test locally first
2. Run unit tests: `python3 tests/test_office.py`
3. Check data file integrity
4. Create a PR with clear description
5. Tag relevant agents in PR description (@chief @engineer)

## API Reference

### Office.py Functions

- `gather()`: Fetch all data from footyalmanac repo
- `build_standup(trigger)`: Generate standup meeting
- `build_report(period)`: Generate playback report
- `water_cooler()`: Generate agent conversations

### Org.py Functions

- `candidates(data, org)`: List hiring candidates
- `review(data, org, today, history)`: Hire one specialist
- `metric(hire, data)`: Calculate KPI for a hire
- `lines_and_objectives(data, org)`: Generate standup content

### CEO.py Functions ⭐

- `handle_message(message, issue)`: Process CEO chat
- `build_prompt(message, context)`: Build AI prompt with context
- `generate_daily_report()`: CEO's daily overview
- `load_context()`: Load current business state

## Roadmap

- [x] CEO agent with 1-2-1 chat
- [x] Unit tests for core functions
- [x] Development documentation
- [ ] Integration tests for markets
- [ ] Performance benchmarking
- [ ] CEO integration with LLM API
- [ ] Real-time chat interface
- [ ] Agent personality customization
- [ ] Historical trend analysis
- [ ] Predictive hiring suggestions
