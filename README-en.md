# Bedrock Tooluse Reporter

AI-powered Automatic Report Generation System  

## Overview

Bedrock Tooluse Reporter is an AI system that automatically generates detailed reports on given topics. It leverages multiple AI models to gather information, diversify perspectives, conduct data research, and write comprehensive reports.  

## Features

- **Context Understanding**: Comprehends user intent and collects basic information related to the topic
- **Multiple Perspectives**: Acquires diverse viewpoints through dialogue between two different AI models
- **Data Collection**: Gathers information using web searches, content retrieval, and image searches
- **Report Generation**: Creates structured markdown reports based on collected information
- **Visualization**: Enhances reports with Mermaid diagrams and web images
- **Multiple Formats**: Outputs reports in three formats: Markdown, HTML, and PDF

## System Architecture

The system consists of four main components:  

1. **ContextChecker**: Understands user intent and collects basic information about the topic
2. **PerspectiveExplorer**: Obtains multifaceted perspectives through dialogue between two different AI models
3. **DataSurveyor**: Collects necessary data based on the report framework
4. **ReportWriter**: Writes the report based on collected data and framework

### Prerequisites
- AWS environment
  - Region: `us-west-2`
  - Configured with AWS CLI (`aws configure`)
  - Permission to call Bedrock API
  - Supported models: claude-3.7-sonnet-v1, claude-3.5-sonnet-v2
- Python 3.10
- Brave Search API key

## Installation

1. Clone the repository  
   ```shell
   git clone https://github.com/aws-samples/bedrock-tooluse-reporter
   cd bedrock-tooluse-reporter
   ```
2. Create a `.brave` file in the root directory of the repository and save your Brave Search API key  
3. Create a virtual environment and install dependencies  
    ```shell
    python -m venv .venv
    source .venv/bin/activate  # For Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    ```

## Usage

```bash
# Basic usage
python main.py --prompt "Topic to research"
```

Example:  
```shell
python main.py --prompt "Report on luxury condo literature and social status signaling"
```

### Options
- `--prompt`, `-p`: Topic to research (required)
- `--mode`, `-m`: Processing mode (short/long). Short reduces processing iterations for faster results, long conducts more detailed research
- `--log-level`, `-l`: Specify log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- `--resume-file`, `-r`: Specify to resume from a previous conversation history

Example:  
```shell
python main.py --prompt "The future of AI and copyright" --mode long --log-level DEBUG
```

### Output
- Reports are generated in `./report/[timestamp]/`
- Each report directory contains:
    - `report.md`: Markdown format report
    - `report.html`: Styled HTML format report
    - `report.pdf`: Printable PDF format report
    - `images/`: Image files used in the report

## Developer Information
### Dependency Management
This project uses pip-compile to manage dependencies.  

```shell
# After editing requirements.in, update requirements.txt
pip-compile requirements.in

# Install dependencies
pip install -r requirements.txt
```

### Project Structure
```text
bedrock-tooluse-reporter/
├── main.py                # Main entry point
├── requirements.txt       # Dependencies
├── research/              # Research-related modules
│   ├── __init__.py
│   ├── perspective_explorer.py
│   ├── reporter.py
│   └── mermaid.md
├── utils/                 # Utility modules
│   ├── __init__.py
│   ├── bedrock.py
│   ├── bedrock_wrapper.py
│   ├── config.py
│   ├── conversation.py
│   ├── logger.py
│   ├── tools.py
│   └── utils.py
├── report/                # Generated reports
├── conversation/          # Conversation history
└── log/                   # Log files
```

## Configuration

Settings are managed in `utils/config.py`. Main configuration items:  

- AI model IDs
- Maximum execution count for each process
- Directory paths
- Tools to use
- Image-related settings
- Document-related settings

### Troubleshooting
- **API Key Error**: Verify that the `.brave` file is correctly placed
- **AWS Authentication Error**: Ensure authentication information is correctly set with `aws configure`
- **Model Access Error**: Confirm you have access to the specified Bedrock models
- **Memory Error**: Ensure sufficient memory when processing large images or long texts