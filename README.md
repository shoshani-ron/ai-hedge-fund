# AI Hedge Fund

This is a proof of concept for an AI-powered hedge fund.  The goal of this project is to explore the use of AI to make trading decisions.  This project is for **educational** purposes only and is not intended for real trading or investment.

This system employs several agents working together:

1. Aswath Damodaran Agent - The Dean of Valuation, focuses on story, numbers, and disciplined valuation
2. Ben Graham Agent - The godfather of value investing, only buys hidden gems with a margin of safety
3. Bill Ackman Agent - An activist investor, takes bold positions and pushes for change
4. Cathie Wood Agent - The queen of growth investing, believes in the power of innovation and disruption
5. Charlie Munger Agent - Warren Buffett's partner, only buys wonderful businesses at fair prices
6. Michael Burry Agent - The Big Short contrarian who hunts for deep value
7. Mohnish Pabrai Agent - The Dhandho investor, who looks for doubles at low risk
8. Nassim Taleb Agent - The Black Swan risk analyst, focuses on tail risk, antifragility, and asymmetric payoffs
9. Peter Lynch Agent - Practical investor who seeks "ten-baggers" in everyday businesses
10. Phil Fisher Agent - Meticulous growth investor who uses deep "scuttlebutt" research 
11. Rakesh Jhunjhunwala Agent - The Big Bull of India
12. Stanley Druckenmiller Agent - Macro legend who hunts for asymmetric opportunities with growth potential
13. Warren Buffett Agent - The oracle of Omaha, seeks wonderful companies at a fair price
14. Valuation Agent - Calculates the intrinsic value of a stock and generates trading signals
15. Sentiment Agent - Analyzes market sentiment and generates trading signals
16. Fundamentals Agent - Analyzes fundamental data and generates trading signals
17. Technicals Agent - Analyzes technical indicators and generates trading signals
18. Risk Manager - Calculates risk metrics and sets position limits
19. Portfolio Manager - Makes final trading decisions and generates orders

<img width="1042" alt="Screenshot 2025-03-22 at 6 19 07 PM" src="https://github.com/user-attachments/assets/cbae3dcf-b571-490d-b0ad-3f0f035ac0d4" />

Note: the system does not actually make any trades.

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt)

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No investment advice or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
- Past performance does not indicate future results

By using this software, you agree to use it solely for learning purposes.

## Table of Contents
- [How to Install](#how-to-install)
- [How to Run](#how-to-run)
  - [⌨️ Command Line Interface](#️-command-line-interface)
  - [🖥️ Web Application](#️-web-application)
- [How to Contribute](#how-to-contribute)
- [Feature Requests](#feature-requests)
- [License](#license)

## How to Install

Before you can run the AI Hedge Fund, you'll need to install it. These steps are common to both the full-stack web application and command line interface.

### 1. Clone the Repository

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

### 2. Install Dependencies

1. Install Poetry (if not already installed):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies:
```bash
poetry install
```

### 3. Set up API keys (optional)

**No API keys are required** to run the hedge fund. Financial data is sourced from [yfinance](https://github.com/ranaroussi/yfinance) (free, no key needed), and LLMs can be run via the Claude CLI or Codex CLI using your existing subscription.

If you want to use other LLM providers, create a `.env` file:
```bash
cp .env.example .env
```

Then add whichever keys you need:
```bash
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
# ... see .env.example for all options
```

## How to Run

### ⌨️ Command Line Interface

You can run the AI Hedge Fund directly via terminal. This approach offers more granular control and is useful for automation, scripting, and integration purposes.

#### Quick Start (no API keys needed)

```bash
poetry run python src/main.py --tickers AAPL,MSFT,NVDA
```

When prompted to select a model, choose any **"via Claude CLI"** or **"via Codex CLI"** option at the top of the list — these use your existing [Claude Code](https://claude.ai/code) or [Codex CLI](https://github.com/openai/codex) subscription with no API key required.

#### Common flags

```bash
# Skip interactive pickers with flags
poetry run python src/main.py \
  --tickers AAPL,MSFT,NVDA \
  --analysts-all \
  --model claude-sonnet-4-6 \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --show-reasoning
```

| Flag | Description |
|------|-------------|
| `--tickers` | Comma-separated list of stock tickers |
| `--analysts-all` | Use all 19 analysts (skips interactive picker) |
| `--analysts` | Comma-separated list of specific analysts |
| `--model` | Model name to use (skips model picker) |
| `--start-date` | Start date in YYYY-MM-DD format |
| `--end-date` | End date in YYYY-MM-DD format |
| `--show-reasoning` | Print each agent's full reasoning |
| `--initial-cash` | Starting portfolio cash (default: 100,000) |
| `--ollama` | Use a local Ollama model |

You can optionally specify the start and end dates to make decisions over a specific time period.

```bash
poetry run python src/main.py --tickers AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
```

#### Run the Backtester
```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

**Example Output:**
<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />


Note: The `--ollama`, `--start-date`, and `--end-date` flags work for the backtester, as well!

### 🖥️ Web Application

The new way to run the AI Hedge Fund is through our web application that provides a user-friendly interface. This is recommended for users who prefer visual interfaces over command line tools.

Please see detailed instructions on how to install and run the web application [here](https://github.com/virattt/ai-hedge-fund/tree/main/app).

<img width="1721" alt="Screenshot 2025-06-28 at 6 41 03 PM" src="https://github.com/user-attachments/assets/b95ab696-c9f4-416c-9ad1-51feb1f5374b" />


## How to Contribute

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

**Important**: Please keep your pull requests small and focused.  This will make it easier to review and merge.

## Feature Requests

If you have a feature request, please open an [issue](https://github.com/virattt/ai-hedge-fund/issues) and make sure it is tagged with `enhancement`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
